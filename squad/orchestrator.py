"""The match: draft a squad, then run intel, plan, execute and verify with retries, then commit."""

import asyncio
import json
import os
import shutil
import sys
import time
from collections.abc import Awaitable, Callable
from pathlib import Path

from mcp import StdioServerParameters

from .agents import ROSTER
from .blackboard import Blackboard
from .draft import draft
from .llm import LLM
from .mcp_host import MCPHost
from .models import AgentRun, MatchResult, Ticket
from .paths import RUNS_DIR, SANDBOX_DIR
from .prompts import build_prompt
from .runner import AgentError, run_agent
from .trace import Trace
from .workspace import Workspace

AUTONOMY_LEVELS = ("manual", "semi", "full")
Approver = Callable[[str], Awaitable[bool]]


def server_params(name: str, **env: str) -> StdioServerParameters:
    return StdioServerParameters(
        command=sys.executable, args=["-m", f"squad.servers.{name}"], env={**os.environ, **env}
    )


class Match:
    """Autonomy decides when a human is asked: manual before every phase, semi before the commit, full never."""

    def __init__(
        self, ticket_id: str, *, llm: LLM, autonomy: str = "semi", approve: Approver | None = None,
        runs_dir: Path = RUNS_DIR, max_retries: int = 2, listeners=(),
        squad: list[str] | None = None,
    ) -> None:
        if autonomy not in AUTONOMY_LEVELS:
            raise ValueError(f"autonomy must be one of {AUTONOMY_LEVELS}")
        self.ticket_id, self.llm, self.autonomy = ticket_id, llm, autonomy
        self.approve, self.runs_dir, self.max_retries = approve, runs_dir, max_retries
        self.listeners = list(listeners)
        self.squad_override = squad  # skips the draft: used for the solo baseline in evals
        self.runs: list[AgentRun] = []

    async def run(self) -> MatchResult:
        started = time.monotonic()
        failure = None
        async with MCPHost() as host:
            try:
                result = await self._run(host, started)
            except Exception as err:
                # Re-raised below, after the servers shut down: errors that escape the MCP
                # client's context manager come out wrapped in an ExceptionGroup.
                failure = err
        if failure:
            raise failure
        return result

    async def _run(self, host: MCPHost, started: float) -> MatchResult:
        await host.connect("jira", server_params("jira"))
        await host.connect("confluence", server_params("confluence"))
        ticket = Ticket.from_dict(json.loads(await host.call("jira__get_ticket", {"ticket_id": self.ticket_id})))

        run_dir = self.runs_dir / f"{time.strftime('%Y%m%d-%H%M%S')}-{ticket.id}"
        workspace_dir = run_dir / "workspace"
        run_dir.mkdir(parents=True)
        shutil.copytree(SANDBOX_DIR / ticket.sandbox, workspace_dir, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
        Workspace(workspace_dir).init_repo()
        await host.connect("workspace", server_params("workspace", SQUAD_WORKSPACE=str(workspace_dir)))

        trace = Trace(run_dir / "trace.jsonl")
        trace.listeners.extend(self.listeners)
        trace.emit("match_start", ticket=ticket.id, title=ticket.title, autonomy=self.autonomy, llm=type(self.llm).__name__)
        squad = draft(ticket)
        names = self.squad_override or squad.names
        if self.squad_override:
            trace.emit("draft", picks=[{"agent": n, "reason": "fixed squad (no draft)"} for n in names], skipped=[])
        else:
            trace.emit(
                "draft",
                picks=[{"agent": p.agent, "reason": p.reason} for p in squad.picks],
                skipped=[{"agent": p.agent, "reason": p.reason} for p in squad.skipped],
            )

        board = Blackboard(trace)
        attempts, commit, success, reason = 0, None, False, ""
        try:
            attempts, success, reason = await self._play(ticket, names, host, board, trace)
            if success:
                if await self._gate(trace, f"Commit the changes for {ticket.id}?", commit=True):
                    commit = await host.call("workspace__git_commit", {"message": f"{ticket.id}: {ticket.title}"})
                    trace.emit("commit", sha=commit)
                    reason = "verified and committed"
                else:
                    reason = "verified, but the commit was not approved (changes are left in the workspace)"
        except AgentError as err:
            success, reason = False, str(err)

        stats = self._stats(started, attempts)
        trace.emit("match_end", success=success, reason=reason, attempts=attempts, commit=commit, **stats)
        return MatchResult(
            success=success, ticket_id=ticket.id, squad=names, attempts=attempts, commit=commit,
            reason=reason, run_dir=str(run_dir), trace_path=str(trace.path), stats=stats,
        )

    async def _play(self, ticket, squad, host, board, trace) -> tuple[int, bool, str]:
        if not await self._gate(trace, "Start the intel phase?", phase=True):
            return 0, False, "stopped before intel"
        if "RADAR" in squad:
            trace.emit("phase", name="intel")
            board.write("intel", (await self._agent("RADAR", ticket, board, host, trace, "intel", 1, [])).deliverable, "RADAR")

        if "ATLAS" in squad:
            if not await self._gate(trace, "Start the plan phase?", phase=True):
                return 0, False, "stopped before plan"
            trace.emit("phase", name="plan")
            board.write("plan", (await self._agent("ATLAS", ticket, board, host, trace, "plan", 1, [])).deliverable, "ATLAS")
        else:
            board.write("plan", {"criteria": list(ticket.acceptance_criteria), "steps": []}, "ticket")

        sentinels = [n for n in squad if ROSTER[n].role.value == "Sentinel"]
        feedback: list[str] = []
        for attempt in range(1, self.max_retries + 2):
            if not await self._gate(trace, f"Start execute attempt {attempt}?", phase=True):
                return attempt - 1, False, "stopped before execute"
            trace.emit("phase", name="execute", attempt=attempt)
            board.write("work", (await self._agent("FORGE", ticket, board, host, trace, "execute", attempt, feedback)).deliverable, "FORGE")

            trace.emit("phase", name="verify", attempt=attempt)
            runs = await asyncio.gather(
                *(self._agent(n, ticket, board, host, trace, "verify", attempt, []) for n in sentinels)
            )
            feedback = []
            for run in runs:
                passed, issues = run.deliverable["passed"], run.deliverable["issues"]
                trace.emit("verdict", agent=run.agent, passed=passed, issues=issues)
                feedback += [f"{run.agent}: {i}" for i in issues] if not passed else []
                if not passed and not issues:
                    feedback.append(f"{run.agent}: rejected the work without giving a reason")
            if not feedback:
                return attempt, True, "verified"
            if attempt <= self.max_retries:
                trace.emit("retry", attempt=attempt, issues=feedback)
        return self.max_retries + 1, False, f"verification still failing after {self.max_retries + 1} attempts"

    async def _agent(self, name, ticket, board, host, trace, phase, attempt, feedback) -> AgentRun:
        meta = {"ticket": ticket.id, "attempt": attempt, "phase": phase}
        prompt = build_prompt(name, ticket, board.snapshot(), attempt, feedback)
        run = await run_agent(ROSTER[name], prompt, llm=self.llm, host=host, trace=trace, meta=meta)
        self.runs.append(run)
        return run

    async def _gate(self, trace, question, *, phase: bool = False, commit: bool = False) -> bool:
        required = (self.autonomy == "manual" and (phase or commit)) or (self.autonomy == "semi" and commit)
        if not required:
            return True
        approved = bool(self.approve and await self.approve(question))
        trace.emit("approval", question=question, approved=approved, autonomy=self.autonomy)
        return approved

    def _stats(self, started: float, attempts: int) -> dict:
        return {
            "input_tokens": sum(r.input_tokens for r in self.runs),
            "output_tokens": sum(r.output_tokens for r in self.runs),
            "tool_calls": sum(r.tool_calls for r in self.runs),
            "model_calls": sum(r.steps for r in self.runs),
            "seconds": round(time.monotonic() - started, 1),
        }
