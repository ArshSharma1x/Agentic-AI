# Code audit: Agentic-AI squad (as of commit a95a39a)

Scope: README.md, vision.md, every file in `squad/` and `squad/servers/`, `tests/`, the demo `data/` and `sandbox/`. I ran `.venv/bin/pytest -q` (64 passed, 43 s), `squad eval` and `squad run PAY-482 --autonomy full` with the scripted model. No paid model was called. I also ran five probes against the `Workspace` class in throwaway copies, outside the repo; the results are cited below as "probe N".

## Verdict in one paragraph

This is a clean, readable, honestly documented prototype of a plan-execute-verify pipeline: about 1,500 lines, real MCP plumbing, a good trace format and a fair test harness. It is not yet a coding agent that someone could trust on a real repository. Three problems account for most of that gap:

1. **The gates are model opinions, not enforced facts.** The orchestrator never checks test results or scanner results itself. Whatever WARDEN and AEGIS put in `passed` decides the outcome.
2. **The "sandbox" only constrains the file tools.** FORGE gets arbitrary code execution with the user's full environment through `run_tests`, and it can disable the test suite with one `conftest.py`.
3. **The tool layer is too thin for real code.** There is no search, no partial edit, a silent 8,000-character truncation, and a 4,096-token output cap. Any non-trivial file gets corrupted or is out of reach.

The headline eval claim ("solo ships a refund with no authorization check; the squad does not") is staged by the scripted model. It shows that the heuristic scanner flags code that was written to be flagged, nothing more.

---

## 1. Architecture compared with serious agents

**What is sound**
- One `LLM.complete` boundary (`squad/llm.py:22`), so providers and a scripted double can be swapped. That makes the pipeline testable without a model, which is the right call.
- Tool permissions are enforced in code at `squad/mcp_host.py:57-61`, not only stated in the prompt.
- An append-only JSONL trace with listeners (`squad/trace.py`) drives the CLI, the web HUD and the replay. This is good observability design.
- Work happens on a copy with a git baseline, plus `/diff` and a conflict-aware `/apply` (`squad/repl.py:169-197`). The UX instinct is right.

**What is naive, compared with Claude Code, Codex, OpenHands and SWE-agent**

