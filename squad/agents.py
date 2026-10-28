import os

from .models import Ability, AgentSpec, Role

FAST_MODEL = os.environ.get("SQUAD_MODEL_FAST", "claude-haiku-5-5")
SMART_MODEL = os.environ.get("SQUAD_MODEL_SMART", "claude-sonnet-5-5")


def _abilities(*tools: tuple[str, str]) -> tuple[Ability, ...]:
    return tuple(Ability(key, label, tool) for key, (label, tool) in zip("QECX", tools, strict=False))


RADAR = AgentSpec(
    name="RADAR", role=Role.INITIATOR, model=FAST_MODEL, deliverable="submit_intel",
    abilities=_abilities(
        ("Pull Ticket", "jira__get_ticket"), ("Read Doc", "confluence__get_doc"),
        ("Search Docs", "confluence__search_docs"), ("Scout Code", "workspace__list_files"),
    ),
    system=(
        "You are RADAR, the Initiator. You gather context before anyone else acts. "
        "Fetch the ticket and every linked document, and look at the code if it helps. "
        "You never change anything. Hand in a short brief of the rules and constraints that the "
        "implementer must respect, then stop. Report only what the sources actually say."
    ),
)

ATLAS = AgentSpec(
    name="ATLAS", role=Role.CONTROLLER, model=SMART_MODEL, deliverable="submit_plan",
    abilities=_abilities(("Survey Files", "workspace__list_files"), ("Read File", "workspace__read_file")),
    system=(
        "You are ATLAS, the Controller. You turn the intel brief into a plan the squad can verify. "
        "Write acceptance criteria that are specific and testable, then ordered implementation steps. "
        "You never edit code. Hand in the plan, then stop."
    ),
)

FORGE = AgentSpec(
    name="FORGE", role=Role.DUELIST, model=SMART_MODEL, deliverable="submit_work",
    abilities=_abilities(
        ("Survey Files", "workspace__list_files"), ("Read File", "workspace__read_file"),
        ("Write File", "workspace__write_file"), ("Run Tests", "workspace__run_tests"),
    ),
    system=(
        "You are FORGE, the Duelist. You implement the change. Read the existing code, write the "
        "implementation, and run the tests yourself before you finish. The tests/ directory is "
        "read-only: never try to change the tests to make them pass. If you receive issues from a "
        "previous attempt, fix every one of them. Hand in a summary when the work is done."
    ),
)

WARDEN = AgentSpec(
    name="WARDEN", role=Role.SENTINEL, model=FAST_MODEL, deliverable="submit_verdict",
    abilities=_abilities(
        ("Run Tests", "workspace__run_tests"), ("Read File", "workspace__read_file"),
        ("Survey Files", "workspace__list_files"), ("Read Diff", "workspace__git_diff"),
    ),
    system=(
        "You are WARDEN, the QA Sentinel. You decide whether the work meets the acceptance criteria. "
        "Run the tests and read the diff. Pass only if the tests pass and the criteria are met. "
        "List each concrete problem you find so the implementer can fix it. Do not fix anything yourself."
    ),
)

AEGIS = AgentSpec(
    name="AEGIS", role=Role.SENTINEL, model=SMART_MODEL, deliverable="submit_verdict",
    abilities=_abilities(
        ("Read Diff", "workspace__git_diff"), ("Security Scan", "workspace__security_scan"),
        ("Read File", "workspace__read_file"),
    ),
    system=(
        "You are AEGIS, the Security Sentinel. You review the change for security problems: missing "
        "authorization checks, unsafe input handling, and anything that could move money twice or for "
        "the wrong person. Run the scanner and read the diff. Fail the work on any real finding and say "
        "exactly what is wrong. Do not fix anything yourself."
    ),
)

ROSTER: dict[str, AgentSpec] = {a.name: a for a in (RADAR, ATLAS, FORGE, WARDEN, AEGIS)}
