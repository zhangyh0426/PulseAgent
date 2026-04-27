from __future__ import annotations

import json

import pytest

from pulse_agent.mcp_server import create_mcp


@pytest.mark.asyncio
async def test_mcp_surface_exposes_resource_tool_and_prompt(tmp_path):
    mcp = create_mcp(tmp_path)

    tools = await mcp.list_tools()
    resources = await mcp.list_resources()
    prompts = await mcp.list_prompts()

    assert [tool.name for tool in tools] == ["pulse_should_interrupt", "pulse_ack_replan"]
    assert [str(resource.uri) for resource in resources] == ["pulse://context/latest"]
    assert [prompt.name for prompt in prompts] == ["pulse_replan"]

    tool_result = await mcp.call_tool("pulse_should_interrupt", {"last_seen_event_id": None})
    decision = json.loads(tool_result[0].text)
    assert decision["needs_replan"] is False
    assert "latest_event_id" in decision
    assert "pending_replan_event_id" in decision
    assert "last_acknowledged_event_id" in decision

    ack_result = await mcp.call_tool("pulse_ack_replan", {"event_id": "evt_missing"})
    ack = json.loads(ack_result[0].text)
    assert ack["accepted"] is False
    assert "acknowledged_event_id" in ack
    assert "plan_sha256" in ack

    resource_result = await mcp.read_resource("pulse://context/latest")
    assert "# PulseAgent Context" in resource_result[0].content

    prompt_result = await mcp.get_prompt("pulse_replan")
    assert "pulse_should_interrupt" in prompt_result.messages[0].content.text
