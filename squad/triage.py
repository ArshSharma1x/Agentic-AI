"""Triage: read a free-text request and decide how big a squad it needs. Plain rules, logged like the draft."""

import re
import uuid
from dataclasses import dataclass

from .agents import ROSTER
from .draft import Draft, Pick, draft
from .models import Ticket

CHANGE_VERBS = {
    "fix", "add", "implement", "build", "create", "refactor", "change", "update", "write", "remove", "rename",
    "make", "support", "handle", "patch", "introduce", "replace", "delete", "migrate",
}
POLITE = re.compile(r"^(please|can you|could you|would you|i want you to|i need you to|we need to|let's|lets)\s+", re.I)
PLAN_REQUEST = re.compile(r"^(make|create|write|draft|give me)( me)?( a| the)? (plan|breakdown)\b|\b(plan for|break (it|this) down|how should we)\b", re.I)
SECURITY = re.compile(r"\b(security|secure|insecure|vulnerab\w*|exploit\w*|injection|secrets?|permissions?|authori[sz]\w*)\b", re.I)
REVIEW = re.compile(r"\b(review|audit|code quality|sanity check)\b", re.I)
TESTS = re.compile(r"\b(run (the )?tests?|do (the )?tests? pass|test status|are (the )?tests? (passing|failing)|failing tests?)\b", re.I)
QUESTION_START = re.compile(r"^(what|how|why|where|which|who|when|explain|describe|summari[sz]e|show|list|tell|is|are|does|do|can)\b", re.I)
LABEL_WORDS = {
    "payments": r"\b(payments?|refunds?|charges?|billing|money|transfers?|payouts?)\b",
    "auth": r"\b(auth\w*|login|passwords?|permissions?)\b",
    "pii": r"\b(pii|personal data|secrets?)\b",
    "security": r"\b(security|secure|vulnerab\w*)\b",
}
ORDER = ["RADAR", "ATLAS", "FORGE", "WARDEN", "AEGIS"]


@dataclass(frozen=True)
class Triage:
    kind: str  # question, plan, review, test or change
    draft: Draft
    ticket: Ticket


def _picks(*pairs: tuple[str, str]) -> Draft:
    chosen = {a for a, _ in pairs}
    return Draft(tuple(Pick(a, r) for a, r in pairs), tuple(Pick(a, "not needed for this request") for a in ORDER if a not in chosen))


def _kind(text: str) -> tuple[str, str]:
    stripped = POLITE.sub("", text.strip())
    words = stripped.split()
    first = re.sub(r"\W", "", words[0].lower()) if words else ""
    if PLAN_REQUEST.search(stripped):
        return "plan", "asks for a plan"
    if first in CHANGE_VERBS:
        return "change", f"starts with an action verb ({first})"
    if SECURITY.search(stripped) or REVIEW.search(stripped):
        return "review", "asks for a review or mentions security"
    if TESTS.search(stripped):
        return "test", "asks about the test results"
    if QUESTION_START.match(stripped) or stripped.endswith("?"):
        return "question", "reads as a question"
    if any(re.sub(r"\W", "", w.lower()) in CHANGE_VERBS for w in words):
        return "change", "asks for something to be changed"
    return "question", "no action asked for, so treated as a question (pick agents yourself to override)"


def _ticket(text: str, project: str, ticket_id: str, kind: str) -> Ticket:
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    criteria = tuple(re.sub(r"^([-*]|\d+[.)])\s+", "", l) for l in lines if re.match(r"^([-*]|\d+[.)])\s+", l))
    labels = [name for name, pattern in LABEL_WORDS.items() if re.search(pattern, text, re.I)]
    if kind == "change":
        labels.append("bug" if re.search(r"\b(bug|broken|wrong|fix)\b", text, re.I) else "feature")
    title = (lines[0] if lines else text)[:80]
    ttype = "bug" if "bug" in labels else "feature" if kind == "change" else kind
    return Ticket(
        id=ticket_id, title=title, type=ttype, description=text.strip(), labels=tuple(labels),
        repos=(project,), sandbox=project, acceptance_criteria=criteria,
    )


def triage(text: str, project: str, *, agents: list[str] | None = None, ticket_id: str | None = None) -> Triage:
    kind, why = _kind(text)
    ticket = _ticket(text, project, ticket_id or f"ASK-{uuid.uuid4().hex[:5].upper()}", kind)
    if agents:
        unknown = [a for a in agents if a not in ROSTER]
        if unknown:
            raise ValueError(f"unknown agent(s): {', '.join(unknown)}")
        squad = _picks(*[(a, "picked by you") for a in ORDER if a in agents])
        return Triage(kind, squad, ticket)
    if kind == "question":
        squad = _picks(("RADAR", f"{why}: one Initiator can answer it from the code and docs"))
    elif kind == "plan":
        squad = _picks(("RADAR", f"{why}: plan on facts, not guesses"), ("ATLAS", "writes the plan"))
    elif kind == "test":
        squad = _picks(("WARDEN", f"{why}: only the QA gate is needed"))
    elif kind == "review":
        if SECURITY.search(text):
            squad = _picks(("AEGIS", f"{why}: the Security Sentinel reviews code that is already there"))
        else:
            squad = _picks(("WARDEN", f"{why}: runs the tests"), ("AEGIS", "second pair of eyes on security"))
    else:
        squad = draft(ticket)
    return Triage(kind, squad, ticket)


def offline_blocker(squad_names: list[str], ticket_id: str, *, scripted: bool) -> str | None:
    """The scripted model can read, test and scan any project, but it can only write code for the two demo tickets."""
    from .scripted import IMPLEMENTATIONS

    if scripted and "FORGE" in squad_names and ticket_id not in IMPLEMENTATIONS:
        return "FORGE needs a real model to write code for a custom request. Set ANTHROPIC_API_KEY, or pick a squad without FORGE."
    return None
