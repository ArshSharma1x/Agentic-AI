import asyncio
import json
import threading
import time
import urllib.error
import urllib.request

import pytest
import uvicorn

from squad.projects import discover
from squad.scripted import ScriptedLLM
from squad.server import RunState, create_app


@pytest.fixture
def base_url(tmp_path):
    server = uvicorn.Server(uvicorn.Config(create_app(discover(), ScriptedLLM(), runs_dir=tmp_path), host="127.0.0.1", port=0, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.05)
    yield f"http://127.0.0.1:{server.servers[0].sockets[0].getsockname()[1]}"
    server.should_exit = True
    thread.join(5)


def post(url, body, headers=None):
    request = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(request) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as err:
        return err.code, json.load(err)


def test_posts_without_the_squad_header_are_refused(base_url):
    status, _ = post(f"{base_url}/api/runs", {"prompt": "hi", "project": "refunds_api"})
    assert status == 403


def test_triage_preview_shows_the_squad_and_blocks_code_changes_offline(base_url):
    h = {"X-Squad": "1"}
    _, data = post(f"{base_url}/api/triage", {"prompt": "What does refund() do?", "project": "refunds_api"}, h)
    assert [p["agent"] for p in data["picks"]] == ["RADAR"] and data["blocker"] is None
    _, data = post(f"{base_url}/api/triage", {"prompt": "Fix the refund bug", "project": "refunds_api"}, h)
    assert "ANTHROPIC_API_KEY" in data["blocker"]
    status, _ = post(f"{base_url}/api/runs", {"prompt": "Fix the refund bug", "project": "refunds_api"}, h)
    assert status == 400


def test_a_question_streams_a_full_match_over_sse(base_url):
    status, started = post(f"{base_url}/api/runs", {"prompt": "What does refund() do?", "project": "refunds_api", "autonomy": "full"}, {"X-Squad": "1"})
    assert status == 200
    events = []
    with urllib.request.urlopen(f"{base_url}/api/runs/{started['id']}/events", timeout=60) as stream:
        for raw in stream:
            if raw.startswith(b"data: "):
                events.append(json.loads(raw[6:]))
    assert events[0]["type"] == "match_start" and events[-1]["type"] == "match_end" and events[-1]["success"]
    assert [p["agent"] for p in next(e for e in events if e["type"] == "draft")["picks"]] == ["RADAR"]


def test_an_approval_request_pauses_the_match_until_the_browser_answers():
    async def scenario():
        run = RunState()
        waiting = asyncio.create_task(run.approve("Commit?"))
        await asyncio.sleep(0)
        assert run.events == [{"type": "approval_request", "question": "Commit?"}] and not waiting.done()
        run.pending.set_result(True)
        return await waiting

    assert asyncio.run(scenario()) is True
