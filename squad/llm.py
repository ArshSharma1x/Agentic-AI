"""The model boundary. Agents only see `LLM.complete`, so the provider can be swapped or scripted."""

from dataclasses import dataclass, field
from typing import Protocol

from .models import AgentSpec

MAX_OUTPUT_TOKENS = 4096


@dataclass
class LLMResponse:
    """Content blocks are plain dicts: {"type": "text", ...} or {"type": "tool_use", "id", "name", "input"}."""

    content: list[dict]
    input_tokens: int = 0
    output_tokens: int = 0
    meta: dict = field(default_factory=dict)


class LLM(Protocol):
    async def complete(
        self, *, agent: AgentSpec, messages: list[dict], tools: list[dict], meta: dict
    ) -> LLMResponse: ...


class AnthropicLLM:
    """Calls the Claude Messages API with tool use."""

    def __init__(self, client=None, api_key: str | None = None) -> None:
        from anthropic import AsyncAnthropic

        self._client = client or AsyncAnthropic(api_key=api_key)

    async def complete(self, *, agent, messages, tools, meta) -> LLMResponse:
        response = await self._client.messages.create(
            model=agent.model,
            max_tokens=MAX_OUTPUT_TOKENS,
            system=agent.system,
            messages=messages,
            tools=tools,
        )
        blocks: list[dict] = []
        for block in response.content:
            if block.type == "text":
                blocks.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                blocks.append({"type": "tool_use", "id": block.id, "name": block.name, "input": block.input})
        return LLMResponse(blocks, response.usage.input_tokens, response.usage.output_tokens)


def llm_from_config() -> AnthropicLLM | None:
    """A model client if a key is configured (squad.config.json or the environment), else None."""
    from .config import load_config

    key = load_config().api_key
    return AnthropicLLM(api_key=key) if key else None
