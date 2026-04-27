from __future__ import annotations

from pathlib import Path

import typer

from . import __version__
from .mcp_server import run_server
from .protocol import ensure_pulse_dir
from .watcher import start_watcher_thread

app = typer.Typer(help="PulseAgent interrupt-aware MCP sidecar.")


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"pulse-agent {__version__}")
        raise typer.Exit()


VERSION_OPTION = typer.Option(
    False,
    "--version",
    callback=_version_callback,
    is_eager=True,
    help="Show the PulseAgent version.",
)
PROJECT_OPTION = typer.Option(Path("."), "--project", "-p", help="Project root to watch.")
HOST_OPTION = typer.Option("127.0.0.1", "--host", help="HTTP host for the MCP sidecar.")
PORT_OPTION = typer.Option(8765, "--port", help="HTTP port for the MCP sidecar.")


@app.callback()
def main(
    version: bool = VERSION_OPTION,
) -> None:
    _ = version


@app.command()
def start(
    project: Path = PROJECT_OPTION,
    host: str = HOST_OPTION,
    port: int = PORT_OPTION,
) -> None:
    """Initialize .pulse and start the MCP HTTP sidecar."""
    paths = ensure_pulse_dir(project)
    start_watcher_thread(paths.project_root)
    typer.echo(f"PulseAgent watching {paths.pulse_dir}")
    typer.echo(f"MCP endpoint: http://{host}:{port}/mcp")
    run_server(paths.project_root, host=host, port=port)
