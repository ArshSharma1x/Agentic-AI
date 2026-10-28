import asyncio

import pytest

from squad.orchestrator import Match
from squad.projects import discover
from squad.scripted import ScriptedLLM
from squad.llm import LLMResponse
from squad.triage import triage, triage_with_model


@pytest.mark.parametrize("text, kind, squad", [
    ("What does the refund function do?", "question", ["RADAR"]),
    ("How do I fix the leading zero?", "question", ["RADAR"]),
    ("Is the refund function secure?", "review", ["AEGIS"]),
    ("Review this code", "review", ["WARDEN", "AEGIS"]),
    ("Run the tests", "test", ["WARDEN"]),
    ("Make a plan to add refunds", "plan", ["RADAR", "ATLAS"]),
    ("Fix the amount formatting bug", "change", ["RADAR", "ATLAS", "FORGE", "WARDEN"]),
    ("Please add a refund endpoint for payments", "change", ["RADAR", "ATLAS", "FORGE", "WARDEN", "AEGIS"]),
])
def test_triage_sizes_the_squad_from_the_request(text, kind, squad):
    result = triage(text, "refunds_api")
    assert result.kind == kind and result.draft.names == squad


def test_user_picked_agents_override_triage_and_keep_canonical_order():
    result = triage("anything", "refunds_api", agents=["AEGIS", "RADAR"])
    assert result.draft.names == ["RADAR", "AEGIS"]
    with pytest.raises(ValueError):
        triage("anything", "refunds_api", agents=["NOPE"])


def test_bullets_in_the_request_become_acceptance_criteria():
    ticket = triage("Fix it\n- amounts under a dollar keep a zero\n- zero shows $0.00", "amount_format").ticket
    assert ticket.acceptance_criteria == ("amounts under a dollar keep a zero", "zero shows $0.00")


def play(text, tmp_path, project="refunds_api", **kwargs):
    plan = triage(text, project, **kwargs)
    match = Match(plan.ticket.id, llm=ScriptedLLM(), autonomy="full", runs_dir=tmp_path, ticket=plan.ticket,
                  project=discover(demo=True)[project].path, squad_draft=plan.draft)
    return asyncio.run(match.run())


def test_a_question_runs_a_one_agent_match_and_reads_the_project(tmp_path):
    result = play("What does the refund function do?", tmp_path)
    assert result.success and result.squad == ["RADAR"] and result.commit is None
    assert "refunds.py" in result.answer


def test_a_review_squad_reports_findings_without_changing_or_committing(tmp_path):
    result = play("Run the tests", tmp_path)
    assert result.success and result.squad == ["WARDEN"] and result.commit is None
    assert "8 issue(s) found" in result.reason


class FakeModel:
    def __init__(self, agents=None, kind="change", fail=False):
        self.agents, self.kind, self.fail = agents, kind, fail

    async def complete(self, *, agent, messages, tools, meta):
        if self.fail:
            raise RuntimeError("api down")
        picked = [{"name": n, "reason": f"{n} because"} for n in self.agents]
        return LLMResponse([{"type": "tool_use", "id": "x", "name": "submit_triage", "input": {"kind": self.kind, "agents": picked}}])


def names(model, text="do it"):
    return asyncio.run(triage_with_model(text, "refunds_api", model)).draft.names


def test_the_model_picks_the_squad_and_its_reasons_are_kept():
    result = asyncio.run(triage_with_model("explain", "refunds_api", FakeModel(["RADAR"], kind="question")))
    assert result.draft.names == ["RADAR"] and result.draft.picks[0].reason == "RADAR because"


def test_forge_always_brings_a_qa_gate_whatever_the_model_says():
    assert names(FakeModel(["FORGE"])) == ["FORGE", "WARDEN"]


def test_sensitive_code_changes_always_get_a_security_gate():
    assert names(FakeModel(["FORGE", "WARDEN"]), "Add a refund endpoint for payments") == ["FORGE", "WARDEN", "AEGIS"]
    assert names(FakeModel(["RADAR"], kind="question"), "Explain the payments refund flow") == ["RADAR"]


def test_a_failing_or_empty_model_falls_back_to_the_keyword_rules():
    assert names(FakeModel(fail=True), "What does refund() do?") == ["RADAR"]
    assert names(FakeModel([]), "Run the tests") == ["WARDEN"]
