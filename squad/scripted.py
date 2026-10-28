"""A scripted stand-in for the model.

It lets the whole pipeline run without an API key: the MCP servers, the tools, the tests, the
security scanner, the verification gates and the retry loop all run for real. Only the model's
decisions are canned, so this proves the machinery and says nothing about model quality.
"""

import json
import uuid

from .llm import LLMResponse
from .models import AgentSpec

PLANS = {
    "PAY-482": {
        "criteria": [
            "Only the owner of a payment can refund it",
            "A refund request without an idempotency key is rejected",
            "Repeating a request with the same key returns the original refund and moves no money",
            "Refund amounts must be positive and cannot exceed the remaining refundable amount",
            "Refunding an unknown payment is an error",
        ],
        "steps": [
            "Validate the idempotency key and look up the payment",
            "Check the caller owns the payment",
            "Return the existing refund when the key was already used",
            "Validate the amount against the remaining balance, then record the refund",
        ],
    },
}

REFUND_WITHOUT_AUTHZ = '''import uuid

from .store import PaymentStore, Refund


def refund(
    store: PaymentStore,
    user_id: str,
    payment_id: str,
    amount_cents: int,
    idempotency_key: str,
) -> Refund:
    """Refund part or all of a payment. See the refund policy (DOC-REFUND-POLICY)."""
    if not idempotency_key:
        raise ValueError("idempotency_key is required")
    payment = store.get_payment(payment_id)
    existing = store.find_refund(idempotency_key)
    if existing is not None:
        return existing
    if not isinstance(amount_cents, int) or amount_cents <= 0:
        raise ValueError("amount_cents must be a positive integer")
    if amount_cents > payment.amount_cents - payment.refunded_cents:
        raise ValueError("amount exceeds the remaining refundable balance")
    result = Refund(
        id=f"re_{uuid.uuid4().hex[:8]}",
        payment_id=payment_id,
        amount_cents=amount_cents,
        idempotency_key=idempotency_key,
    )
    payment.refunded_cents += amount_cents
    store.save_refund(result)
    return result
'''

REFUND_WITH_AUTHZ = REFUND_WITHOUT_AUTHZ.replace(
    "    payment = store.get_payment(payment_id)\n",
    "    payment = store.get_payment(payment_id)\n"
    "    if payment.owner_id != user_id:\n"
    '        raise PermissionError("only the payment owner can refund it")\n',
)

MONEY_FIX = '''def format_amount(cents: int) -> str:
    """Format an integer number of cents as dollars, e.g. 1999 -> '$19.99'."""
    return f"${cents // 100}.{cents % 100:02d}"
'''

# ticket -> (file to change, implementation per attempt)
IMPLEMENTATIONS = {
    "PAY-482": ("payments/refunds.py", [REFUND_WITHOUT_AUTHZ, REFUND_WITH_AUTHZ]),
    "BUG-101": ("money.py", [MONEY_FIX]),
}


def _use(name: str, **args) -> dict:
    return {"type": "tool_use", "id": f"scripted_{uuid.uuid4().hex[:10]}", "name": name, "input": args}


def _results(messages: list[dict]) -> list:
    """Every tool result so far, parsed from JSON where possible."""
    parsed = []
    for message in messages:
        if message["role"] == "user" and isinstance(message["content"], list):
            for block in message["content"]:
                if block.get("type") == "tool_result":
                    try:
                        parsed.append(json.loads(block["content"]))
                    except (ValueError, TypeError):
                        parsed.append(block["content"])
    return parsed


def _find(results: list, key: str) -> dict | None:
    return next((r for r in reversed(results) if isinstance(r, dict) and key in r), None)


