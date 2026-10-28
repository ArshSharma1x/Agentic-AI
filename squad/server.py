"""`squad start`: a local web app. Type a problem, triage sizes the squad, the match streams live into the HUD."""

import asyncio
import json
import uuid
from collections.abc import Callable
from pathlib import Path

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, StreamingResponse
from starlette.routing import Route

from .config import ConfigError, config_path
from .llm import llm_from_config
from .paths import RUNS_DIR
from .orchestrator import AUTONOMY_LEVELS, Match
from .projects import Project, overview
from .triage import triage_with_model
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

    async def play(self, prompt: str, project: Project, autonomy: str, llm, runs_dir: Path) -> None:
        try:
            self.push({"type": "triaging"})
            plan = await triage_with_model(prompt, project.name, llm, files=overview(project.path))
            self.push({"type": "triage", "kind": plan.kind, "agents": plan.draft.names})
            match = Match(
                plan.ticket.id, llm=llm, autonomy=autonomy, approve=self.approve, listeners=[self.push],
                runs_dir=runs_dir, ticket=plan.ticket, project=project.path, squad_draft=plan.draft,
            )
            await match.run()
        except Exception as err:  # shown in the HUD instead of dying silently inside a background task
            self.push({"type": "error", "message": str(err)})
        finally:
            self.finished = True
            self._wake()


def create_app(projects: dict[str, Project], llm_provider: Callable[[], object | None] = llm_from_config, runs_dir: Path = RUNS_DIR) -> Starlette:
    """`llm_provider` is called on every deploy, so a key added to squad.config.json works without a restart."""
    runs: dict[str, RunState] = {}

    def guard(request: Request) -> JSONResponse | None:
        # A custom header forces a CORS preflight that this server never grants, so other websites cannot start runs.
        if request.headers.get("x-squad") != "1":
            return JSONResponse({"error": "missing X-Squad header"}, status_code=403)
        return None

    async def page(request: Request):
        return HTMLResponse(build_html([], live=True))

    async def config(request: Request):
        try:
            has_key, problem = llm_provider() is not None, None
        except ConfigError as err:
            has_key, problem = False, str(err)
        return JSONResponse({
            "projects": list(projects), "autonomy": list(AUTONOMY_LEVELS), "hasKey": has_key,
            "configPath": str(config_path()), "configError": problem,
        })

    async def start(request: Request):
        if denied := guard(request):
            return denied
        body = await request.json()
        prompt, project, autonomy = str(body.get("prompt", "")).strip(), body.get("project"), body.get("autonomy", "semi")
        if not prompt or len(prompt) > MAX_PROMPT:
            return JSONResponse({"error": f"write a problem (1-{MAX_PROMPT} characters)"}, status_code=400)
        if project not in projects:
            return JSONResponse({"error": "unknown project"}, status_code=400)
        if autonomy not in AUTONOMY_LEVELS:
            return JSONResponse({"error": f"autonomy must be one of {AUTONOMY_LEVELS}"}, status_code=400)
        try:
            llm = llm_provider()
        except ConfigError as err:
            return JSONResponse({"error": str(err)}, status_code=400)
        if llm is None:
            return JSONResponse({"error": f"No API key yet: add it to {config_path()} (see squad.config.example.json)."}, status_code=400)
        if any(not r.finished for r in runs.values()):
            return JSONResponse({"error": "a match is already running"}, status_code=409)
        run, run_id = RunState(), uuid.uuid4().hex[:8]
        runs[run_id] = run
        run.task = asyncio.create_task(run.play(prompt, projects[project], autonomy, llm, runs_dir))
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
        Route("/api/runs", start, methods=["POST"]),
        Route("/api/runs/{run_id}/events", events), Route("/api/runs/{run_id}/approve", approve, methods=["POST"]),
    ])
