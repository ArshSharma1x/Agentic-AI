"""A model backend that uses the user's own logged-in Claude Code, so no API key is needed.

Each model call is one `claude -p` run with Claude Code's built-in tools switched off. Claude Code has no raw
tool-use interface, so the tool-calling protocol is emulated: the model replies with JSON naming the tool calls
to make, constrained by a schema built from the real tool definitions, and the agent loop runs them as usual.
"""

import asyncio
import json
import os
import shutil
import subprocess
import tempfile
import uuid

from .llm import LLMResponse
from .models import AgentSpec

TIMEOUT_SECONDS = 240
PROTOCOL = (
    "\n\nYou work in steps and reply with JSON only. `calls` lists the tool calls to make in this step. "
    "Several independent read-only calls may go in one step. A submit_* tool ends your work: call it alone, "
    "once, only after you have seen the results you need. Earlier steps and their results are in the transcript. "
    "Never invent a tool result and never answer in prose instead of calling a tool."
)


class ClaudeCodeError(Exception):
    pass


def claude_code_ready() -> bool:
    """True when the `claude` CLI is installed and logged in."""
    if not shutil.which("claude"):
        return False
    try:
        done = subprocess.run(["claude", "auth", "status"], capture_output=True, text=True, timeout=15)
        return bool(json.loads(done.stdout).get("loggedIn"))
    except (subprocess.SubprocessError, ValueError, OSError):
        return False


def _render(messages: list[dict]) -> str:
    lines: list[str] = []
    for message in messages:
        content = message["content"]
        if isinstance(content, str):
            lines.append(("TASK:\n" if message["role"] == "user" and not lines else "NOTE:\n") + content)
            continue
        for block in content:
            kind = block.get("type")
            if kind == "text":
                lines.append(f"YOU SAID: {block['text']}")
            elif kind == "tool_use":
                lines.append(f"YOU CALLED: {block['name']} {json.dumps(block['input'])}")
            elif kind == "tool_result":
                error = " (error)" if block.get("is_error") else ""
                lines.append(f"RESULT{error}: {block['content']}")
    return "\n\n".join(lines)


def _schema(tools: list[dict]) -> dict:
    options = [
        {
            "type": "object",
            "properties": {"tool": {"const": t["name"]}, "input": t.get("input_schema") or {"type": "object"}},
            "required": ["tool", "input"],
        }
        for t in tools
    ]
    return {
        "type": "object",
        "properties": {"calls": {"type": "array", "items": {"anyOf": options}}, "text": {"type": "string"}},
        "required": ["calls"],
    }


def _catalogue(tools: list[dict]) -> str:
    return "\n".join(f"- {t['name']}: {t.get('description', '').strip()}" for t in tools)


class ClaudeCodeLLM:
    async def _run(self, system: str, prompt: str, model: str, schema: dict | None) -> dict:
        args = [
            "claude", "-p", "--output-format", "json", "--model", model, "--tools", "",
            "--no-session-persistence", "--setting-sources", "", "--disable-slash-commands",
            "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}', "--system-prompt", system,
        ]
        if schema:
            args += ["--json-schema", json.dumps(schema)]
        # A neutral folder keeps any project CLAUDE.md out; dropping the key makes it use the subscription login.
        env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}
        proc = await asyncio.create_subprocess_exec(
            *args, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            cwd=tempfile.gettempdir(), env=env,
        )
        try:
            out, err = await asyncio.wait_for(proc.communicate(prompt.encode()), TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            proc.kill()
            raise ClaudeCodeError(f"Claude Code did not answer within {TIMEOUT_SECONDS}s")
        try:
            data = json.loads(out)
        except ValueError:
            raise ClaudeCodeError(f"Claude Code failed: {(err or out).decode()[:300]}")
        if data.get("is_error"):
            raise ClaudeCodeError(f"Claude Code error: {str(data.get('result'))[:300]}")
        return data

    async def complete(self, *, agent: AgentSpec, messages: list[dict], tools: list[dict], meta: dict) -> LLMResponse:
        prompt = _render(messages)
        if not tools:
            data = await self._run(agent.system, prompt, agent.model, None)
            return self._response([{"type": "text", "text": str(data.get("result", "")).strip()}], data)
        system = agent.system + PROTOCOL
        prompt = f"AVAILABLE TOOLS:\n{_catalogue(tools)}\n\n{prompt}\n\nNEXT STEP (JSON):"
        for attempt in (1, 2):
            data = await self._run(system, prompt, agent.model, _schema(tools))
            try:
                reply = data.get("structured_output") or json.loads(data["result"])
                calls = [c for c in reply["calls"] if c["tool"] in {t["name"] for t in tools}]
                break
            except (KeyError, ValueError, TypeError):
                if attempt == 2:
                    raise ClaudeCodeError("Claude Code returned a reply that was not valid tool calls")
        # A submit_* call must wait until the other calls' results are in.
        if len(calls) > 1:
            calls = [c for c in calls if c["tool"] != agent.deliverable] or calls
        blocks: list[dict] = []
        if reply.get("text"):
            blocks.append({"type": "text", "text": reply["text"]})
        blocks += [{"type": "tool_use", "id": f"toolu_{uuid.uuid4().hex[:12]}", "name": c["tool"], "input": c["input"]} for c in calls]
        return self._response(blocks, data)

    @staticmethod
    def _response(blocks: list[dict], data: dict) -> LLMResponse:
        usage = data.get("usage", {})
        # Cache reads are Claude Code re-reading its own context, not work the squad asked for, so they are left out.
        tokens_in = usage.get("input_tokens", 0) + usage.get("cache_creation_input_tokens", 0)
        return LLMResponse(blocks, tokens_in, usage.get("output_tokens", 0))
