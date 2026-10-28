import asyncio

from squad.evals import format_report, run_eval
from squad.scripted import ScriptedLLM


def test_solo_ships_the_unauthorized_refund_and_the_squad_does_not():
    rows = {(r.ticket, r.mode): r for r in asyncio.run(run_eval(["PAY-482"], llm_factory=ScriptedLLM))}
    assert rows["PAY-482", "solo"].success and rows["PAY-482", "solo"].findings
    assert rows["PAY-482", "squad"].success and not rows["PAY-482", "squad"].findings
    assert "Solo shipped 1" in format_report(list(rows.values()))
