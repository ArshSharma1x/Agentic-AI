"""Connects the squad to MCP servers and decides which agent may call which tool."""

from collections.abc import Iterable
from contextlib import AsyncExitStack

from mcp import Client, StdioServerParameters

NAMESPACE_SEP = "__"
MAX_RESULT_CHARS = 8000


class ToolCallError(Exception):
    """A tool failed or was not allowed. The message is written for the agent to read."""


class MCPHost:
    def __init__(self) -> None:
        self._stack = AsyncExitStack()
        self._tools: dict[str, tuple[Client, object]] = {}

    async def __aenter__(self) -> "MCPHost":
        await self._stack.__aenter__()
        return self

    async def __aexit__(self, *exc) -> None:
        await self._stack.__aexit__(*exc)

    async def connect(self, name: str, params: StdioServerParameters) -> list[str]:
        """Launch an MCP server over stdio and register its tools as `<name>__<tool>`."""
        client = await self._stack.enter_async_context(Client(params))
        registered = []
        for tool in (await client.list_tools()).tools:
            qualified = f"{name}{NAMESPACE_SEP}{tool.name}"
            self._tools[qualified] = (client, tool)
            registered.append(qualified)
        return registered

    def tool_defs(self, allowed: Iterable[str]) -> list[dict]:
        """Tool definitions in the Anthropic tool-use format, limited to what an agent may use."""
        return [
            {"name": name, "description": tool.description or "", "input_schema": tool.input_schema}
            for name, (_, tool) in self._tools.items()
            if name in set(allowed)
        ]

    async def call(self, qualified: str, args: dict) -> str:
        """Call a tool with no permission check. Only the orchestrator uses this."""
        if qualified not in self._tools:
            raise ToolCallError(f"unknown tool: {qualified}")
        client, tool = self._tools[qualified]
        result = await client.call_tool(tool.name, args)
        text = "\n".join(c.text for c in result.content if getattr(c, "type", "") == "text")
        if result.is_error:
            raise ToolCallError(text or "tool failed")
        return text[:MAX_RESULT_CHARS]

    async def call_as(self, agent_name: str, allowed: set[str], qualified: str, args: dict) -> str:
        """Call a tool on behalf of an agent, enforcing that agent's abilities."""
        if qualified not in allowed:
            raise ToolCallError(f"{agent_name} is not allowed to use {qualified}")
        return await self.call(qualified, args)
