"""Who writes the code. FORGE is a seat, not a fixed model loop: the built-in agent, or Claude Code itself.

Claude Code brings the tools serious agents use (Read, Edit with exact-match replace, Grep, Glob) and keeps one
session across retries, so it remembers what it tried. It is started with no shell, no web access and no MCP
servers: it can edit files in the working copy and nothing else. Running anything is the gate's job, inside the
sandbox. Whatever it writes, including any attempt to edit tests, is judged by WARDEN like any other author.
"""

import asyncio
import json
import os
import shutil
import uuid
from pathlib import Path

from .models import AgentRun

TOOLS = "Read,Edit,Write,Glob,Grep"
TIMEOUT_SECONDS = 900
RULES = (
    "You are FORGE, the author in a verification squad. Make the requested change in this working copy. "
    "You cannot run commands. After you finish, an independent gate re-runs the ORIGINAL tests (plus hidden ones) "
    "in a sandbox and checks integrity: changing, skipping or deleting existing tests, test configuration or CI "
    "fails the change. Add tests for new behaviour in new test files. End with a short summary of what you changed."
)


class AuthorError(Exception):
    pass


class ClaudeCodeAuthor:
    name = "claude-code"

    def __init__(self, model: str, binary: str = "claude") -> None:
        self.model, self.binary = model, binary
        self.session: str | None = None

    async def write(self, workspace: Path, prompt: str, trace, meta: dict) -> AgentRun:
        first = self.session is None
        self.session = self.session or str(uuid.uuid4())
        args = [
            self.binary, "-p", "--output-format", "stream-json", "--verbose", "--model", self.model,
            "--permission-mode", "acceptEdits", "--tools", TOOLS, "--setting-sources", "",
            "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}', "--append-system-prompt", RULES,
            *(["--session-id", self.session] if first else ["--resume", self.session]),
        ]
        env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}
        trace.emit("agent_start", agent="FORGE", role="Duelist", model=f"Claude Code ({self.model})", phase=meta["phase"])
        proc = await asyncio.create_subprocess_exec(
            *args, cwd=workspace, env=env, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE, limit=16 * 1024 * 1024,
        )
        proc.stdin.write(prompt.encode())
        await proc.stdin.drain()
        proc.stdin.close()
        run = AgentRun(agent="FORGE", deliverable={}, steps=0, tool_calls=0)
        result: dict = {}
        try:
            async with asyncio.timeout(TIMEOUT_SECONDS):
                async for line in proc.stdout:
                    event = _parse(line)
                    if event.get("type") == "assistant":
                        run.steps += 1
                        for block in event.get("message", {}).get("content", []):
                            if block.get("type") == "tool_use":
                                run.tool_calls += 1
                                trace.emit("tool_call", agent="FORGE", tool=f"claude:{block['name']}", args=_relative(block.get("input", {}), workspace))
                    elif event.get("type") == "user":
                        for block in event.get("message", {}).get("content", []):
                            if isinstance(block, dict) and block.get("type") == "tool_result":
                                text = block.get("content")
                                text = text if isinstance(text, str) else json.dumps(text)
                                trace.emit("tool_result", agent="FORGE", tool="claude", ok=not block.get("is_error"), preview=" ".join(text.split())[:160])
                    elif event.get("type") == "result":
                        result = event
                await proc.wait()
        except TimeoutError:
            proc.kill()
            raise AuthorError(f"Claude Code did not finish within {TIMEOUT_SECONDS}s")
        if not result or result.get("is_error"):
            err = (await proc.stderr.read()).decode(errors="replace")
            raise AuthorError(f"Claude Code failed: {str(result.get('result') or err)[:300]}")
        usage = result.get("usage", {})
        run.input_tokens = usage.get("input_tokens", 0) + usage.get("cache_creation_input_tokens", 0)
        run.output_tokens = usage.get("output_tokens", 0)
        run.deliverable = {"summary": str(result.get("result", "")).strip()}
        trace.emit("agent_done", agent="FORGE", steps=run.steps, tool_calls=run.tool_calls,
                   input_tokens=run.input_tokens, output_tokens=run.output_tokens)
        return run


def _parse(line: bytes) -> dict:
    try:
        return json.loads(line)
    except ValueError:
        return {}


def _relative(args: dict, root: Path) -> dict:
    """Absolute paths in the trace are noise; show them relative to the working copy."""
    prefix = str(Path(root).resolve()) + os.sep
    return {k: (v.replace(prefix, "") if isinstance(v, str) else v) for k, v in args.items() if k != "content" or len(str(v)) < 200}


def author_from_config(model: str):
    """`author` in squad.config.json (or SQUAD_AUTHOR): auto, squad or claude-code. Auto prefers Claude Code."""
    from .claude_code import claude_code_ready
    from .config import load_config

    choice = os.environ.get("SQUAD_AUTHOR") or load_config().author
    if choice == "squad":
        return None
    if choice == "claude-code" or (choice == "auto" and shutil.which("claude") and claude_code_ready()):
        return ClaudeCodeAuthor(model)
    return None
