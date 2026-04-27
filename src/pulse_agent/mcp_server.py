from __future__ import annotations

from pathlib import Path

from mcp.server.fastmcp import FastMCP

from .context import compile_context
from .policy import should_interrupt
from .protocol import ensure_pulse_dir


def create_mcp(
    project: str | Path | None = None,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> FastMCP:
    project_root = ensure_pulse_dir(project).project_root
    mcp = FastMCP(
        "PulseAgent",
        host=host,
        port=port,
        stateless_http=True,
        json_response=True,
        streamable_http_path="/mcp",
    )

    @mcp.resource("pulse://context/latest")
    def latest_context() -> str:
        """Return the latest PulseAgent context summary."""
        return compile_context(project_root)

    @mcp.tool()
    def pulse_should_interrupt(last_seen_event_id: str | None = None) -> dict:
        """Check whether an IDE agent should pause and replan."""
        return should_interrupt(project_root, last_seen_event_id).model_dump(mode="json")

    @mcp.prompt()
    def pulse_replan() -> str:
        """Prompt an agent to replan using the latest PulseAgent context."""
        return (
            "Before continuing, read pulse://context/latest and call "
            "pulse_should_interrupt with your last seen event id. If needs_replan is true, "
            "pause implementation, summarize the changed guidance or constraints, "
            "update your plan, "
            "then continue only under the latest PulseAgent context."
        )

    return mcp


def run_server(
    project: str | Path | None = None,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> None:
    mcp = create_mcp(project, host=host, port=port)
    mcp.run(transport="streamable-http")
