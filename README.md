# Agentic-AI

A squad of AI agents that verifies code changes with evidence a skeptic would accept. The author agent writes; a deterministic gate and an independent reviewer decide. Why and where it is going: [vision.md](vision.md).

> **Status, stated plainly:** an audit in November 2026 found that the old gates trusted the model's own verdict and that model-written code ran without isolation. Both are fixed (deterministic gate, OS sandbox), with an adversarial test for every finding. Pluggable author agents, signed evidence and a live eval are next (see vision.md).

## Verify any agent's work

Let Claude Code, Codex, Cursor or anything else make a change, then:

```
cd your-repo
agentic verify
```

```
Verifying your working tree against HEAD (uncommitted changes), 2 file(s) changed
WARDEN gate FAIL (sandbox: seatbelt)
   !! integrity: changed existing test tests/test_calc.py
   ok compile: 1 changed file(s) compile
   !! tests: 1 test(s) fail: tests.test_calc::test_add
```

It rebuilds the change in a private copy with the base commit as the baseline, so your repo is never modified and its hooks never run. With no `--base`, uncommitted work is checked against `HEAD`, and a clean branch against where it left `main`. Exit codes: `0` PASS, `1` FAIL, `2` UNVERIFIED, `3` usage error, so it drops straight into CI. Options: `--hidden <dir>` adds tests the agent never saw, `--json <file>` writes the full report, `--evidence <file>` writes an [in-toto](https://in-toto.io) attestation statement, `--loopback` lets suites that start local servers use localhost (never the internet).

### In CI, on every pull request

```yaml
permissions: { contents: read, id-token: write, attestations: write }
jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - uses: ArshSharma1x/Agentic-AI@main
```

The job fails on FAIL and (unless `fail-on-unverified: false`) UNVERIFIED, writes a summary table to the run, and signs the evidence with GitHub artifact attestations (Sigstore, no keys to manage). Anyone can then check that a commit really passed the gate: `gh attestation verify --owner <you> --predicate-type https://github.com/ArshSharma1x/Agentic-AI/attestations/verification/v0.1 ...`. This repo gates its own pull requests the same way (`.github/workflows/agentic-verify.yml`).

### Policy (`.agentic.toml`)

```toml
network = "none"              # or "loopback"
require_tests = false         # true: untestable changes FAIL instead of UNVERIFIED
allow_test_changes = false    # true: edits to existing tests are reported, and the edited tests run
sensitive = ["payments/**"]   # changes here are UNVERIFIED until a human reviews them
```

The policy is read from the **base** commit, so a change cannot loosen the rules that judge it, and editing the file counts as tampering.

## How it works

The author (FORGE) makes the change in a copy of your project. If Claude Code is installed and logged in, FORGE **is** Claude Code: one session per working copy (so retries and follow-ups keep context), with its real Read, Edit, Grep and Glob tools, and with no shell, no web access and no MCP servers, so it can edit files and nothing else. Otherwise a built-in agent fills the seat. Set `"author": "squad" | "claude-code"` in `squad.config.json` to choose. Then **WARDEN, the deterministic gate** (`squad/gate.py`), decides. It is code, not a model, and the author cannot talk it round:

| Check | What it catches |
|---|---|
| Integrity | Changed, moved or deleted existing tests; planted `conftest.py`, `pytest.ini`, `sitecustomize.py` or pytest settings in `pyproject.toml`; source code that detects it is under test (`PYTEST_CURRENT_TEST`) or exits early |
| Review | Edits to CI or to the gate's own policy: often legitimate, so not FAIL, but UNVERIFIED until a human looks |
| Compile | Syntax errors in any changed Python, JSON, JavaScript or Java file, even ones the tests never import |
| Original tests | Runs the tests **as they were before the change** (tampered files are put back first) and compares each test with the baseline: only failures the change introduced count; all-skipped, vanished or early-exit runs fail |
| Hidden tests | Optional tests the author never sees. Failures are reported by count only, so the author cannot fit to them |

The verdict is **PASS**, **FAIL**, or **UNVERIFIED** (for example, the project has no tests). Nothing is committed on UNVERIFIED unless you accept it. AEGIS, an independent model reviewer, can add findings on top, but no model can turn a red gate green. Model-written code runs in an OS sandbox (Seatbelt on macOS, bubblewrap on Linux): no network, no reading your home directory, no writing outside the working copy, and an allow-listed environment with no API keys, tokens or SSH agent. Git runs with hooks and `fsmonitor` disabled. Where no sandbox is available the evidence says `sandbox: none` rather than pretending. Each defence has an adversarial test (`tests/test_gate.py`, `tests/test_sandbox.py`), and CI runs them against the real Linux sandbox.

Least privilege by construction: RADAR reads untrusted tickets and docs but can write nothing and reach nothing; its notes reach FORGE marked as untrusted data, never as instructions. FORGE can write code, but the code it runs has no network and no secrets. No role holds untrusted input, secrets and a way out at the same time (the "lethal trifecta" behind the 2026 CI-secret thefts).

The dispatcher sizes the squad per request (a question gets RADAR alone; a change gets FORGE, the gate, and AEGIS when payments, auth or PII are involved), and every pick is logged with its reason. Each run writes a `trace.jsonl`.

## Setup

You need Python 3.11+, git, and one of:

- **Claude Code**, installed and logged in with a subscription (run `claude` once to check). No key needed; the squad uses your login.
- **An Anthropic API key** (console.anthropic.com), which is faster and cheaper per run. A key, if present, is used first.

macOS and Linux are what has been tested.

```
git clone https://github.com/ArshSharma1x/Agentic-AI.git && cd Agentic-AI
python3 -m venv .venv && .venv/bin/pip install -e .
cp squad.config.example.json squad.config.json    # only if you use an API key: put it in this file (gitignored)
ln -s "$PWD/.venv/bin/agentic" ~/.local/bin/agentic   # optional: lets you type `agentic` anywhere
```

## Use

```
cd /path/to/your/project
agentic          # or: /path/to/Agentic-AI/.venv/bin/python -m squad
```

This opens the squad terminal. Type what you need, the way you would in any coding assistant. A dispatcher reads each message and sends in only the agents the job needs: a greeting gets a plain reply, a question gets RADAR, a security audit gets AEGIS, a code change gets FORGE with a QA gate (plus a security gate for payments, auth or PII). The session remembers earlier turns, so follow-ups like "now add a test for that" work.

The squad works on a copy of your folder and only `/apply` writes back to it. Code the squad runs is sandboxed (see How it works).

| Command | Does |
|---|---|
| `/diff` | every change the squad has made this session |
| `/apply` | copies those changes into your real folder, after asking, and skips files you edited meanwhile |
| `/autonomy manual\|semi\|full` | when you are asked: before each phase, before a commit, or never |
| `/squad`, `/new`, `/help`, `/exit` | the roster, a fresh session, help, leave |

Every agent is a model call, so a model is required: your Claude Code login, or an API key (`squad.config.json` or the `ANTHROPIC_API_KEY` environment variable). With a key the squad uses the API; without one it uses Claude Code. Set `"provider": "api"` or `"claude-code"` in `squad.config.json` (or `SQUAD_PROVIDER`) to force one. Through Claude Code each step is a separate `claude -p` run, so it is a few seconds slower per step and counts against your subscription's usage limits. `python -m squad start --web` opens the browser version of the same thing.

`squad.config.json` can also list MCP servers under `mcpServers` (same shape as `.mcp.json`). They default to the bundled Jira, Confluence and workspace stand-ins; point a name at a real MCP server command to swap it. Relative commands are resolved from the config file's folder.

Limits to know: tests run with `pytest` using the squad's own Python, so a project whose tests need their own installed dependencies will fail QA; other test runners (npm, JUnit, go test) are not supported yet, and a project with no pytest tests simply skips the test step.

## Other commands

`run` and `eval` are dev tools that use a scripted model and the bundled demo tickets, so they work with no key.

```
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/python -m squad run PAY-482 --autonomy full
.venv/bin/python -m squad ask "What does this project do?"   # terminal version of the app (needs a model: Claude Code login or API key)
.venv/bin/python -m squad replay <path-to-trace.jsonl>
.venv/bin/python -m squad eval   # machinery check with the scripted model (not a quality result)
.venv/bin/python -m squad ui <path-to-trace.jsonl> --open   # game-style HTML replay
.venv/bin/pytest
```

The scripted model uses real MCP tools with canned decisions, so it proves the machinery and not model quality. Use `--autonomy manual|semi|full` to control approval gates.
