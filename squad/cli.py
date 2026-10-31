import argparse
import asyncio
import os
import sys
from pathlib import Path

from .evals import format_report, run_eval
from .llm import AnthropicLLM, llm_from_config
from .mcp_host import ToolCallError
from .config import ConfigError, config_path, load_config
from .projects import discover, overview
from .repl import Session, ask_yes_no as _ask, run_repl
from .triage import triage_with_model
from .orchestrator import AUTONOMY_LEVELS, Match
from .render import render
from .scripted import ScriptedLLM
from .trace import Trace
from .ui import write_replay


def _print_event(event: dict) -> None:
    line = render(event)
    if line:
        print(line, flush=True)


def _pick_llm(choice: str):
    """For the dev tools (`run`, `eval`): the scripted model unless a key is configured and asked for."""
    llm = llm_from_config() if choice != "scripted" else None
    if choice == "anthropic" and llm is None:
        sys.exit(f"No API key yet: copy squad.config.example.json to {config_path()} and add your key.")
    if llm:
        return llm
    if choice == "auto" and not _pick_llm.warned:
        _pick_llm.warned = True
        print("No API key configured: using the scripted model (real tools, canned decisions).")
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
    projects = discover([Path(p) for p in args.project], cwd=Path.cwd(), demo=args.demo)
    name = args.on or next(iter(projects))
    if name not in projects:
        sys.exit(f"unknown project {name!r}; choose one of: {', '.join(projects)}")
    try:
        llm = llm_from_config()
    except ConfigError as err:
        sys.exit(str(err))
    if llm is None:
        sys.exit(f"No API key yet: copy squad.config.example.json to {config_path()} and add your key.")
    plan = asyncio.run(triage_with_model(args.prompt, name, llm, files=overview(projects[name].path)))
    match = Match(
        plan.ticket.id, llm=llm, autonomy=args.autonomy, approve=_ask, listeners=[_print_event],
        ticket=plan.ticket, project=projects[name].path, squad_draft=plan.draft,
    )
    result = asyncio.run(match.run())
    print(result.trace_path)
    return 0 if result.success else 1


def _start(args) -> int:
    projects = discover([Path(p) for p in args.project], cwd=Path.cwd(), demo=args.demo)
    if args.web:
        return _web(args, projects)
    name = args.on or next(iter(projects))
    if name not in projects:
        sys.exit(f"unknown project {name!r}; choose one of: {', '.join(projects)}")
    try:
        llm = llm_from_config()
    except ConfigError as err:
        sys.exit(str(err))
    if llm is None:
        sys.exit(f"No API key yet: copy squad.config.example.json to {config_path()} and add your key.")
    return run_repl(Session(projects[name], llm, autonomy=args.autonomy))


def _web(args, projects) -> int:
    import threading
    import webbrowser

    import uvicorn

    from .server import create_app

    url = f"http://127.0.0.1:{args.port}"
    try:
        status = "model connected" if load_config().api_key else f"no API key yet: add it to {config_path()}"
    except ConfigError as err:
        status = str(err)
    print(f"Squad is live at {url}  (Ctrl+C to stop)\nWorking on: {', '.join(projects)}  |  {status}")
    if not args.no_open:
        threading.Timer(1.0, webbrowser.open, [url]).start()
    uvicorn.run(create_app(projects), host="127.0.0.1", port=args.port, log_level="warning")
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
    sub = parser.add_subparsers(dest="command")

    run = sub.add_parser("run", help="dev tool: play a match on a bundled demo ticket (scripted model by default)")
    run.add_argument("ticket", help="ticket id, e.g. PAY-482")
    run.add_argument("--llm", choices=("auto", "scripted", "anthropic"), default="scripted")
    run.add_argument("--autonomy", choices=AUTONOMY_LEVELS, default="semi")
    run.add_argument("--max-retries", type=int, default=2)
    run.set_defaults(handler=_run)

    replay = sub.add_parser("replay", help="replay a saved match trace")
    replay.add_argument("trace", help="path to a trace.jsonl file")
    replay.set_defaults(handler=_replay)

    start = sub.add_parser("start", help="open the squad terminal: type a request, the right agents deploy (default command)")
    start.add_argument("--on", help="project to work on (default: the folder you are in)")
    start.add_argument("--autonomy", choices=AUTONOMY_LEVELS, default="semi")
    start.add_argument("--web", action="store_true", help="use the browser app instead of the terminal")
    start.add_argument("--port", type=int, default=8765, help="port for --web")
    start.add_argument("--project", action="append", default=[], help="add your own project folder (copied, never edited in place)")
    start.add_argument("--demo", action="store_true", help="also offer the bundled demo projects")
    start.add_argument("--no-open", action="store_true", help="with --web: do not open the browser")
    start.set_defaults(handler=_start)

    ask = sub.add_parser("ask", help="give the squad a problem in plain words; it sizes the squad itself")
    ask.add_argument("prompt")
    ask.add_argument("--on", help="project to work on (default: the folder you are in)")
    ask.add_argument("--project", action="append", default=[], help="add your own project folder (copied, never edited in place)")
    ask.add_argument("--demo", action="store_true", help="also offer the bundled demo projects")
    ask.add_argument("--autonomy", choices=AUTONOMY_LEVELS, default="semi")
    ask.set_defaults(handler=_ask_cmd)

    ui = sub.add_parser("ui", help="write a standalone HTML replay of a trace")
    ui.add_argument("trace", help="path to a trace.jsonl file")
    ui.add_argument("-o", "--output", help="output file (default: replay.html next to the trace)")
    ui.add_argument("--open", action="store_true", help="open the replay in the browser")
    ui.set_defaults(handler=_ui)

    ev = sub.add_parser("eval", help="dev tool: compare the squad with a solo baseline on the demo tickets (scripted model by default)")
    ev.add_argument("tickets", nargs="*", default=["PAY-482", "BUG-101"], help="ticket ids (default: all demo tickets)")
    ev.add_argument("--llm", choices=("auto", "scripted", "anthropic"), default="scripted")
    ev.set_defaults(handler=_eval)

    args = parser.parse_args(argv)
    if args.command is None:  # bare `squad` opens the terminal
        args = parser.parse_args(["start"])
    return args.handler(args)
