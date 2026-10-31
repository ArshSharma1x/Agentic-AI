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

## Setup

You need Python 3.11+, git, and an Anthropic API key (console.anthropic.com). Every agent is a model call, so a run costs a few cents of API usage. macOS and Linux are what has been tested.

```
git clone https://github.com/ArshSharma1x/Agentic-AI.git && cd Agentic-AI
python3 -m venv .venv && .venv/bin/pip install -e .
cp squad.config.example.json squad.config.json    # then put your key in it (the file is gitignored)
ln -s "$PWD/.venv/bin/agentic" ~/.local/bin/agentic   # optional: lets you type `agentic` anywhere
```

## Use

```
cd /path/to/your/project
agentic          # or: /path/to/Agentic-AI/.venv/bin/python -m squad
```

This opens the squad terminal. Type what you need, the way you would in any coding assistant. A dispatcher reads each message and sends in only the agents the job needs: a greeting gets a plain reply, a question gets RADAR, a security audit gets AEGIS, a code change gets FORGE with a QA gate (plus a security gate for payments, auth or PII). The session remembers earlier turns, so follow-ups like "now add a test for that" work.

The squad works on a copy of your folder, so nothing in your files changes until you say so:

| Command | Does |
|---|---|
| `/diff` | every change the squad has made this session |
| `/apply` | copies those changes into your real folder, after asking, and skips files you edited meanwhile |
| `/autonomy manual\|semi\|full` | when you are asked: before each phase, before a commit, or never |
| `/squad`, `/new`, `/help`, `/exit` | the roster, a fresh session, help, leave |

A key is required because every agent is a model call; the terminal tells you where to put it. The `ANTHROPIC_API_KEY` environment variable also works and takes priority. `python -m squad start --web` opens the browser version of the same thing.

`squad.config.json` can also list MCP servers under `mcpServers` (same shape as `.mcp.json`). They default to the bundled Jira, Confluence and workspace stand-ins; point a name at a real MCP server command to swap it. Relative commands are resolved from the config file's folder.

Limits to know: tests run with `pytest` using the squad's own Python, so a project whose tests need their own installed dependencies will fail QA; other test runners (npm, JUnit, go test) are not supported yet, and a project with no pytest tests simply skips the test step.

## Other commands

`run` and `eval` are dev tools that use a scripted model and the bundled demo tickets, so they work with no key.

```
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/python -m squad run PAY-482 --autonomy full
.venv/bin/python -m squad ask "What does this project do?"   # terminal version of the app (needs a key)
.venv/bin/python -m squad replay <path-to-trace.jsonl>
.venv/bin/python -m squad eval   # full squad vs a solo FORGE + WARDEN baseline
.venv/bin/python -m squad ui <path-to-trace.jsonl> --open   # game-style HTML replay
.venv/bin/pytest
```

The scripted model uses real MCP tools with canned decisions, so it proves the machinery and not model quality. Use `--autonomy manual|semi|full` to control approval gates.