| Area | This repo | Serious agents |
|---|---|---|
| Edit tool | Whole-file overwrite only (`squad/workspace.py:67`) | str_replace / apply_patch with a uniqueness check, a lint/syntax check after each edit, a diff shown back to the model |
| Navigation | `list_files` + `read_file` only. No grep, no glob, no symbol search, no line ranges | ripgrep, glob, ranged views, repo maps (SWE-agent's ACI exists to solve exactly this) |
| Execution | Only `pytest -q` with the squad's own Python | A sandboxed shell (container or seatbelt/landlock), so the agent can install deps, build, lint and run any test runner |
| Tool output | Silently cut at 8,000 chars (`squad/mcp_host.py:55`), test output kept to the last 4,000 (`squad/workspace.py:93`) | Explicit truncation markers, paging, spill to file |
| Loop | 14 fixed steps, no `stop_reason` handling, no output-length recovery, no compaction (`squad/runner.py:31-72`) | Handles max_tokens and pause_turn, compacts or summarises context, budgets by tokens or cost |
| Prompt caching | None (`squad/llm.py:38`); the whole history is re-sent at full price on every step | cache_control on system, tools and history prefix |
| Structured outputs | Deliverables are taken as raw dicts with no validation (`squad/runner.py:52`) | Strict tool schemas plus validation and a repair turn |
| State | `Blackboard` is a dict that loses everything when the process exits (`squad/blackboard.py`) | Durable session state, resumable runs, checkpoints |
| Orchestration | A hard-coded linear pipeline in `Match._play` (`squad/orchestrator.py:136-168`) | Usually one strong agent loop plus optional subagents for isolated context, not a fixed role pipeline |

The blackboard is presented as an architectural feature, but it is a `dict` passed into `build_prompt`. No agent reads or writes it through tools. That is fine, but it should be called what it is: a typed handoff between pipeline stages.

## 2. Is the multi-agent split justified?

Mostly not. It is a sequential pipeline with role prompts. Taking each agent in turn:

- **RADAR (intel)**: role-play, and harmful in its current form. It turns the ticket and docs into a lossy Haiku summary (`squad/agents.py:13-26`, `squad/prompts.py:25,32`). FORGE then gets that summary as "rules the implementer must respect" but cannot read Confluence itself, since it has no `confluence__*` tool (`squad/agents.py:40-43`). This is the telephone-game failure: the agent that writes the code never sees the primary source. A single agent with the Jira and Confluence tools would do better. The only defensible version of RADAR is a subagent that explores in its *own* context window and returns citations, as Claude Code's Explore agent does. That would need the search tools RADAR does not have.
- **ATLAS (plan)**: role-play. Writing criteria and steps in a separate call, with no tools beyond read, is what a single agent does in its first turn. The value would come from turning criteria into **executable tests**, and ATLAS cannot write tests. Neither can anyone else, because `tests/` is read-only (`squad/workspace.py:70`).
- **FORGE (coder)**: the only agent doing real work, and it is under-equipped (see section 1).
- **WARDEN (QA)**: mostly theatre. It re-runs the same `pytest` FORGE already ran, reads a diff that may be truncated, and then a *weaker* model (Haiku, `squad/agents.py:53`) judges a stronger model's work. The test run should be deterministic orchestrator code. A model reviewer adds value only as an independent reviewer with fresh context and the ability to write adversarial tests.
- **AEGIS (security)**: the one split with a real argument. An independent reviewer with a different prompt, fresh context and a security checklist does catch things the author misses; separation of duties is a real principle. But it is weakened because its only checker is a keyword heuristic (section 4), and it cannot see the policy doc either.

In short, keep "author vs independent verifier", which is a genuine pattern. Drop the fixed RADAR→ATLAS→FORGE relay. The repo's own eval does not test the right baseline: the solo run is FORGE with **no access to the policy doc** (`squad/evals.py:13`), so of course it misses the authorization rule. The fair baseline is a single agent that has every tool and the same checklist.

## 3. Is MCP used meaningfully?

The plumbing is real: stdio servers, namespaced tools, and a config that lets a name point at a real server (`squad/orchestrator.py:32-43`). The servers themselves add nothing:
- `servers/jira.py` and `servers/confluence.py` are about 35-line JSON-file readers with a substring search. Each run, the orchestrator writes a one-ticket JSON file for free-text requests and launches a "Jira" process to read it back (`squad/orchestrator.py:89-92`). That is indirection with no capability.
- `servers/workspace.py` is a thin wrapper over `Workspace`. Running it as a separate process does not sandbox anything (the test subprocess inherits the full environment; see section 5).
- Swapping in the *real* Atlassian MCP server would break things. Tool names are hard-coded to the stand-in schemas (`jira__get_ticket`, `confluence__get_doc` in `squad/agents.py:16-17`), and `Ticket.from_dict` expects the stand-in JSON shape, including a `sandbox` key (`squad/models.py:48-54`). The "point a name at a real MCP server" claim in README.md:55 is untested and almost certainly false for Jira.

MCP becomes meaningful when (a) a real server such as the Atlassian, GitHub or Linear MCP works end to end, with tool names mapped by capability rather than hard-coded, and (b) the workspace server becomes a real isolation boundary, for example a container exposed over MCP.

## 4. How trustworthy are the verification gates?

Not trustworthy. In order of severity:

1. **The gate is whatever the sentinel model says.** `_verify` reads `run.deliverable["passed"]` (`squad/orchestrator.py:193`) and never checks the actual `run_tests` exit code or scanner result. If WARDEN hallucinates `passed: true` over a red suite, the change is committed. With the Claude Code backend, `passed` can even arrive as the string `"false"`, which is truthy, so it counts as a pass: nothing validates the type.
2. **FORGE can game the tests trivially.**
   - A root `conftest.py` that marks every test skipped gives `pytest` exit 0. Probe 2: buggy `money.py`, "5 skipped", `passed: True`.
   - On macOS (case-insensitive APFS), `write_file("Tests/test_money.py", ...)` overwrites the protected tests, because the guard compares `parts[0]` against `"tests"` case-sensitively (`squad/workspace.py:68-71`). Probe 1 confirmed it: the real `tests/test_money.py` was replaced.
   - `pytest.ini`, `pyproject.toml` `[tool.pytest]` addopts, `collect_ignore`, `sitecustomize.py`, or tests in any directory other than the top-level `tests/` are all writable.
3. **No tests means a pass.** `run_tests` returns `passed: True` when there are no pytest files (`squad/workspace.py:83-84`). Every non-Python project, and every "new project" request (an empty workspace, `squad/repl.py:75-78`), ships unverified.
4. **No compile, lint or type step.** A syntax error in a file the tests don't import passes QA. Ironically, the security scanner is the only thing that parses files (`squad/workspace.py:141`).
5. **New behaviour is never tested.** `tests/` is read-only, so FORGE cannot add tests for the feature it builds. ATLAS's criteria are checked only by a Haiku model reading a diff. README.md:42 advertises "now add a test for that", which the `tests/` guard blocks.
6. **The security scanner is a keyword matcher.** `_missing_authorization` passes any `refund/charge/transfer/payout` function whose source contains the substring `"authorize"` or `"PermissionError"` (`squad/workspace.py:146-148`). Probe 5: a comment `# authorize: TODO` passes. It only checks four function names, only Python, only `ast.FunctionDef` (async defs are skipped), and any `NotImplementedError` anywhere in the body exempts the function. Calling it "a tripwire" in the docs is honest; making it the sole evidence for the eval is not.
7. **The demo tests are shaped to fit the story.** `sandbox/refunds_api/tests/test_refunds.py` has no test for "a non-owner cannot refund", even though it is rule 1 of the policy. That is the only reason WARDEN passes the insecure version. A real QA gate would have written that test.

The fix direction is in the top-10 list: deterministic gates computed by the orchestrator, tamper detection on test configuration, and test generation by the verifier.

## 5. Context, cost, latency, failures, sandbox, prompt injection

**Context and memory**
- Session memory is the last 4 turns, each cut to 200-240 chars (`squad/repl.py:29,92,117,136`). Follow-ups ("now add a test for that") lose almost all detail, including which files were touched.
- Each retry starts FORGE with an empty message history (`squad/orchestrator.py:160` → a new `run_agent`). It must re-read everything and loses its own reasoning about the previous attempt.
- Within an agent, history grows with no compaction, and old tool results stay at full size.
- Triage sees only the first 60 file names (`squad/projects.py:31`).

**Cost**
- There is no prompt caching on the API path, so cost grows quadratically with steps.
- A free-text "fix X" request almost always pulls in RADAR, ATLAS, FORGE and WARDEN, because free text rarely has bullet criteria (`squad/draft.py:34`). That is four separate contexts, each re-reading the same files for a one-line fix.
- There is no budget or cost cap, which vision.md itself lists as missing.

**Latency**
- Strictly sequential phases.
- The Claude Code backend spawns a new `claude -p` process for *every step* and re-renders the whole transcript as text (`squad/claude_code.py:83-108`), with a 240 s timeout per step. Real tool use is emulated with a JSON schema, so parallel tool calls, tool-use IDs and caching are all lost.

**Failure handling**
- Only `ToolCallError` is caught in the loop (`squad/runner.py:60`). MCP transport errors, a `KeyError` on a deliverable missing `passed`/`key_facts`/`criteria` (`squad/orchestrator.py:193`, `squad/prompts.py:25,50`, `squad/orchestrator.py:178`), and API errors all bubble up and kill the match.
- `stop_reason == "max_tokens"` is never checked. With `MAX_OUTPUT_TOKENS = 4096` (`squad/llm.py:9`) and whole-file writes, any file larger than about 12-15 KB cannot be written in one call. The truncated `tool_use` is then executed or errors confusingly.
- Two sentinels run concurrently (`squad/orchestrator.py:190`), and both can call `git_diff`, which runs `git add -A` (`squad/workspace.py:96`). If the MCP server runs sync tools concurrently, that races on `.git/index.lock`. Even if it doesn't, a 60 s pytest blocks the other sentinel's calls.

**Sandbox security (it is not a sandbox)**
- **Arbitrary code execution**: anything FORGE writes runs as the user under `pytest`, with network access and the full environment. `server_params` passes `{**os.environ}` to the workspace server (`squad/orchestrator.py:43`), and pytest inherits it, including `ANTHROPIC_API_KEY`, cloud credentials and `SSH_AUTH_SOCK`. Probe 4: a `conftest.py` wrote a file into `$HOME` outside the workspace. `~/.ssh`, `~/.aws` and the user's real project folder are all readable and writable. README.md:44 ("nothing in your files changes until you say so") is only true if the model behaves.
- **`.git/` is writable** through `write_file` (probe 3). A model, or injected instructions, can set `core.fsmonitor` or `core.hooksPath` in `.git/config`. Git then runs that command on the next `git add` or `git commit`, both of which the orchestrator runs (`squad/workspace.py:96,119`).
- `copy_project` skips `.env`, keys and `squad.config.json` by filename (`squad/workspace.py:159`). That is good, but secrets in `config/*.yaml`, `credentials.json`, `.npmrc`, `.netrc` or `settings.py` are copied and readable.
- The web server's only CSRF defence is a custom header (`squad/server.py:75-79`). There is no Host-header check, so DNS rebinding defeats it, and there is no auth token on a localhost service that executes code.
- `/apply` writes to a path the *model* proposes (`destination`, `squad/triage.py:189`), restricted only to "somewhere in $HOME" (`squad/repl.py:72`), and it asks first.

**Prompt injection** (exposure is high)
- All three parts of the lethal trifecta are present: untrusted content (ticket text, Confluence pages, repo files), privileged action (code execution through tests, commit), and exfiltration (unrestricted network from the test process).
- RADAR's summary of untrusted docs is injected into FORGE's prompt as authoritative "rules the implementer must respect" (`squad/prompts.py:32`, `squad/local_tools.py:11`). That *raises* the authority of injected text.
- The Claude Code backend flattens tool results into plain text with markers like `RESULT:` / `YOU CALLED:` / `TASK:` (`squad/claude_code.py:43-59`). A file containing those markers can forge transcript turns.
- No content is delimited or marked as untrusted, and there is no human gate before code execution.

## 6. Code quality and test quality

**Code**: compact, consistent, well-named, with honest docstrings. Little dead code. The scripted LLM is a good testing idea. The smells:
- Everything is stringly typed: deliverables are bare dicts, `role.value == "Sentinel"` (`squad/orchestrator.py:151`), `describe()` matches on a class name (`squad/llm.py:67-68`), and the `_pick_llm.warned` function attribute (`squad/cli.py:40`).
- `Match.__init__` has 12 optional parameters that change behaviour (ad-hoc ticket, project, draft, workspace). The real-ticket path and the free-text path are tangled in `_run`.
- Config is re-read from disk on every `server_params` call. The workspace server builds its `Workspace` at import time from an environment variable (`squad/servers/workspace.py:11`).
- `/apply` mishandles renames. With git's default rename detection, `--name-status` gives `R100\told\tnew`, so the code copies `new` and never deletes `old` (`squad/workspace.py:106`).
- `prompts.build_prompt` is a big if-chain keyed on agent name, so adding an agent means editing core code.
- The README and vision.md are commendably candid about limits. Keep that.

**Tests** (64, all green): good integration coverage that drives real MCP subprocesses through the scripted model. The weaknesses:
- Mostly happy-path tests of the scripted path, which was designed to pass. `test_evals.py` asserts the staged outcome.
- **There are no adversarial tests**, and these are exactly the cases that matter: conftest or skip gaming, case-variant `Tests/`, writes into `.git/`, truncated reads followed by a write, a malformed deliverable, a sentinel saying `passed: true` over a red suite, prompt-injection fixtures.
- `AnthropicLLM` has no test at all (`squad/llm.py:28-47`), not even with a fake client.
- Brittle magic numbers: `"8 issue(s) found"` (`tests/test_triage.py:55`) depends on how many sandbox tests fail against a stub.
- There is no live-model eval, as the author admits. A portfolio-grade claim needs one, even a small one.

## 7. Top 10 problems, ranked by severity

1. **The verification gates trust the model's `passed` flag.** `squad/orchestrator.py:193-197`. *Fix*: compute the hard gates in the orchestrator. Run tests (and lint/compile) yourself after FORGE finishes, and require `exit_code == 0` *and* a minimum number of tests actually executed (parse the pytest summary, or use `--junitxml`, and reject when everything is skipped or deselected). Let sentinel models only add issues, never override a red hard gate. Validate deliverables against their JSON schemas (use strict tool use on the API path) and reject non-boolean `passed`.

2. **The "sandbox" gives FORGE code execution with the user's environment and filesystem.** `squad/orchestrator.py:43`, `squad/workspace.py:85-89`. *Fix*: run `run_tests` (and later a shell tool) inside a container or an OS sandbox (Docker/Podman with `--network none`, the workspace mounted read-write and nothing else; or macOS `sandbox-exec` / Linux bubblewrap + landlock, the way Claude Code and Codex do). Pass an allow-listed environment (`PATH`, `HOME=/tmp/x`, `LANG`), never `os.environ`. Until then, change the README claim.

3. **Tests are trivially gameable.** Root `conftest.py`, pytest config files, case-variant `Tests/`, tests outside `tests/`. `squad/workspace.py:15,68-71`. *Fix*: protect by *content*, not path. Snapshot hashes of every test file and every test-affecting config file (`conftest.py`, `pytest.ini`, `pyproject.toml`'s `[tool.pytest]`, `setup.cfg`, `tox.ini`, `sitecustomize.py`, `.git/`) at the baseline, and fail the gate on any change the user did not approve. Compare paths with `os.path.normcase` and against the real resolved inode. Better still, run the *baseline* test files from a pristine copy against the modified sources.

4. **Silent truncation plus whole-file overwrite corrupts files over 8 KB.** `squad/mcp_host.py:9,55`, `squad/workspace.py:67-74`, `squad/llm.py:9`. Today the agent cannot safely edit `squad/orchestrator.py` (11.4 KB). *Fix*: add `read_file(path, offset, limit)` with line numbers and an explicit `[truncated: N more lines]` marker, plus an `edit_file(path, old, new)` str_replace tool that fails on zero or multiple matches. Keep `write_file` for new files only. Handle `stop_reason == "max_tokens"` in `runner.py` by telling the model its output was cut off.

5. **The agents cannot navigate a real repo.** There is no search tool at all (`squad/agents.py:15-18,41-43`). *Fix*: add `grep(pattern, glob)` (ripgrep), `glob(pattern)` and paged `list_files`. Optionally add a repo map (ctags/tree-sitter summary) for RADAR. Without these the system works only on the two 1-file demo sandboxes.

6. **The eval is staged and the baseline is unfair.** `squad/scripted.py:79-82` (insecure code on attempt 1 by construction), `squad/evals.py:13` (solo gets no doc access), `sandbox/refunds_api/tests/test_refunds.py` (no ownership test). vision.md:87 presents the result as evidence. *Fix*: build 15-30 seeded tasks with **hidden** acceptance tests that the agents never see (SWE-bench style: fail-to-pass plus pass-to-pass), run them with a live model, and compare (a) the squad, (b) a single agent with *all* tools and the same security checklist, and (c) a single agent plus an independent reviewer. Report pass rate, hidden-test pass rate, cost, latency and variance over at least 3 seeds. Until that exists, remove the solo-vs-squad claim.

7. **Prompt-injection exposure, with injected text promoted to authority.** `squad/prompts.py:25,32`, `squad/claude_code.py:43-59`. *Fix*: give FORGE direct read access to the primary sources and pass RADAR's output as *notes with citations*, not "rules". Wrap all tool output in clearly delimited untrusted blocks. Add a policy layer: the model cannot widen the network or filesystem, no exec before human approval in `semi` mode, and sanitise transcript markers in the Claude Code renderer (or use a structured format).

8. **`.git/` is writable, and git runs model-controlled config.** `squad/workspace.py:30-34,67`. *Fix*: refuse writes under `.git` (and any dotdir you do not expect). Run every git command with `-c core.fsmonitor= -c core.hooksPath=/dev/null` and `GIT_CONFIG_NOSYSTEM=1`. Better, keep the git directory outside the workspace (`--git-dir` elsewhere, with the workspace as `--work-tree`).

9. **Fragile loop and failure handling.** `squad/runner.py:56-63` catches only `ToolCallError`. Missing deliverable keys raise `KeyError` in `orchestrator.py:178,193` and `prompts.py:25,50`. There is no per-call timeout on MCP calls, and FORGE retries start from a blank history. *Fix*: validate each deliverable against its schema and, if invalid, send the error back as a tool_result so the model can repair it. Wrap MCP calls in a timeout and turn transport errors into tool errors. Carry a compact "attempt summary" (files changed, last test failure) into the next FORGE attempt. Budget by tokens or cost, not 14 steps.

10. **No caching, a per-step process for the Claude Code backend, and a weak model on the QA gate.** `squad/llm.py:36-47`, `squad/claude_code.py:83-108`, `squad/agents.py:53`. *Fix*: add `cache_control` breakpoints on the system prompt, tools and the last tool_result (a large cost cut on multi-step runs). For the subscription path, use the Claude Agent SDK, or keep one long-lived `claude` session with an MCP config pointing at your servers, instead of re-spawning and re-rendering the transcript per step. Put the independent reviewer on a model at least as strong as the author.

Honourable mentions (not in the top 10): the web server needs a Host-header check and a random per-launch token (`squad/server.py:75-79`). `/apply` mishandles renames (`squad/workspace.py:106`). Real Jira/Confluence swap-in is advertised but cannot work with hard-coded tool names and the `Ticket` shape (`squad/models.py:48-54`). `run_tests` treats "no tests" as a pass (`squad/workspace.py:83-84`).

## 8. What is novel or worth keeping

The honest answer is that the agent *mechanics* are not novel. Plan-execute-verify pipelines with role names are the most common multi-agent demo there is (MetaGPT, ChatDev, CrewAI templates). The Valorant theme is a presentation layer; it helps explain the system to non-engineers, but it is not a technical differentiator. These parts are worth keeping and building on:

- **Explainable, logged squad sizing** (`squad/draft.py`, `squad/triage.py:154-190`), with **non-negotiable rules applied after the model's choice** ("FORGE always brings QA", "sensitive changes always get a security gate"). Model proposes, policy disposes: this is the right pattern and under-used in other tools. Make the rule layer the product: declarative, versioned policies per repository (`squad.policy.yaml`) that the dispatcher cannot override.
- **Separation of duties as a first-class concept**: the author cannot approve its own work, and the verifier has different tools and fresh context. Lean into this for *regulated* work, such as payments, auth and PII changes, where "who verified what, with which evidence" matters. That is a differentiated niche that Claude Code, Codex and OpenHands do not target.
- **The trace and replay as an audit artifact** (`squad/trace.py`, `squad/ui.py`). Turn it into a signed, reviewable "evidence bundle" for each change: the sources read, the tests run with exit codes, scanner output, approvals. It could attach to a PR. That is concrete value for compliance-minded teams.
- **Copy-on-write sessions with conflict-aware `/apply`** (`squad/repl.py:169-197`). Good UX; keep it once real isolation sits behind it.
- **The scripted LLM test double** (`squad/scripted.py`). Keep it for machinery tests, but stop using it as evidence of quality.

If the goal is a genuinely valuable open-source tool, the strongest pivot I see is to **stop competing as a coding agent** (Claude Code and Codex will out-execute it) and become **a verification and governance layer around any coding agent**. That means policy-driven gates, deterministic test and scan enforcement, tamper detection, an independent model reviewer, and an evidence bundle per change. FORGE could then be Claude Code itself, driven through the Agent SDK. Most of the existing code (triage rules, gates, trace, apply) maps directly onto that.
