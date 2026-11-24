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
def read_file(path: str, offset: int = 1, limit: int = 2000) -> str:
    """Read a text file as numbered lines (number, tab, text). Long files say how to read the rest."""
    return ws.read_file(path, offset, limit)


@server.tool()
def edit_file(path: str, old: str, new: str) -> str:
    """Replace one exact occurrence of `old` with `new` in a file. `old` must match exactly once and must not
    include the line-number prefix from read_file. Prefer this to write_file for changing existing files."""
    return ws.edit_file(path, old, new)


@server.tool()
def write_file(path: str, content: str) -> str:
    """Create a new file, or replace a whole file. Existing tests, test configuration and CI are read-only."""
    return ws.write_file(path, content)


@server.tool()
def grep(pattern: str, glob: str = "**/*") -> str:
    """Search file contents with a regular expression; returns path:line: text. Narrow with a glob like '**/*.py'."""
    return ws.grep(pattern, glob)


@server.tool()
def glob(pattern: str) -> list[str]:
    """List files matching a glob pattern such as '**/*.py' or 'src/**/test_*.py'."""
    return ws.glob(pattern)


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
