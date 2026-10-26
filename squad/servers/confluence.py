"""MCP server standing in for Confluence. Reads pages from data/docs.json."""

import json

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from ..paths import DATA_DIR

server = MCPServer("confluence")


def _docs() -> dict:
    return json.loads((DATA_DIR / "docs.json").read_text())


@server.tool()
def get_doc(doc_id: str) -> dict:
    """Fetch a documentation page by id."""
    docs = _docs()
    if doc_id not in docs:
        raise ToolError(f"unknown doc: {doc_id}")
    return docs[doc_id]


@server.tool()
def search_docs(query: str) -> list[dict]:
    """Search documentation pages by title or body text."""
    q = query.lower()
    return [
        {"id": d["id"], "title": d["title"]}
        for d in _docs().values()
        if q in d["title"].lower() or q in d["body"].lower()
    ]


if __name__ == "__main__":
    server.run()
