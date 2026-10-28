import json

from squad.draft import draft
from squad.models import Ticket
from squad.paths import DATA_DIR


def load(ticket_id: str) -> Ticket:
    return Ticket.from_dict(json.loads((DATA_DIR / "tickets.json").read_text())[ticket_id])


def test_payments_feature_gets_the_full_squad():
    result = draft(load("PAY-482"))
    assert result.names == ["RADAR", "ATLAS", "FORGE", "WARDEN", "AEGIS"]
    reasons = {p.agent: p.reason for p in result.picks}
    assert "no acceptance criteria" in reasons["ATLAS"]
    assert "payments" in reasons["AEGIS"]


def test_small_bug_gets_a_minimal_squad():
    result = draft(load("BUG-101"))
    assert result.names == ["RADAR", "FORGE", "WARDEN"]
    assert {p.agent for p in result.skipped} == {"ATLAS", "AEGIS"}


def test_multi_repo_work_adds_a_controller_even_with_criteria():
    base = load("BUG-101")
    ticket = Ticket(**{**base.__dict__, "repos": ("a", "b")})
    assert "ATLAS" in draft(ticket).names


def test_every_pick_has_a_reason():
    for ticket_id in ("PAY-482", "BUG-101"):
        assert all(p.reason for p in draft(load(ticket_id)).picks)