class ScriptedLLM:
    async def complete(self, *, agent: AgentSpec, messages, tools, meta) -> LLMResponse:
        step = sum(1 for m in messages if m["role"] == "assistant")
        handler = getattr(self, f"_{agent.name.lower()}")
        return LLMResponse(handler(step, messages, meta))

    def _dispatch(self, step, messages, meta):
        """Test double for triage: answers with the keyword rules."""
        from .triage import triage

        request = messages[0]["content"].split("Request:\n", 1)[-1]
        plan = triage(request, "project")
        return [_use("submit_triage", kind=plan.kind, agents=[{"name": p.agent, "reason": p.reason} for p in plan.draft.picks])]

    def _explore(self, step, messages, meta):
        """RADAR on a free-text request: really lists and reads the project, but cannot reason about it."""
        results = _results(messages)
        if step == 0:
            return [_use("jira__get_ticket", ticket_id=meta["ticket"])]
        if step == 1:
            return [_use("workspace__list_files")]
        listing = next((r for r in results if isinstance(r, str) and ".py" in r), "")
        files = listing.split()
        sources = [f for f in files if f.endswith(".py") and not f.startswith("tests/") and not f.endswith("__init__.py")][:4]
        if step == 2:
            return [_use("workspace__read_file", path=f) for f in sources]
        facts = [f"{f}: {len(files)} file(s) in the project" if i == 0 else f for i, f in enumerate(files[:12])]
        for text in (r for r in results if isinstance(r, str) and not r.startswith("{")):
            facts += [l.strip() for l in text.splitlines() if l.strip().startswith(("def ", "class ", '"""'))][:6]
        ticket = _find(results, "description") or {"description": meta["ticket"]}
        summary = (
            "Offline mode: I can list and read this project but cannot reason about it, so this is a map, not an answer to "
            f"\"{ticket['description'][:120]}\". Set ANTHROPIC_API_KEY for a real answer."
        )
        return [_use("submit_intel", summary=summary, key_facts=facts)]

    def _radar(self, step, messages, meta):
        if meta["ticket"] not in IMPLEMENTATIONS:
            return self._explore(step, messages, meta)
        results = _results(messages)
        ticket = _find(results, "linked_docs")
        if step == 0:
            return [_use("jira__get_ticket", ticket_id=meta["ticket"])]
        if step == 1 and ticket and ticket["linked_docs"]:
            return [_use("confluence__get_doc", doc_id=d) for d in ticket["linked_docs"]]
        facts = list(ticket["acceptance_criteria"]) if ticket else []
        for doc in (r for r in results if isinstance(r, dict) and "body" in r):
            facts += [line.split(". ", 1)[-1] for line in doc["body"].splitlines() if line.strip()]
        summary = f"{ticket['title']}. {ticket['description']}" if ticket else meta["ticket"]
        return [_use("submit_intel", summary=summary, key_facts=facts)]

    def _atlas(self, step, messages, meta):
        plan = PLANS.get(meta["ticket"], {"criteria": ["The change works as described in the ticket"], "steps": ["Implement the ticket"]})
        return [_use("submit_plan", **plan)]

    def _forge(self, step, messages, meta):
        path, attempts = IMPLEMENTATIONS[meta["ticket"]]
        source = attempts[min(meta["attempt"], len(attempts)) - 1]
        if step == 0:
            return [_use("workspace__read_file", path=path)]
        if step == 1:
            return [_use("workspace__write_file", path=path, content=source)]
        if step == 2:
            return [_use("workspace__run_tests")]
        return [_use("submit_work", summary=f"Implemented {path} (attempt {meta['attempt']}) and ran the test suite.")]

    def _warden(self, step, messages, meta):
        if step == 0:
            return [_use("workspace__run_tests")]
        run = _find(_results(messages), "exit_code") or {"passed": False, "output": ""}
        issues = [] if run["passed"] else [l for l in run["output"].splitlines() if l.startswith("FAILED")] or ["test suite failed"]
        return [_use("submit_verdict", passed=run["passed"], issues=issues)]

    def _aegis(self, step, messages, meta):
        if step == 0:
            return [_use("workspace__git_diff")]
        if step == 1:
            return [_use("workspace__security_scan")]
        scan = _find(_results(messages), "findings") or {"passed": False, "findings": []}
        issues = [f"{f['rule']} in {f['file']}:{f['line']}: {f['detail']}" for f in scan["findings"]]
        return [_use("submit_verdict", passed=scan["passed"], issues=issues)]
