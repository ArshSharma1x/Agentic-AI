"""Turns trace events into readable console lines. The CLI uses it live and for replays."""

from .agents import ROSTER

RESET, DIM, BOLD = "\033[0m", "\033[2m", "\033[1m"
ROLE_COLORS = {"Duelist": "\033[91m", "Initiator": "\033[96m", "Controller": "\033[93m", "Sentinel": "\033[92m"}
RED, GREEN = "\033[91m", "\033[92m"


def _who(name: str) -> str:
    agent = ROSTER.get(name)
    color = ROLE_COLORS[agent.role.value] if agent else ""
    return f"{color}{BOLD}{name:<7}{RESET}"


def _short(value, limit: int = 90) -> str:
    text = " ".join(str(value).split())
    return text if len(text) <= limit else text[: limit - 3] + "..."


def render(event: dict) -> str | None:
    t = f"{DIM}{event['t']:6.1f}s{RESET}"
    kind = event["type"]
    if kind == "match_start":
        return f"\n{BOLD}MATCH{RESET} {event['ticket']}: {event['title']}  {DIM}[autonomy={event['autonomy']}, llm={event['llm']}]{RESET}"
    if kind == "draft":
        lines = [f"\n{BOLD}AGENT SELECT{RESET}"]
        lines += [f"  {_who(p['agent'])} {DIM}{p['reason']}{RESET}" for p in event["picks"]]
        lines += [f"  {DIM}{p['agent']:<7} benched: {p['reason']}{RESET}" for p in event["skipped"]]
        return "\n".join(lines)
    if kind == "phase":
        attempt = f" (attempt {event['attempt']})" if "attempt" in event else ""
        return f"\n{BOLD}== {event['name'].upper()}{attempt} =={RESET}"
    if kind == "tool_call":
        return f"{t} {_who(event['agent'])} {event['tool']} {DIM}{_short(event['args'])}{RESET}"
    if kind == "tool_result":
        mark = f"{DIM}->{RESET}" if event["ok"] else f"{RED}!!{RESET}"
        return f"{t} {'':<7} {mark} {DIM}{_short(event['preview'])}{RESET}"
    if kind == "agent_done":
        return f"{t} {_who(event['agent'])} done {DIM}({event['steps']} model calls, {event['input_tokens'] + event['output_tokens']} tokens){RESET}"
    if kind == "verdict":
        label = f"{GREEN}PASS{RESET}" if event["passed"] else f"{RED}FAIL{RESET}"
        issues = "".join(f"\n{'':<17}{RED}- {_short(i, 110)}{RESET}" for i in event["issues"])
        return f"{t} {_who(event['agent'])} verdict {label}{issues}"
    if kind == "retry":
        return f"{t} {BOLD}RETRY{RESET} attempt {event['attempt']} rejected; sending {len(event['issues'])} issue(s) back to FORGE"
    if kind == "approval":
        return f"{t} {BOLD}APPROVAL{RESET} {event['question']} -> {'yes' if event['approved'] else 'no'}"
    if kind == "commit":
        return f"{t} {BOLD}COMMIT{RESET} {event['sha']}"
    if kind == "match_end":
        verdict = f"{GREEN}VICTORY{RESET}" if event["success"] else f"{RED}DEFEAT{RESET}"
        tokens = event["input_tokens"] + event["output_tokens"]
        answer = f"\n\n{event['answer']}" if event.get("answer") else ""
        return (
            f"\n{BOLD}{verdict}{RESET} {event['reason']}{answer}\n"
            f"{DIM}attempts={event['attempts']} model_calls={event['model_calls']} tool_calls={event['tool_calls']} "
            f"tokens={tokens} time={event['seconds']}s{RESET}"
        )
    return None  # agent_start and blackboard writes stay in the trace file only
