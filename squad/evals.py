"""Eval: does the squad ship better work than a solo coder + tester? Both are audited the same way afterwards."""

import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .llm import LLM
from .orchestrator import Match
from .workspace import Workspace

SOLO = ["FORGE", "WARDEN"]


@dataclass
class EvalRow:
    ticket: str
    mode: str
    success: bool
    attempts: int
    model_calls: int
    tokens: int
    findings: list[str]  # from an independent scan of the finished workspace, whatever the squad concluded


async def run_eval(tickets: list[str], *, llm_factory: Callable[[], LLM]) -> list[EvalRow]:
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        for ticket in tickets:
            for mode, squad in (("squad", None), ("solo", SOLO)):
                runs_dir = Path(tmp) / mode
                result = await Match(ticket, llm=llm_factory(), autonomy="full", runs_dir=runs_dir, squad=squad).run()
                scan = Workspace(Path(result.run_dir) / "workspace").security_scan()
                findings = [f"{f['rule']} in {f['file']}" for f in scan["findings"]]
                s = result.stats
                rows.append(EvalRow(ticket, mode, result.success, result.attempts, s["model_calls"],
                                    s["input_tokens"] + s["output_tokens"], findings))
    return rows


def format_report(rows: list[EvalRow]) -> str:
    head = f"{'ticket':<9}{'mode':<7}{'shipped':<9}{'attempts':<10}{'model calls':<13}{'tokens':<8}audit of shipped code"
    lines = [head, "-" * len(head)]
    for r in rows:
        audit = "; ".join(r.findings) if r.findings else "clean"
        lines.append(f"{r.ticket:<9}{r.mode:<7}{'yes' if r.success else 'no':<9}{r.attempts:<10}{r.model_calls:<13}{r.tokens:<8}{audit}")
    insecure = [r for r in rows if r.mode == "solo" and r.success and r.findings]
    lines.append("")
    lines.append(f"Solo shipped {len(insecure)} change(s) that the independent audit flags; the squad shipped "
                 f"{len([r for r in rows if r.mode == 'squad' and r.success and r.findings])}.")
    return "\n".join(lines)
