"""MCP server exposing the sandboxed workspace (filesystem, tests, git, security scan)."""

import os
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from ..workspace import Workspace

server = MCPServer("workspace")
ws = Workspace(Path(os.environ["SQUAD_WORKSPACE"]))


@server.tool()
def list_files() -> list[str]:
    """List every file in the workspace, relative to its root."""
    return ws.list_files()


@server.tool()
def read_file(path: str) -> str:
    """Read a text file from the workspace."""
    return ws.read_file(path)


@server.tool()
def write_file(path: str, content: str) -> str:
    """Create or overwrite a file. The tests/ directory is read-only."""
    return ws.write_file(path, content)


@server.tool()
def run_tests() -> dict:
    """Run the project's test suite and return pass/fail plus the pytest output."""
    return ws.run_tests()


@server.tool()
def git_diff() -> str:
    """Show every change made since the baseline commit."""
    return ws.git_diff()


@server.tool()
def security_scan() -> dict:
    """Run the heuristic security scanner over the source files."""
    return ws.security_scan()


@server.tool()
def git_commit(message: str) -> str:
    """Commit all changes. Reserved for the orchestrator after human approval."""
    return ws.git_commit(message)


if __name__ == "__main__":
    server.run()
