import asyncio

import pytest

from squad.llm import LLMResponse
from squad.projects import Project, discover
from squad.repl import Session
from squad.scripted import ScriptedLLM


class FrontDesk:
    """Chat replies come from the fake; everything else (triage, agents) is the scripted model."""

    def __init__(self):
        self.scripted, self.seen = ScriptedLLM(), []

    async def complete(self, *, agent, messages, tools, meta):
        if agent.name == "SQUAD":
            self.seen.append(messages[0]["content"])
            return LLMResponse([{"type": "text", "text": "Hello! Tell me what you need."}], 3, 4)
        return await self.scripted.complete(agent=agent, messages=messages, tools=tools, meta=meta)


@pytest.fixture
def session(tmp_path):
    lines = []
    project = discover(demo=True)["refunds_api"]
    answers = iter([True])

    async def ask(question):
        return next(answers, False)

    s = Session(project, FrontDesk(), autonomy="full", runs_dir=tmp_path, out=lines.append, ask=ask)
    s.lines = lines
    return s


def run(session, line):
    return asyncio.run(session.handle(line))


def text(session):
    return "\n".join(session.lines)


def test_a_greeting_gets_a_chat_reply_and_deploys_no_agents(session):
    assert run(session, "hello")
    assert "Hello! Tell me what you need." in text(session) and "MATCH" not in text(session)
    assert not session.workspace.exists()


def test_a_question_sends_in_one_agent(session):
    run(session, "What does the refund function do?")
    out = text(session)
    assert "RADAR" in out and "benched" in out and "VICTORY" in out and "refunds.py" in out


def test_later_turns_see_what_happened_earlier(session):
    run(session, "What does the refund function do?")
    run(session, "hello")
    assert "What does the refund function do?" in session.llm.seen[-1]


def test_slash_commands(session):
    assert run(session, "/autonomy manual") and session.autonomy == "manual"
    run(session, "/autonomy nonsense")
    run(session, "/squad")
    run(session, "/nope")
    out = text(session)
    assert "autonomy set to manual" in out and "choose one of" in out and "WARDEN" in out and "unknown command /nope" in out
    assert run(session, "/exit") is False


def test_changes_stay_in_the_copy_until_applied(tmp_path):
    source = tmp_path / "proj"
    source.mkdir()
    (source / "app.py").write_text("x = 1\n")
    (source / "keep.py").write_text("k = 1\n")
    lines = []

    async def yes(question):
        return True

    s = Session(Project("proj", source), FrontDesk(), autonomy="full", runs_dir=tmp_path / "runs", out=lines.append, ask=yes)
    asyncio.run(s.handle("What is in this project?"))  # creates the working copy
    (s.workspace / "app.py").write_text("x = 2\n")
    (s.workspace / "new.py").write_text("n = 1\n")
    (source / "keep.py").write_text("k = 99\n")  # the user edits this one meanwhile
    (s.workspace / "keep.py").write_text("k = 2\n")

    asyncio.run(s.handle("/diff"))
    assert "+x = 2" in "\n".join(lines)
    assert (source / "app.py").read_text() == "x = 1\n"

    asyncio.run(s.handle("/apply"))
    assert (source / "app.py").read_text() == "x = 2\n" and (source / "new.py").exists()
    assert (source / "keep.py").read_text() == "k = 99\n"  # not overwritten
    assert "skipped keep.py" in "\n".join(lines)


def test_a_new_folder_request_gets_an_empty_workspace_and_applies_to_the_destination(tmp_path, monkeypatch):
    from squad.triage import Triage, triage

    monkeypatch.setenv("HOME", str(tmp_path))
    dest = tmp_path / "Calc"
    lines = []

    async def yes(question):
        return True

    async def fake_triage(text, project, llm, **kw):
        plan = triage(text, project)
        return Triage(plan.kind, plan.draft, plan.ticket, str(dest))

    monkeypatch.setattr("squad.repl.triage_with_model", fake_triage)
    project = discover(demo=True)["refunds_api"]
    s = Session(project, FrontDesk(), autonomy="full", runs_dir=tmp_path / "runs", out=lines.append, ask=yes)
    asyncio.run(s.handle("What is in here?"))
    files = {p.name for p in s.workspace.iterdir()}
    assert "refunds.py" not in files and "tests" not in files  # not a copy of the current project
    (s.workspace / "Calc.java").write_text("class Calc {}\n")
    asyncio.run(s.handle("/apply"))
    assert (dest / "Calc.java").read_text() == "class Calc {}\n"


def test_new_folders_outside_home_are_refused(tmp_path, monkeypatch):
    from squad.triage import Triage, triage

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir()
    lines = []

    async def fake_triage(text, project, llm, **kw):
        plan = triage(text, project)
        return Triage(plan.kind, plan.draft, plan.ticket, "/etc/evil")

    monkeypatch.setattr("squad.repl.triage_with_model", fake_triage)
    s = Session(discover(demo=True)["refunds_api"], FrontDesk(), runs_dir=tmp_path / "runs", out=lines.append)
    asyncio.run(s.handle("make a folder"))
    assert any("only create new folders inside your home" in l for l in lines)
