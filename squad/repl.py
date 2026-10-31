"""The squad terminal: type a request, the right agents deploy, and the session remembers what happened."""

import asyncio
import dataclasses
import shutil
import sys
import time
from collections.abc import Callable
from pathlib import Path

from .agents import ROSTER
from .config import ConfigError, config_path, load_config
from .orchestrator import AUTONOMY_LEVELS, Match
from .paths import RUNS_DIR
from .projects import Project, overview
from .render import BOLD, DIM, RESET, ROLE_COLORS, render
from .triage import CHAT, triage_with_model
from .workspace import Workspace

HELP = f"""{BOLD}Just type what you need.{RESET} A dispatcher reads it and sends in only the agents the job needs.
  /squad          show the agents and what each does
  /autonomy [x]   show or set when you are asked: manual, semi (before a commit) or full (never)
  /diff           show every change the squad has made since the session began
  /apply          copy those changes into your real folder (asks first, skips files you edited meanwhile)
  /new            forget this session and start from a fresh copy of your folder
  /exit           leave (Ctrl+D also works)
Work happens in a copy of your folder, so nothing touches your files until you /apply."""
CONTEXT_TURNS = 4
JOBS = {
    "RADAR": "answers questions and gathers context (read-only)",
    "ATLAS": "plans the work and writes acceptance criteria",
    "FORGE": "writes and changes the code",
    "WARDEN": "runs the tests and checks the work meets the criteria",
    "AEGIS": "reviews for security problems",
}


async def ask_yes_no(question: str) -> bool:
    if not sys.stdin.isatty():
        print(f"(no terminal to ask: {question} -> no)")
        return False
    answer = await asyncio.to_thread(input, f"\n? {question} [y/N] ")
    return answer.strip().lower() in ("y", "yes")


