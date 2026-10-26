"""The agent loop: call the model, run the tools it asks for, repeat until it hands in its deliverable."""

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

