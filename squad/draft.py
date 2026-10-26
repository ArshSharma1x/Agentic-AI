"""Agent select: decide which agents join the squad for a ticket, with a reason for every pick."""

from dataclasses import dataclass

from .models import Ticket

SENSITIVE_LABELS = {"security", "payments", "auth", "pii"}


@dataclass(frozen=True)
class Pick:
    agent: str
    reason: str


@dataclass(frozen=True)
class Draft:
    picks: tuple[Pick, ...]
    skipped: tuple[Pick, ...]

    @property
    def names(self) -> list[str]:
        return [p.agent for p in self.picks]


def draft(ticket: Ticket) -> Draft:
    picks: list[Pick] = [
        Pick("RADAR", "every match starts with intel"),
        Pick("FORGE", "someone has to write the code"),
        Pick("WARDEN", "nothing ships without a QA gate"),
    ]
    skipped: list[Pick] = []

    if not ticket.acceptance_criteria:
        picks.insert(1, Pick("ATLAS", "ticket has no acceptance criteria, so the squad needs a plan"))
    elif len(ticket.repos) > 1:
        picks.insert(1, Pick("ATLAS", f"work spans {len(ticket.repos)} repos, so it needs coordinating"))
    else:
        skipped.append(Pick("ATLAS", "acceptance criteria are already written and the scope is one repo"))

    sensitive = SENSITIVE_LABELS & set(ticket.labels)
    if sensitive:
        picks.append(Pick("AEGIS", f"ticket is labelled {', '.join(sorted(sensitive))}, so it gets a security gate"))
    else:
        skipped.append(Pick("AEGIS", "no security-sensitive labels"))

    return Draft(tuple(picks), tuple(skipped))