class Session:
    def __init__(
        self, project: Project, llm, *, autonomy: str = "semi", runs_dir: Path = RUNS_DIR,
        out: Callable[[str], None] = print, ask=ask_yes_no,
    ) -> None:
        self.project, self.llm, self.autonomy, self.runs_dir = project, llm, autonomy, runs_dir
        self.out, self.ask = out, ask
        self.turns: list[tuple[str, str]] = []
        self.tokens = 0
        self._new_workspace()

    def _new_workspace(self) -> None:
        """A fresh working copy of the project. `source` is what gets copied; `target` is where /apply writes."""
        self.workspace = self.runs_dir / f"{time.strftime('%Y%m%d-%H%M%S')}-session" / "workspace"
        self.source = self.target = self.project.path
        self.turns.clear()

    def _start_new_project(self, destination: str) -> bool:
        """A request for a new folder elsewhere gets an empty workspace, not a copy of the current project."""
        dest = Path(destination).expanduser()
        home = Path.home().resolve()
        if not dest.is_absolute() or home not in (dest.resolve(), *dest.resolve().parents) or dest.resolve() == home:
            self.out(f"\nI only create new folders inside your home directory ({home}); {destination} is not.")
            return False
        base = self.runs_dir / f"{time.strftime('%Y%m%d-%H%M%S')}-new"
        (base / "empty").mkdir(parents=True)
        self.workspace, self.source, self.target = base / "workspace", base / "empty", dest
        return True

    def banner(self) -> str:
        try:
            status = "model connected" if load_config().api_key else f"no API key yet: add it to {config_path()}"
        except ConfigError as err:
            status = str(err)
        roster = "  ".join(f"{ROLE_COLORS[a.role.value]}{a.name}{RESET}" for a in ROSTER.values())
        return (
            f"\n{BOLD}SQUAD{RESET}  {DIM}working on{RESET} {self.project.name}  {DIM}| autonomy {self.autonomy} | {status}{RESET}\n"
            f"{roster}\n{DIM}Type a request, /help for commands.{RESET}"
        )

    def _context(self) -> str:
        return "\n".join(f"- You asked: {q}\n  Result: {a}" for q, a in self.turns[-CONTEXT_TURNS:])

    async def handle(self, line: str) -> bool:
        """One line of input. Returns False when the user is leaving."""
        line = line.strip()
        if not line:
            return True
        if line.startswith("/"):
            return await self._command(line)
        await self._request(line)
        return True

    async def _request(self, text: str) -> None:
        plan = await triage_with_model(
            text, self.project.name, self.llm, files=overview(self.project.path),
            history=self._context(), allow_chat=True,
        )
        if plan.kind == "chat":
            reply = await self.llm.complete(
                agent=CHAT, tools=[], meta={},
                messages=[{"role": "user", "content": (f"Earlier in this session:\n{self._context()}\n\n" if self.turns else "") + text}],
            )
            answer = "".join(b["text"] for b in reply.content if b["type"] == "text").strip()
            self.tokens += reply.input_tokens + reply.output_tokens
            self.out(f"\n{answer}")
            self.turns.append((text, answer[:200]))
            return
        ticket = plan.ticket
        if plan.destination:
            if not self._start_new_project(plan.destination):
                return
            ticket = dataclasses.replace(ticket, description=(
                f"{ticket.description}\n\nThis is a new project. The workspace root IS the new folder (it will be copied to "
                f"{plan.destination}), so put files directly in the root, not in a subfolder named after the project. "
                "Do not use absolute paths."))
        if self.turns:
            ticket = dataclasses.replace(ticket, description=f"{ticket.description}\n\nContext from earlier in this session:\n{self._context()}")
        match = Match(
            ticket.id, llm=self.llm, autonomy=self.autonomy, approve=self.ask, runs_dir=self.runs_dir,
            listeners=[lambda e: (line := render(e)) and self.out(line)],
            ticket=ticket, project=self.source, squad_draft=plan.draft, workspace=self.workspace,
        )
        result = await match.run()
        self.tokens += result.stats["input_tokens"] + result.stats["output_tokens"]
        self.turns.append((text, f"{result.reason}. {result.answer}"[:240]))
        if plan.destination:
            self.out(f"{DIM}New project is in the sandbox. Type /apply to create {self.target}{RESET}")

    async def _command(self, line: str) -> bool:
        name, _, arg = line[1:].partition(" ")
        arg = arg.strip()
        if name in ("exit", "quit", "q"):
            return False
        if name == "help":
            self.out(HELP)
        elif name == "squad":
            for agent in ROSTER.values():
                self.out(f"  {ROLE_COLORS[agent.role.value]}{BOLD}{agent.name:<7}{RESET} {agent.role.value:<10} {DIM}{JOBS[agent.name]}{RESET}")
        elif name == "autonomy":
            if not arg:
                self.out(f"autonomy is {self.autonomy} (manual, semi, full)")
            elif arg in AUTONOMY_LEVELS:
                self.autonomy = arg
                self.out(f"autonomy set to {arg}")
            else:
                self.out(f"choose one of: {', '.join(AUTONOMY_LEVELS)}")
        elif name == "diff":
            self.out(Workspace(self.workspace).baseline_diff() if self.workspace.exists() else "(no changes yet)")
        elif name == "apply":
            await self._apply()
        elif name == "new":
            self._new_workspace()
            self.out("fresh session: the next request starts from a new copy of your folder")
        else:
            self.out(f"unknown command /{name}; try /help")
        return True

    async def _apply(self) -> None:
        if not self.workspace.exists():
            return self.out("nothing to apply yet")
        ws, source = Workspace(self.workspace), self.target
        todo, skipped = [], []
        for status, rel in ws.changes():
            target = source / rel
            try:
                base = ws.baseline_file(rel)
                current = target.read_text() if target.exists() else None
                clean = current == base  # the file is exactly as the squad found it (None means absent both times)
            except (UnicodeDecodeError, OSError):
                clean = False
            (todo if clean else skipped).append((status, rel))
        for status, rel in skipped:
            self.out(f"  skipped {rel}: it changed in your folder since the session began")
        if not todo:
            return self.out("nothing to apply")
        for status, rel in todo:
            self.out(f"  {status} {rel}")
        if not await self.ask(f"Copy {len(todo)} file(s) into {source}?"):
            return self.out("not applied")
        for status, rel in todo:
            if status == "D":
                (source / rel).unlink(missing_ok=True)
            else:
                (source / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(self.workspace / rel, source / rel)
        self.out(f"applied {len(todo)} file(s)")


def run_repl(session: Session) -> int:
    try:
        import readline  # noqa: F401  (line editing and history for input())
    except ImportError:
        pass
    session.out(session.banner())
    while True:
        try:
            line = input(f"\n{BOLD}squad ›{RESET} ")
        except EOFError:
            break
        except KeyboardInterrupt:
            session.out("\n(Ctrl+D or /exit to leave)")
            continue
        try:
            if not asyncio.run(session.handle(line)):
                break
        except KeyboardInterrupt:
            session.out(f"\n{DIM}interrupted{RESET}")
        except Exception as err:  # a failed turn should not end the session
            session.out(f"\nsomething went wrong: {err}")
    session.out(f"{DIM}session tokens: {session.tokens}{RESET}")
    return 0
