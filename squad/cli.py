import argparse
import asyncio
import os
import sys
from pathlib import Path

from .llm import describe, llm_from_config, no_model_message
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
        sys.exit(no_model_message())
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


def _author():
    from .agents import SMART_MODEL
    from .authors import author_from_config

    return author_from_config(SMART_MODEL)


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
        sys.exit(no_model_message())
    plan = asyncio.run(triage_with_model(args.prompt, name, llm, files=overview(projects[name].path)))
    match = Match(
        plan.ticket.id, llm=llm, autonomy=args.autonomy, approve=_ask, listeners=[_print_event],
        ticket=plan.ticket, project=projects[name].path, squad_draft=plan.draft, author=_author(),
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
        sys.exit(no_model_message())
    from .agents import SMART_MODEL
    from .authors import author_from_config

    return run_repl(Session(projects[name], llm, autonomy=args.autonomy, author=author_from_config(SMART_MODEL)))


def _web(args, projects) -> int:
    import threading
    import webbrowser

    import uvicorn

    from .server import create_app

    url = f"http://127.0.0.1:{args.port}"
    try:
        llm = llm_from_config()
        status = f"model: {describe(llm)}" if llm else no_model_message()
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


def _verify(args) -> int:
    import json

    from . import evidence
    from .gate import FAIL, PASS
    from .policy import PolicyError
    from .verify import VerifyError, verify

    try:
        result = verify(Path(args.repo), base=args.base, head=args.head, hidden=Path(args.hidden) if args.hidden else None,
                        network="loopback" if args.loopback else None, approve_test_changes=args.approve_test_changes)
    except (VerifyError, PolicyError) as err:
        print(f"agentic verify: {err}", file=sys.stderr)
        return 3
    report = result.report
    if args.json:
        Path(args.json).write_text(json.dumps(result.to_dict(), indent=2))
    if args.evidence:
        evidence.write(args.evidence, evidence.statement(result, args.subject or f"git+file://{result.repo}"))
    if args.predicate:
        evidence.write(args.predicate, evidence.predicate(result))
    if args.summary_md:
        with open(args.summary_md, "a") as out:
            out.write(evidence.summary_markdown(result))
    if not args.quiet:
        print(f"Verifying {result.head_label} against {result.base_label} ({result.base[:10]}), {len(result.changes)} file(s) changed")
        print(render({"type": "gate", "t": 0.0, "agent": "WARDEN", **report.to_dict()}))
    return {PASS: 0, FAIL: 1}.get(report.verdict, 2)


def _eval(args) -> int:
    import json
    from dataclasses import asdict

    from .bench import load_tasks, metrics, report_markdown, run_all

    tasks = [t for t in load_tasks() if not args.only or t.name in args.only]
    print(f"Running {len(tasks)} task(s) x {args.seeds} seed(s) with Claude Code ({args.model}), {args.jobs} at a time")
    runs = asyncio.run(run_all(tasks, model=args.model, seeds=args.seeds, jobs=args.jobs))
    m = metrics(runs)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(json.dumps({"model": args.model, "metrics": m, "runs": [asdict(r) for r in runs]}, indent=2))
    (out / "README.md").write_text(report_markdown(runs, m, args.model))
    print(json.dumps(m, indent=2))
    print(f"report: {out / 'README.md'}")
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

    ver = sub.add_parser("verify", help="gate a change made by any agent: original tests, tamper checks, sandboxed; exit 0 PASS, 1 FAIL, 2 UNVERIFIED")
    ver.add_argument("--base", help="commit to compare against (default: HEAD if you have uncommitted changes, else where the branch left main)")
    ver.add_argument("--head", help="commit to verify instead of the working tree")
    ver.add_argument("--hidden", help="folder of hidden tests the author never saw")
    ver.add_argument("--json", help="write the full report to this file")
    ver.add_argument("--evidence", help="write an in-toto attestation statement of this verification to this file")
    ver.add_argument("--predicate", help="write only the attestation predicate (for actions/attest) to this file")
    ver.add_argument("--subject", help="subject name for the attestation (default: the repo path)")
    ver.add_argument("--summary-md", help="append a markdown summary to this file (e.g. $GITHUB_STEP_SUMMARY)")
    ver.add_argument("--approve-test-changes", metavar="WHO", help="a human approved this change's edits to existing tests; recorded in the evidence")
    ver.add_argument("--loopback", action="store_true", help="let tests use localhost (never the internet); for suites that start local servers")
    ver.add_argument("--repo", default=".", help="repository to verify (default: current folder)")
    ver.add_argument("-q", "--quiet", action="store_true")
    ver.set_defaults(handler=_verify)

    ui = sub.add_parser("ui", help="write a standalone HTML replay of a trace")
    ui.add_argument("trace", help="path to a trace.jsonl file")
    ui.add_argument("-o", "--output", help="output file (default: replay.html next to the trace)")
    ui.add_argument("--open", action="store_true", help="open the replay in the browser")
    ui.set_defaults(handler=_ui)

    ev = sub.add_parser("eval", help="live eval: Claude Code on seeded tasks (incl. impossible ones); do its 'done' claims survive the gate?")
    ev.add_argument("--model", default="claude-sonnet-5-5")
    ev.add_argument("--seeds", type=int, default=1)
    ev.add_argument("--jobs", type=int, default=3)
    ev.add_argument("--only", nargs="*", help="task names to run (default: all)")
    ev.add_argument("--out", default="docs/eval", help="folder for results.json and README.md")
    ev.set_defaults(handler=_eval)

    argv = sys.argv[1:] if argv is None else argv
    if not argv or (argv[0].startswith("-") and argv[0] not in ("-h", "--help")):
        argv = ["start", *argv]  # bare `agentic`, or `agentic --autonomy full`, opens the terminal
    args = parser.parse_args(argv)
    return args.handler(args)
