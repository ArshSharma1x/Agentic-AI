"""The model boundary. Agents only see `LLM.complete`, so the provider can be swapped or scripted."""

import os
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
        extra = {"tools": tools} if tools else {}
        response = await self._client.messages.create(
            model=agent.model, max_tokens=MAX_OUTPUT_TOKENS, system=agent.system, messages=messages, **extra
        )
        blocks: list[dict] = []
        for block in response.content:
            if block.type == "text":
                blocks.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                blocks.append({"type": "tool_use", "id": block.id, "name": block.name, "input": block.input})
        return LLMResponse(blocks, response.usage.input_tokens, response.usage.output_tokens)


def llm_from_config() -> LLM | None:
    """A model client, or None. Order: an API key (config file or environment), then a logged-in Claude Code.

    `provider` in squad.config.json (or SQUAD_PROVIDER) can force "api" or "claude-code"; the default is "auto".
    """
    from .claude_code import ClaudeCodeLLM, claude_code_ready
    from .config import load_config

    config = load_config()
    mode = os.environ.get("SQUAD_PROVIDER") or config.provider
    if mode in ("auto", "api") and config.api_key:
        return AnthropicLLM(api_key=config.api_key)
    if mode in ("auto", "claude-code") and claude_code_ready():
        return ClaudeCodeLLM()
    return None


def describe(llm) -> str:
    return "Claude Code subscription" if type(llm).__name__ == "ClaudeCodeLLM" else "Anthropic API key"


def no_model_message() -> str:
    from .config import config_path

    return f"No model available: log in to Claude Code (run `claude`), or add an Anthropic API key to {config_path()} (see squad.config.example.json)."
