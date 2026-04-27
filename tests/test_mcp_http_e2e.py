from __future__ import annotations

import json
import socket
import subprocess
import sys
import time

import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_for_port(port: int, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with socket.socket() as sock:
            sock.settimeout(0.25)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.05)
    raise TimeoutError(f"Timed out waiting for PulseAgent on port {port}.")


def _stop_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


@pytest.mark.asyncio
async def test_streamable_http_mcp_replan_ack_flow(tmp_path):
    port = _free_port()
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "pulse_agent",
            "start",
            "--project",
            str(tmp_path),
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    try:
        _wait_for_port(port)
        guidance = tmp_path / ".pulse" / "guidance.md"
        plan = tmp_path / ".pulse" / "plan.md"
        guidance.write_text("# Guidance\n\nUse the HTTP MCP flow.\n", encoding="utf-8")

        async with streamable_http_client(f"http://127.0.0.1:{port}/mcp") as (
            read_stream,
            write_stream,
            _,
        ):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                result = await session.call_tool(
                    "pulse_should_interrupt",
                    {"last_seen_event_id": None},
                )
                decision = json.loads(result.content[0].text)
                assert decision["needs_replan"] is True
                assert decision["pending_replan_event_id"]
                assert decision["pending_replan_files"] == [".pulse/guidance.md"]

                plan.write_text("# Plan\n\nHandle the HTTP MCP flow.\n", encoding="utf-8")
                ack_result = await session.call_tool(
                    "pulse_ack_replan",
                    {"event_id": decision["pending_replan_event_id"]},
                )
                ack = json.loads(ack_result.content[0].text)
                assert ack["accepted"] is True
                assert ack["acknowledged_event_id"] == decision["pending_replan_event_id"]
                assert ack["plan_sha256"]

                next_result = await session.call_tool(
                    "pulse_should_interrupt",
                    {"last_seen_event_id": decision["latest_event_id"]},
                )
                next_decision = json.loads(next_result.content[0].text)
                assert next_decision["needs_replan"] is False
                assert next_decision["pending_replan_event_id"] is None
                assert next_decision["last_acknowledged_event_id"] == ack["acknowledged_event_id"]
    finally:
        _stop_process(process)
