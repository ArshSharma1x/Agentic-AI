"""`squad start`: a local web app. Type a problem, triage sizes the squad, the match streams live into the HUD."""

import asyncio
import json
import uuid
from pathlib import Path

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, StreamingResponse
from starlette.routing import Route

from .agents import ROSTER
from .paths import RUNS_DIR
from .orchestrator import AUTONOMY_LEVELS, Match
from .projects import Project
from .scripted import ScriptedLLM
from .triage import offline_blocker, triage
from .ui import build_html

MAX_PROMPT = 4000


class RunState:
    """One match: its events so far, who is waiting for more, and an approval the human has yet to answer."""

    def __init__(self) -> None:
        self.events: list[dict] = []
        self.finished = False
        self.pending: asyncio.Future | None = None
        self._waiters: list[asyncio.Future] = []

    def push(self, event: dict) -> None:
        self.events.append(event)
        self._wake()

    def _wake(self) -> None:
        for waiter in self._waiters:
            if not waiter.done():
                waiter.set_result(None)
        self._waiters.clear()

    async def changed(self) -> None:
        waiter = asyncio.get_running_loop().create_future()
        self._waiters.append(waiter)
        await waiter

    async def approve(self, question: str) -> bool:
        self.pending = asyncio.get_running_loop().create_future()
        self.push({"type": "approval_request", "question": question})
        return await self.pending

    async def play(self, match: Match) -> None:
        try:
            await match.run()
        except Exception as err:  # shown in the HUD instead of dying silently inside a background task
            self.push({"type": "error", "message": str(err)})
        finally:
            self.finished = True
            self._wake()


def create_app(projects: dict[str, Project], llm, runs_dir: Path = RUNS_DIR) -> Starlette:
    runs: dict[str, RunState] = {}
    scripted = isinstance(llm, ScriptedLLM)

    def guard(request: Request) -> JSONResponse | None:
        # A custom header forces a CORS preflight that this server never grants, so other websites cannot start runs.
        if request.headers.get("x-squad") != "1":
            return JSONResponse({"error": "missing X-Squad header"}, status_code=403)
        return None

    async def parse(request: Request):
        body = await request.json()
        prompt, project = str(body.get("prompt", "")).strip(), body.get("project")
        if not prompt or len(prompt) > MAX_PROMPT:
            return None, JSONResponse({"error": f"write a problem (1-{MAX_PROMPT} characters)"}, status_code=400)
        if project not in projects:
            return None, JSONResponse({"error": "unknown project"}, status_code=400)
        agents = [str(a).upper() for a in body.get("agents") or []] or None
        try:
            plan = triage(prompt, project, agents=agents)
        except ValueError as err:
            return None, JSONResponse({"error": str(err)}, status_code=400)
        return (plan, body), None

    async def page(request: Request):
        return HTMLResponse(build_html([], live=True))

    async def config(request: Request):
        return JSONResponse({
            "projects": list(projects), "autonomy": list(AUTONOMY_LEVELS), "agents": list(ROSTER),
            "llm": "scripted" if scripted else "anthropic",
        })

    async def preview(request: Request):
        if denied := guard(request):
            return denied
        parsed, error = await parse(request)
        if error:
            return error
        plan, _ = parsed
        return JSONResponse({
            "kind": plan.kind,
            "picks": [{"agent": p.agent, "reason": p.reason} for p in plan.draft.picks],
            "skipped": [{"agent": p.agent, "reason": p.reason} for p in plan.draft.skipped],
            "blocker": offline_blocker(plan.draft.names, plan.ticket.id, scripted=scripted),
        })

    async def start(request: Request):
        if denied := guard(request):
            return denied
        parsed, error = await parse(request)
        if error:
            return error
        plan, body = parsed
        autonomy = body.get("autonomy", "semi")
        if autonomy not in AUTONOMY_LEVELS:
            return JSONResponse({"error": f"autonomy must be one of {AUTONOMY_LEVELS}"}, status_code=400)
        if blocker := offline_blocker(plan.draft.names, plan.ticket.id, scripted=scripted):
            return JSONResponse({"error": blocker}, status_code=400)
        if any(not r.finished for r in runs.values()):
            return JSONResponse({"error": "a match is already running"}, status_code=409)
        run, run_id = RunState(), uuid.uuid4().hex[:8]
        runs[run_id] = run
        match = Match(
            plan.ticket.id, llm=llm, autonomy=autonomy, approve=run.approve, listeners=[run.push], runs_dir=runs_dir,
            ticket=plan.ticket, project=projects[body["project"]].path, squad_draft=plan.draft,
        )
        run.task = asyncio.create_task(run.play(match))
        return JSONResponse({"id": run_id})

    async def events(request: Request):
        run = runs.get(request.path_params["run_id"])
        if run is None:
            return JSONResponse({"error": "unknown run"}, status_code=404)

        async def stream():
            sent = 0
            while True:
                while sent < len(run.events):
                    yield f"data: {json.dumps(run.events[sent])}\n\n"
                    sent += 1
                if run.finished:
                    return
                try:
                    await asyncio.wait_for(run.changed(), 15)
                except TimeoutError:
                    yield ": keep-alive\n\n"

        return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})

    async def approve(request: Request):
        if denied := guard(request):
            return denied
        run = runs.get(request.path_params["run_id"])
        if run is None or run.pending is None or run.pending.done():
            return JSONResponse({"error": "nothing is waiting for approval"}, status_code=409)
        run.pending.set_result(bool((await request.json()).get("approved")))
        return JSONResponse({"ok": True})

    return Starlette(routes=[
        Route("/", page), Route("/api/config", config),
        Route("/api/triage", preview, methods=["POST"]), Route("/api/runs", start, methods=["POST"]),
        Route("/api/runs/{run_id}/events", events), Route("/api/runs/{run_id}/approve", approve, methods=["POST"]),
    ])
