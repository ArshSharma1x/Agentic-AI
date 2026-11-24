"""The model boundary. Agents only see `LLM.complete`, so the provider can be swapped or scripted."""

import os
from dataclasses import dataclass, field
from typing import Protocol

from .models import AgentSpec

MAX_OUTPUT_TOKENS = 16000


@dataclass
class LLMResponse:
    """Content blocks are plain dicts: {"type": "text", ...} or {"type": "tool_use", "id", "name", "input"}."""

    content: list[dict]
    input_tokens: int = 0
    output_tokens: int = 0
    meta: dict = field(default_factory=dict)
    stop_reason: str = "end_turn"  # "max_tokens" means the reply was cut off, tool calls and all


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
        # Cache the stable prefix (system, tools, history so far): each step then re-reads it at a fraction of the price.
        cache = {"type": "ephemeral"}
        extra = {"tools": [*tools[:-1], {**tools[-1], "cache_control": cache}]} if tools else {}
        history = [*messages[:-1], _cached(messages[-1])] if messages else messages
        response = await self._client.messages.create(
            model=agent.model, max_tokens=MAX_OUTPUT_TOKENS, messages=history,
            system=[{"type": "text", "text": agent.system, "cache_control": cache}], **extra,
        )
        blocks: list[dict] = []
        for block in response.content:
            if block.type == "text":
                blocks.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                blocks.append({"type": "tool_use", "id": block.id, "name": block.name, "input": block.input})
        usage = response.usage
        tokens_in = usage.input_tokens + (getattr(usage, "cache_creation_input_tokens", 0) or 0)
        return LLMResponse(blocks, tokens_in, usage.output_tokens, stop_reason=response.stop_reason or "end_turn")


def _cached(message: dict) -> dict:
    """The newest message with a cache breakpoint on its last block (copied: the caller's history is not touched)."""
    content = message["content"]
    if isinstance(content, str):
        content = [{"type": "text", "text": content}]
    if not content:
        return message
    return {**message, "content": [*content[:-1], {**content[-1], "cache_control": {"type": "ephemeral"}}]}


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
