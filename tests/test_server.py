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
    server = uvicorn.Server(uvicorn.Config(create_app(discover(demo=True), lambda: ScriptedLLM(), runs_dir=tmp_path), host="127.0.0.1", port=0, log_level="error"))
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


def test_config_never_exposes_the_key_and_reports_whether_one_is_set(base_url):
    with urllib.request.urlopen(f"{base_url}/api/config") as r:
        data = json.load(r)
    assert set(data) == {"projects", "autonomy", "hasKey", "configPath", "configError"} and "refunds_api" in data["projects"]


def test_deploying_without_a_key_explains_where_to_put_it(tmp_path):
    app = create_app(discover(demo=True), lambda: None, runs_dir=tmp_path)
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.05)
    try:
        url = f"http://127.0.0.1:{server.servers[0].sockets[0].getsockname()[1]}"
        status, data = post(f"{url}/api/runs", {"prompt": "hi", "project": "refunds_api"}, {"X-Squad": "1"})
    finally:
        server.should_exit = True
        thread.join(5)
    assert status == 400 and "No model available" in data["error"] and "squad.config.example.json" in data["error"]


def test_a_question_streams_a_full_match_over_sse(base_url):
    status, started = post(f"{base_url}/api/runs", {"prompt": "What does refund() do?", "project": "refunds_api", "autonomy": "full"}, {"X-Squad": "1"})
    assert status == 200
    events = []
    with urllib.request.urlopen(f"{base_url}/api/runs/{started['id']}/events", timeout=60) as stream:
        for raw in stream:
            if raw.startswith(b"data: "):
                events.append(json.loads(raw[6:]))
    assert [e["type"] for e in events[:3]] == ["triaging", "triage", "match_start"] and events[-1]["type"] == "match_end" and events[-1]["success"]
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
