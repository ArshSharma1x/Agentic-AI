import argparse
import asyncio
import os
import sys
from pathlib import Path

from .evals import format_report, run_eval
from .llm import AnthropicLLM
from .mcp_host import ToolCallError
from .projects import discover
from .triage import offline_blocker, triage
from .orchestrator import AUTONOMY_LEVELS, Match
from .render import render
from .scripted import ScriptedLLM
from .trace import Trace
from .ui import write_replay


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


def _ask_cmd(args) -> int:
    projects = discover([Path(p) for p in args.project])
    if args.on not in projects:
        sys.exit(f"unknown project {args.on!r}; choose one of: {', '.join(projects)}")
    agents = [a.strip().upper() for a in args.agents.split(",")] if args.agents else None
    try:
        plan = triage(args.prompt, args.on, agents=agents)
    except ValueError as err:
        sys.exit(str(err))
    llm = _pick_llm(args.llm)
    blocker = offline_blocker(plan.draft.names, plan.ticket.id, scripted=isinstance(llm, ScriptedLLM))
    if blocker:
        sys.exit(blocker)
    match = Match(
        plan.ticket.id, llm=llm, autonomy=args.autonomy, approve=_ask, max_retries=2, listeners=[_print_event],
        ticket=plan.ticket, project=projects[args.on].path, squad_draft=plan.draft,
    )
    result = asyncio.run(match.run())
    print(result.trace_path)
    return 0 if result.success else 1


def _start(args) -> int:
    import threading
    import webbrowser

    import uvicorn

    from .server import create_app

    projects = discover([Path(p) for p in args.project])
    llm = _pick_llm(args.llm)
    url = f"http://127.0.0.1:{args.port}"
    print(f"Squad is live at {url}  (Ctrl+C to stop). Projects: {', '.join(projects)}")
    if not args.no_open:
        threading.Timer(1.0, webbrowser.open, [url]).start()
    uvicorn.run(create_app(projects, llm), host="127.0.0.1", port=args.port, log_level="warning")
    return 0


def _ui(args) -> int:
    path = Path(args.trace)
    if not path.is_file():
        sys.exit(f"no such trace file: {path}")
    out = write_replay(path, Path(args.output) if args.output else path.with_name("replay.html"))
    print(out)
    if args.open:
        import webbrowser
        webbrowser.open(out.resolve().as_uri())
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

    start = sub.add_parser("start", help="open the squad app in your browser: type a problem, watch the squad work")
    start.add_argument("--port", type=int, default=8765)
    start.add_argument("--project", action="append", default=[], help="add your own project folder (copied, never edited in place)")
    start.add_argument("--llm", choices=("auto", "scripted", "anthropic"), default="auto")
    start.add_argument("--no-open", action="store_true", help="do not open the browser")
    start.set_defaults(handler=_start)

    ask = sub.add_parser("ask", help="give the squad a problem in plain words; it sizes the squad itself")
    ask.add_argument("prompt")
    ask.add_argument("--on", default="refunds_api", help="project to work on (default: refunds_api)")
    ask.add_argument("--project", action="append", default=[], help="add your own project folder (copied, never edited in place)")
    ask.add_argument("--agents", help="override the squad, e.g. RADAR,AEGIS")
    ask.add_argument("--llm", choices=("auto", "scripted", "anthropic"), default="auto")
    ask.add_argument("--autonomy", choices=AUTONOMY_LEVELS, default="semi")
    ask.set_defaults(handler=_ask_cmd)

    ui = sub.add_parser("ui", help="write a standalone HTML replay of a trace")
    ui.add_argument("trace", help="path to a trace.jsonl file")
    ui.add_argument("-o", "--output", help="output file (default: replay.html next to the trace)")
    ui.add_argument("--open", action="store_true", help="open the replay in the browser")
    ui.set_defaults(handler=_ui)

    ev = sub.add_parser("eval", help="compare the full squad with a solo FORGE + WARDEN baseline")
    ev.add_argument("tickets", nargs="*", default=["PAY-482", "BUG-101"], help="ticket ids (default: all demo tickets)")
    ev.add_argument("--llm", choices=("auto", "scripted", "anthropic"), default="auto")
    ev.set_defaults(handler=_eval)

    args = parser.parse_args(argv)
    return args.handler(args)
