"""The built-in author's tools and loop: exact edits, search, honest truncation, cut-off replies, caching."""

import asyncio
from types import SimpleNamespace

import pytest

from squad.agents import ROSTER
from squad.llm import AnthropicLLM, LLMResponse
from squad.workspace import Workspace, WorkspaceError


@pytest.fixture
def ws(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "app.py").write_text("def a():\n    return 1\n\n\ndef b():\n    return 1\n")
    (tmp_path / "tests" / "test_app.py").write_text("def test_a():\n    assert True\n")
    w = Workspace(tmp_path)
    w.init_repo()
    return w


def test_edit_file_needs_one_exact_match(ws):
    with pytest.raises(WorkspaceError, match="found 2 times"):
        ws.edit_file("app.py", "return 1", "return 2")
    ws.edit_file("app.py", "def b():\n    return 1", "def b():\n    return 2")
    assert "return 2" in (ws.root / "app.py").read_text()
    with pytest.raises(WorkspaceError, match="read-only"):
        ws.edit_file("tests/test_app.py", "assert True", "assert False")


def test_read_file_pages_instead_of_cutting_silently(ws):
    (ws.root / "big.py").write_text("\n".join(f"x{i} = {i}" for i in range(50)))
    first = ws.read_file("big.py", limit=10)
    assert first.splitlines()[0].strip().startswith("1\tx0") and "40 more line(s): read_file with offset=11" in first
    assert ws.read_file("big.py", offset=48).splitlines()[-1].endswith("x49 = 49")


def test_grep_and_glob_find_code(ws):
    assert ws.grep(r"def \w\(", "*.py").splitlines() == ["app.py:1: def a():", "app.py:5: def b():"]
    assert ws.glob("tests/*.py") == ["tests/test_app.py"]


def test_a_cut_off_reply_runs_none_of_its_tool_calls(tmp_path):
    from squad.orchestrator import Match
    from squad.scripted import ScriptedLLM, _use

    class CutOff(ScriptedLLM):
        cut = True

        async def complete(self, *, agent, messages, tools, meta):
            if agent.name == "FORGE" and self.cut:
                self.cut = False
                return LLMResponse([_use("workspace__write_file", path="money.py", content="def format_amount(c")], stop_reason="max_tokens")
            return await super().complete(agent=agent, messages=messages, tools=tools, meta=meta)

    result = asyncio.run(Match("BUG-101", llm=CutOff(), autonomy="full", runs_dir=tmp_path).run())
    assert result.success and result.verdict == "PASS"  # the half-written file was never written


def test_the_api_client_caches_the_prompt_prefix_and_reports_the_stop_reason():
    seen = {}

    class Messages:
        async def create(self, **kwargs):
            seen.update(kwargs)
            usage = SimpleNamespace(input_tokens=10, cache_creation_input_tokens=5, output_tokens=3)
            return SimpleNamespace(content=[SimpleNamespace(type="text", text="hi")], usage=usage, stop_reason="max_tokens")

    llm = AnthropicLLM(client=SimpleNamespace(messages=Messages()))
    history = [{"role": "user", "content": "do it"}]
    tools = [{"name": "a", "input_schema": {}}, {"name": "b", "input_schema": {}}]
    reply = asyncio.run(llm.complete(agent=ROSTER["FORGE"], messages=history, tools=tools, meta={}))
    assert reply.stop_reason == "max_tokens" and reply.input_tokens == 15
    assert seen["system"][0]["cache_control"] and seen["tools"][-1]["cache_control"] and "cache_control" not in seen["tools"][0]
    assert seen["messages"][-1]["content"][-1]["cache_control"] and history == [{"role": "user", "content": "do it"}]
