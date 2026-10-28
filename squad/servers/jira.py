"""MCP server standing in for Jira. Reads tickets from data/tickets.json."""

import json

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from ..paths import DATA_DIR

server = MCPServer("jira")


def _tickets() -> dict:
    return json.loads((DATA_DIR / "tickets.json").read_text())


@server.tool()
def get_ticket(ticket_id: str) -> dict:
    """Fetch a ticket by id, including labels, linked docs and acceptance criteria."""
    tickets = _tickets()
    if ticket_id not in tickets:
        raise ToolError(f"unknown ticket: {ticket_id}")
    return tickets[ticket_id]


@server.tool()
def list_tickets() -> list[dict]:
    """List every ticket with its id, title and type."""
    return [{"id": t["id"], "title": t["title"], "type": t["type"]} for t in _tickets().values()]


if __name__ == "__main__":
    server.run()
