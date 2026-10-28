# Agentic-AI

A Valorant-style squad of AI agents that takes a ticket from requirements to a verified commit, using MCP tools. The concept is in [vision.md](vision.md).

## How it works

For each ticket, an explicit and logged draft picks the squad:

| Agent  | Role                | Does                                   |
|--------|---------------------|----------------------------------------|
| RADAR  | Initiator           | Gathers intel from Jira and Confluence |
| ATLAS  | Controller          | Plans the work                         |
| FORGE  | Duelist             | Writes the code                        |
| WARDEN | Sentinel (QA)       | Runs the tests                         |
| AEGIS  | Sentinel (Security) | Scans for security problems            |

The match runs intel, plan, execute and verify, with retries. A commit happens only after the verify gates pass and the autonomy level allows it. Every agent can call only its own MCP tools, and `tests/` is read-only to agents. Each match writes a `trace.jsonl`.

## Run

## Quick start

```
.venv/bin/python -m squad start      # opens the app: type a problem, the squad is sized to it
```

Type a question and one agent answers. Ask for a security audit and AEGIS reviews the code. Ask for a change and the full squad drafts, builds, verifies and asks before committing. Pick agents yourself with the toggles to override triage. Add your own code with `--project /path/to/folder` (it is copied, never edited in place).

## Commands

```
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/python -m squad run PAY-482 --autonomy full
.venv/bin/python -m squad ask "What does the refund function do?"   # a plain-words problem; triage sizes the squad
.venv/bin/python -m squad replay <path-to-trace.jsonl>
.venv/bin/python -m squad eval   # full squad vs a solo FORGE + WARDEN baseline
.venv/bin/python -m squad ui <path-to-trace.jsonl> --open   # game-style HTML replay
.venv/bin/pytest
```

`--llm auto` uses Claude when `ANTHROPIC_API_KEY` is set and a scripted model otherwise. The scripted model uses real MCP tools with canned decisions, so it proves the machinery and not model quality. Use `--autonomy manual|semi|full` to control approval gates.
