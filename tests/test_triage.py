import asyncio

import pytest

from squad.orchestrator import Match
from squad.projects import discover
from squad.scripted import ScriptedLLM
from squad.triage import offline_blocker, triage


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


def test_scripted_model_refuses_custom_code_changes_only():
    assert "ANTHROPIC_API_KEY" in offline_blocker(["FORGE"], "ASK-1", scripted=True)
    assert offline_blocker(["RADAR"], "ASK-1", scripted=True) is None
    assert offline_blocker(["FORGE"], "PAY-482", scripted=True) is None
    assert offline_blocker(["FORGE"], "ASK-1", scripted=False) is None


def play(text, tmp_path, project="refunds_api", **kwargs):
    plan = triage(text, project, **kwargs)
    match = Match(plan.ticket.id, llm=ScriptedLLM(), autonomy="full", runs_dir=tmp_path, ticket=plan.ticket,
                  project=discover()[project].path, squad_draft=plan.draft)
    return asyncio.run(match.run())


def test_a_question_runs_a_one_agent_match_and_reads_the_project(tmp_path):
    result = play("What does the refund function do?", tmp_path)
    assert result.success and result.squad == ["RADAR"] and result.commit is None
    assert "refunds.py" in result.answer


def test_a_review_squad_reports_findings_without_changing_or_committing(tmp_path):
    result = play("Run the tests", tmp_path)
    assert result.success and result.squad == ["WARDEN"] and result.commit is None
    assert "8 issue(s) found" in result.reason
