import asyncio

import pytest

from squad.llm import LLMResponse
from squad.mcp_host import MCPHost, ToolCallError
from squad.orchestrator import Match, server_params
from squad.render import render
from squad.scripted import ScriptedLLM
from squad.trace import Trace


def play(ticket_id, tmp_path, **kwargs):
    match = Match(ticket_id, llm=kwargs.pop("llm", ScriptedLLM()), autonomy="full", runs_dir=tmp_path, **kwargs)
    return asyncio.run(match.run())


def test_payments_feature_is_rejected_by_security_then_fixed(tmp_path):
    result = play("PAY-482", tmp_path)
    assert result.success and result.attempts == 2 and result.commit
    assert result.squad == ["RADAR", "ATLAS", "FORGE", "WARDEN", "AEGIS"]

    events = Trace.load(tmp_path.joinpath(*result.trace_path.split("/")[-2:]))
    verdicts = [e for e in events if e["type"] == "verdict"]
    first_aegis = next(v for v in verdicts if v["agent"] == "AEGIS")
    assert not first_aegis["passed"] and "missing-authorization-check" in first_aegis["issues"][0]
    assert any(e["type"] == "retry" for e in events)
    assert events[-1]["type"] == "match_end" and events[-1]["success"]


def test_small_bug_runs_a_minimal_squad_with_no_retry(tmp_path):
    result = play("BUG-101", tmp_path)
    assert result.success and result.attempts == 1
    assert result.squad == ["RADAR", "FORGE", "WARDEN"]


def test_giving_up_after_max_retries_does_not_commit(tmp_path):
    result = play("PAY-482", tmp_path, max_retries=0)
    assert not result.success and result.commit is None
    assert "still failing" in result.reason


def test_semi_autonomy_asks_before_commit_and_a_no_leaves_it_uncommitted(tmp_path):
    asked = []

    async def deny(question):
        asked.append(question)
        return False

    match = Match("BUG-101", llm=ScriptedLLM(), autonomy="semi", approve=deny, runs_dir=tmp_path)
    result = asyncio.run(match.run())
    assert asked == ["Commit the changes for BUG-101?"]
    assert result.success and result.commit is None and "not approved" in result.reason


def test_unknown_ticket_fails_cleanly(tmp_path):
    with pytest.raises(ToolCallError, match="unknown ticket"):
        play("NOPE-1", tmp_path)


def test_agents_cannot_use_tools_outside_their_abilities(tmp_path):
    async def attempt():
        async with MCPHost() as host:
            await host.connect("jira", server_params("jira"))
            with pytest.raises(ToolCallError, match="not allowed"):
                await host.call_as("FORGE", {"workspace__read_file"}, "jira__get_ticket", {"ticket_id": "BUG-101"})

    asyncio.run(attempt())


def test_agent_that_never_hands_in_work_is_stopped(tmp_path):
    class Chatty:
        async def complete(self, **_):
            return LLMResponse([{"type": "text", "text": "thinking..."}])

    result = play("BUG-101", tmp_path, llm=Chatty())
    assert not result.success and result.commit is None
    assert "stopped without calling" in result.reason


def test_every_event_renders_or_is_deliberately_skipped(tmp_path):
    result = play("BUG-101", tmp_path)
    events = Trace.load(tmp_path.joinpath(*result.trace_path.split("/")[-2:]))
    skipped = {e["type"] for e in events if render(e) is None}
    assert skipped <= {"agent_start", "blackboard"}
