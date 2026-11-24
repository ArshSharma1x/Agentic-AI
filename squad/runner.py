"""The agent loop: call the model, run the tools it asks for, repeat until it hands in its deliverable."""

import jsonschema

from .llm import LLM
from .local_tools import LOCAL_TOOLS
from .mcp_host import MCPHost, ToolCallError
from .models import AgentRun, AgentSpec
from .trace import Trace

MAX_STEPS = 14
PREVIEW_CHARS = 160


class AgentError(Exception):
    pass


def _preview(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= PREVIEW_CHARS else text[:PREVIEW_CHARS] + "..."


def _invalid(args, schema: dict) -> str | None:
    try:
        jsonschema.validate(args, {**schema, "additionalProperties": False})
    except jsonschema.ValidationError as err:
        return f"rejected: {err.message}. Call the tool again with valid arguments."
    return None


async def run_agent(
    agent: AgentSpec, prompt: str, *, llm: LLM, host: MCPHost, trace: Trace, meta: dict
) -> AgentRun:
    tools = host.tool_defs(agent.tools) + [LOCAL_TOOLS[agent.deliverable]]
    messages: list[dict] = [{"role": "user", "content": prompt}]
    run = AgentRun(agent=agent.name, deliverable={}, steps=0, tool_calls=0)
    nudged = False
    trace.emit("agent_start", agent=agent.name, role=agent.role.value, model=agent.model, phase=meta["phase"])

    for _ in range(MAX_STEPS):
        response = await llm.complete(agent=agent, messages=messages, tools=tools, meta=meta)
        run.steps += 1
        run.input_tokens += response.input_tokens
        run.output_tokens += response.output_tokens
        messages.append({"role": "assistant", "content": response.content})

        calls = [b for b in response.content if b["type"] == "tool_use"]
        if response.stop_reason == "max_tokens":
            # A cut-off reply can hold a half-written tool call (half a file). Run none of it; ask for smaller steps.
            trace.emit("tool_result", agent=agent.name, tool="(reply)", ok=False, preview="reply cut off at the output limit; nothing in it was run")
            cut = "Your reply was cut off at the output limit, so none of its tool calls were run. Use smaller steps (edit_file instead of rewriting whole files)."
            messages.append({"role": "user", "content": [
                *({"type": "tool_result", "tool_use_id": c["id"], "content": cut, "is_error": True} for c in calls),
                *([] if calls else [{"type": "text", "text": cut}]),
            ]})
            continue
        if not calls:
            if nudged:
                raise AgentError(f"{agent.name} stopped without calling {agent.deliverable}")
            nudged = True
            messages.append({"role": "user", "content": f"You must finish by calling {agent.deliverable}."})
            continue

        results, finished = [], False
        for call in calls:
            name, args = call["name"], call["input"]
            run.tool_calls += 1
            trace.emit("tool_call", agent=agent.name, tool=name, args=args)
            if name == agent.deliverable:
                problem = _invalid(args, LOCAL_TOOLS[name]["input_schema"])
                if problem:  # e.g. passed: "false" instead of false. Ask for a repair instead of trusting it.
                    trace.emit("tool_result", agent=agent.name, tool=name, ok=False, preview=_preview(problem))
                    results.append({"type": "tool_result", "tool_use_id": call["id"], "content": problem, "is_error": True})
                    continue
                run.deliverable = args
                finished = True
                results.append({"type": "tool_result", "tool_use_id": call["id"], "content": "recorded"})
                continue
            try:
                output = await host.call_as(agent.name, agent.tools, name, args)
                trace.emit("tool_result", agent=agent.name, tool=name, ok=True, preview=_preview(output))
                results.append({"type": "tool_result", "tool_use_id": call["id"], "content": output})
            except ToolCallError as err:
                trace.emit("tool_result", agent=agent.name, tool=name, ok=False, preview=_preview(str(err)))
                results.append({"type": "tool_result", "tool_use_id": call["id"], "content": str(err), "is_error": True})

        if finished:
            trace.emit(
                "agent_done", agent=agent.name, steps=run.steps, tool_calls=run.tool_calls,
                input_tokens=run.input_tokens, output_tokens=run.output_tokens,
            )
            return run
        messages.append({"role": "user", "content": results})

    raise AgentError(f"{agent.name} exceeded {MAX_STEPS} steps without finishing")

