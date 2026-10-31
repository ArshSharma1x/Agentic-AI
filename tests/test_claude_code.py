import asyncio
import json

import pytest

from squad import claude_code, llm
from squad.agents import ROSTER
from squad.claude_code import ClaudeCodeLLM, _render, _schema
from squad.config import ConfigError, load_config

TOOLS = [
    {"name": "workspace__list_files", "description": "list", "input_schema": {"type": "object", "properties": {}}},
    {"name": "submit_intel", "description": "hand in", "input_schema": {"type": "object", "properties": {"summary": {"type": "string"}}}},
]


class Canned(ClaudeCodeLLM):
    def __init__(self, replies):
        self.replies, self.calls = list(replies), []

    async def _run(self, system, prompt, model, schema):
        self.calls.append((system, prompt, schema))
        return self.replies.pop(0)


def reply(payload, **usage):
    return {"result": payload if isinstance(payload, str) else json.dumps(payload), "usage": {"input_tokens": 5, "cache_creation_input_tokens": 100, "cache_read_input_tokens": 9000, "output_tokens": 7, **usage}}


def complete(model, tools=TOOLS, messages=None):
    return asyncio.run(model.complete(agent=ROSTER["RADAR"], messages=messages or [{"role": "user", "content": "hi"}], tools=tools, meta={}))


def test_replies_become_tool_use_blocks_and_cache_reads_are_not_counted():
    out = complete(Canned([reply({"calls": [{"tool": "workspace__list_files", "input": {}}]})]))
    assert [b["name"] for b in out.content if b["type"] == "tool_use"] == ["workspace__list_files"]
    assert out.input_tokens == 105 and out.output_tokens == 7


def test_a_submit_call_waits_for_the_other_calls_in_the_same_step():
    out = complete(Canned([reply({"calls": [
        {"tool": "workspace__list_files", "input": {}}, {"tool": "submit_intel", "input": {"summary": "x"}}]})]))
    assert [b["name"] for b in out.content] == ["workspace__list_files"]


def test_a_lone_submit_call_goes_through():
    out = complete(Canned([reply({"calls": [{"tool": "submit_intel", "input": {"summary": "done"}}]})]))
    assert out.content[0]["input"] == {"summary": "done"}


def test_unknown_tools_are_dropped_and_bad_json_is_retried_once():
    model = Canned([reply("not json"), reply({"calls": [{"tool": "rm_rf", "input": {}}, {"tool": "workspace__list_files", "input": {}}]})])
    assert [b["name"] for b in complete(model).content] == ["workspace__list_files"]
    assert len(model.calls) == 2
    with pytest.raises(claude_code.ClaudeCodeError):
        complete(Canned([reply("nope"), reply("nope")]))


def test_with_no_tools_it_is_plain_text():
    model = Canned([reply("Hello there")])
    out = complete(model, tools=[])
    assert out.content == [{"type": "text", "text": "Hello there"}] and model.calls[0][2] is None


def test_the_transcript_and_schema_carry_the_real_tool_definitions():
    text = _render([
        {"role": "user", "content": "Do it"},
        {"role": "assistant", "content": [{"type": "tool_use", "id": "1", "name": "workspace__list_files", "input": {}}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "1", "content": "a.py b.py"}]},
    ])
    assert "TASK:\nDo it" in text and "YOU CALLED: workspace__list_files" in text and "RESULT: a.py b.py" in text
    options = _schema(TOOLS)["properties"]["calls"]["items"]["anyOf"]
    assert [o["properties"]["tool"]["const"] for o in options] == ["workspace__list_files", "submit_intel"]


def test_provider_order_and_overrides(monkeypatch, tmp_path):
    cfg = tmp_path / "squad.config.json"
    cfg.write_text(json.dumps({"anthropic": {"api_key": "sk-ant-real"}}))
    monkeypatch.setenv("SQUAD_CONFIG", str(cfg))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("SQUAD_PROVIDER", raising=False)
    monkeypatch.setattr(claude_code, "claude_code_ready", lambda: True)
    assert type(llm.llm_from_config()).__name__ == "AnthropicLLM"  # a key wins in auto
    monkeypatch.setenv("SQUAD_PROVIDER", "claude-code")
    assert type(llm.llm_from_config()).__name__ == "ClaudeCodeLLM"
    cfg.write_text("{}")
    monkeypatch.delenv("SQUAD_PROVIDER")
    assert type(llm.llm_from_config()).__name__ == "ClaudeCodeLLM"  # no key: fall back to the login
    monkeypatch.setattr(claude_code, "claude_code_ready", lambda: False)
    assert llm.llm_from_config() is None


def test_an_unknown_provider_is_a_config_error(tmp_path):
    cfg = tmp_path / "c.json"
    cfg.write_text('{"provider": "banana"}')
    with pytest.raises(ConfigError):
        load_config(cfg)
