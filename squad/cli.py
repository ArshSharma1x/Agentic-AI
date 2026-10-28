import argparse
import asyncio
import os
import sys
from pathlib import Path

from .evals import format_report, run_eval
from .llm import AnthropicLLM
from .mcp_host import ToolCallError
from .orchestrator import AUTONOMY_LEVELS, Match
from .render import render
from .scripted import ScriptedLLM
from .trace import Trace


def _print_event(event: dict) -> None:
    line = render(event)
    if line:
        print(line, flush=True)


async def _ask(question: str) -> bool:
    if not sys.stdin.isatty():
        print(f"(no terminal to ask: {question} -> no)")
        return False
    answer = await asyncio.to_thread(input, f"\n? {question} [y/N] ")
    return answer.strip().lower() in ("y", "yes")


def _pick_llm(choice: str):
    has_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    if choice == "anthropic" or (choice == "auto" and has_key):
        if not has_key:
            sys.exit("ANTHROPIC_API_KEY is not set")
        return AnthropicLLM()
    if choice == "auto" and not _pick_llm.warned:
        _pick_llm.warned = True
        print("No ANTHROPIC_API_KEY found: using the scripted model (real tools, canned decisions).")
    return ScriptedLLM()


_pick_llm.warned = False


def _run(args) -> int:
    match = Match(
        args.ticket, llm=_pick_llm(args.llm), autonomy=args.autonomy, approve=_ask,
        max_retries=args.max_retries, listeners=[_print_event],
    )
    try:
        result = asyncio.run(match.run())
    except ToolCallError as err:
        sys.exit(f"could not start the match: {err}")
    print(f"{result.trace_path}")
    return 0 if result.success else 1


def _replay(args) -> int:
    path = Path(args.trace)
    if not path.is_file():
        sys.exit(f"no such trace file: {path}")
    for event in Trace.load(path):
        _print_event(event)
    return 0


def _eval(args) -> int:
    rows = asyncio.run(run_eval(args.tickets, llm_factory=lambda: _pick_llm(args.llm)))
    print(format_report(rows))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="squad", description="Run a squad of agents on a ticket.")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="play a match on a ticket")
    run.add_argument("ticket", help="ticket id, e.g. PAY-482")
    run.add_argument("--llm", choices=("auto", "scripted", "anthropic"), default="auto")
    run.add_argument("--autonomy", choices=AUTONOMY_LEVELS, default="semi")
    run.add_argument("--max-retries", type=int, default=2)
    run.set_defaults(handler=_run)

    replay = sub.add_parser("replay", help="replay a saved match trace")
    replay.add_argument("trace", help="path to a trace.jsonl file")
    replay.set_defaults(handler=_replay)

    ev = sub.add_parser("eval", help="compare the full squad with a solo FORGE + WARDEN baseline")
    ev.add_argument("tickets", nargs="*", default=["PAY-482", "BUG-101"], help="ticket ids (default: all demo tickets)")
    ev.add_argument("--llm", choices=("auto", "scripted", "anthropic"), default="auto")
    ev.set_defaults(handler=_eval)

    args = parser.parse_args(argv)
    return args.handler(args)
