"""Triage: read a free-text request and decide how big a squad it needs. Plain rules, logged like the draft."""

import re
import uuid
from dataclasses import dataclass

from .agents import FAST_MODEL, ROSTER
from .draft import SENSITIVE_LABELS, Draft, Pick, draft
from .models import AgentSpec, Role, Ticket

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


TRIAGE_TOOL = {
    "name": "submit_triage",
    "description": "Choose which agents the request needs. Call exactly once.",
    "input_schema": {
        "type": "object",
        "properties": {
            "kind": {"type": "string", "enum": ["question", "plan", "review", "test", "change"]},
            "agents": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"name": {"type": "string", "enum": ORDER}, "reason": {"type": "string"}},
                    "required": ["name", "reason"],
                },
                "description": "The smallest squad that can do the job well.",
            },
        },
        "required": ["kind", "agents"],
    },
}
DISPATCH = AgentSpec(
    name="DISPATCH", role=Role.CONTROLLER, model=FAST_MODEL, abilities=(), deliverable="submit_triage",
    system=(
        "You are DISPATCH. You read a request about a software project and pick the smallest squad that can do it. "
        "RADAR answers questions and gathers context (read-only). ATLAS writes plans and acceptance criteria. "
        "FORGE writes and changes code. WARDEN runs the tests and checks the work meets the criteria. AEGIS reviews "
        "for security problems. A question needs RADAR alone. A security audit needs AEGIS. Only code changes need "
        "FORGE. Do not add agents the job does not need. Call submit_triage once."
    ),
)


async def triage_with_model(text: str, project: str, llm, *, files: list[str] = (), ticket_id: str | None = None) -> Triage:
    """Let a model choose the squad, then apply the safety rules that must hold whatever it says.

    Falls back to the keyword rules if the model fails or returns nothing usable.
    """
    fallback = triage(text, project, ticket_id=ticket_id)
    prompt = f"Project: {project}\nFiles: {', '.join(list(files)[:60]) or '(unknown)'}\n\nRequest:\n{text}"
    try:
        reply = await llm.complete(
            agent=DISPATCH, messages=[{"role": "user", "content": prompt}], tools=[TRIAGE_TOOL], meta={}
        )
        call = next(b for b in reply.content if b.get("type") == "tool_use" and b["name"] == "submit_triage")
        kind = call["input"]["kind"]
        chosen = {a["name"]: a["reason"] for a in call["input"]["agents"] if a.get("name") in ROSTER}
    except Exception:
        return fallback
    if not chosen:
        return fallback
    ticket = _ticket(text, project, fallback.ticket.id, kind)
    # Rules that hold whatever the model says: nothing ships without QA, and sensitive code gets a security gate.
    if "FORGE" in chosen and "WARDEN" not in chosen:
        chosen["WARDEN"] = "rule: nothing ships without a QA gate"
    sensitive = SENSITIVE_LABELS & set(ticket.labels)
    if "FORGE" in chosen and sensitive and "AEGIS" not in chosen:
        chosen["AEGIS"] = f"rule: the request touches {', '.join(sorted(sensitive))}, so it gets a security gate"
    return Triage(kind, _picks(*[(a, chosen[a]) for a in ORDER if a in chosen]), ticket)
