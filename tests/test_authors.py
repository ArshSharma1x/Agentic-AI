"""Claude Code as the author, driven through a stand-in `claude` binary that speaks the same stream-json."""

import asyncio
import json
import sys
import textwrap

from squad.authors import ClaudeCodeAuthor
from squad.orchestrator import Match
from squad.scripted import ScriptedLLM

FAKE = textwrap.dedent('''\
    import json, sys, pathlib
    args, prompt = sys.argv[1:], sys.stdin.read()
    log = pathlib.Path({log!r})
    log.write_text(log.read_text() + json.dumps(args) + "\\n" if log.exists() else json.dumps(args) + "\\n")
    def say(**e): print(json.dumps(e), flush=True)
    say(type="system", subtype="init")
    attempt = 2 if "--resume" in args else 1
    body = {bodies!r}[attempt - 1]
    say(type="assistant", message={{"content": [{{"type": "tool_use", "id": "t1", "name": "Edit", "input": {{"file_path": str(pathlib.Path.cwd() / "money.py")}}}}]}})
    pathlib.Path("money.py").write_text(body)
    say(type="user", message={{"content": [{{"type": "tool_result", "tool_use_id": "t1", "content": "edited"}}]}})
    say(type="result", subtype="success", is_error=False, result=f"attempt {{attempt}} done", usage={{"input_tokens": 10, "output_tokens": 5}})
''')

GOOD = 'def format_amount(cents: int) -> str:\n    return f"${cents // 100}.{cents % 100:02d}"\n'
BAD = "def format_amount(cents):\n    return 'nope'\n"


def fake_claude(tmp_path, bodies):
    script = tmp_path / "claude_fake.py"
    log = tmp_path / "calls.log"
    script.write_text(FAKE.format(log=str(log), bodies=bodies))
    binary = tmp_path / "claude"
    binary.write_text(f"#!/bin/sh\nexec {sys.executable} {script} \"$@\"\n")
    binary.chmod(0o755)
    return str(binary), log


def test_claude_code_writes_the_gate_judges_and_the_retry_resumes_the_same_session(tmp_path):
    binary, log = fake_claude(tmp_path, [BAD, GOOD])
    author = ClaudeCodeAuthor("claude-sonnet-5-5", binary=binary)
    match = Match("BUG-101", llm=ScriptedLLM(), autonomy="full", runs_dir=tmp_path / "runs", author=author)
    result = asyncio.run(match.run())
    assert result.success and result.attempts == 2 and result.verdict == "PASS" and result.commit
    calls = [json.loads(l) for l in log.read_text().splitlines()]
    assert "--session-id" in calls[0] and calls[1][calls[1].index("--resume") + 1] == author.session
    for call in calls:  # no shell, no web, no MCP servers, no user settings
        assert call[call.index("--tools") + 1] == "Read,Edit,Write,Glob,Grep"
        assert "--strict-mcp-config" in call and call[call.index("--setting-sources") + 1] == ""
