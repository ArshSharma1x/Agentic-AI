"""Builds the task prompt each agent receives from what is on the blackboard."""

from .models import Ticket


def _bullets(items) -> str:
    return "\n".join(f"- {i}" for i in items) or "- (none)"


def build_prompt(agent: str, ticket: Ticket, board: dict, attempt: int, feedback: list[str]) -> str:
    header = f"Ticket {ticket.id}: {ticket.title}\n{ticket.description}\n"
    intel, plan = board.get("intel"), board.get("plan")

    if agent == "RADAR":
        docs = ", ".join(ticket.linked_docs) or "none"
        if ticket.type == "question":
            return (
                f"{header}\nAnswer this from the code and docs in the workspace; read what you need. Put the answer in "
                "the summary and the evidence (files, functions) in key_facts, then call submit_intel."
            )
        return f"{header}\nLinked docs: {docs}\nGather the context the squad needs, then call submit_intel."

    if agent == "ATLAS":
        return (
            f"{header}\nIntel brief:\n{intel['summary']}\n{_bullets(intel['key_facts'])}\n\n"
            "Write the acceptance criteria and implementation steps, then call submit_plan."
        )

    if agent == "FORGE":
        parts = [header]
        if intel:
            parts.append(f"Intel brief:\n{intel['summary']}\n{_bullets(intel['key_facts'])}\n")
        if plan:
            parts.append(f"Acceptance criteria:\n{_bullets(plan['criteria'])}\n")
            if plan.get("steps"):
                parts.append(f"Plan:\n{_bullets(plan['steps'])}\n")
        if feedback:
            parts.append(f"Attempt {attempt}. The Sentinels rejected your last attempt:\n{_bullets(feedback)}\n")
        parts.append("Implement the change, run the tests, then call submit_work.")
        return "\n".join(parts)

    # Sentinels
    work = board.get("work")
    if not work:
        return (
            f"{header}\nNothing has been changed. Review the code in the workspace as it stands against the request, "
            "then call submit_verdict. Fail it only for real problems, and name each one."
        )
    return (
        f"{header}\nAcceptance criteria:\n{_bullets(plan['criteria'])}\n\n"
        f"Implementer's summary: {work.get('summary', '(none)')}\n"
        f"Review attempt {attempt}. Check the work, then call submit_verdict."
    )

