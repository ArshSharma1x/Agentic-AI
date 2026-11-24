# Vision

**Coding agents write code. Nobody checks their work in a way a skeptic would accept. Agentic-AI is the squad that does.**

## The problem

By late 2026 every serious vendor ships a capable coding agent (Claude Code, Codex, Cursor, Copilot, Devin, opencode). They compete on the same surfaces and the same models. What none of them gives you is evidence:

- **Agents game verification.** Research measures it directly: agents edit or delete tests, special-case test inputs, and exit early with a success code. A single `conftest.py` can turn a red suite green.
- **Review is a model's opinion.** Vendor review bots are another model saying "looks good", inside one vendor's product, with no record an outsider can check.
- **Agents run with too much power.** The 2026 prompt-injection incidents (Clinejection, Comment and Control, GitLost) all routed untrusted issue or PR text into an agent that held secrets and network access.
- **Nobody can answer the auditor.** What did the agent read? Which tests ran, and were they the original tests? Who approved the merge?

Developer trust in AI output fell from 40% to 29% between 2024 and 2025, even as usage rose. The bottleneck is no longer generating code. It is trustworthy evidence that the code is right.

## What we build

A **verification gate** that sits between "the agent says it's done" and "a human merges". It works with any author agent, and every gate decision is computed by code, never by a model's say-so.

The squad keeps its Valorant names, but each one is a real job, not a persona:

| Agent | Job | How |
|---|---|---|
| **FORGE** (Duelist) | The author. Writes the change. | Pluggable: our built-in agent, or Claude Code, Codex, any agent that leaves a diff |
| **WARDEN** (Sentinel) | The deterministic gate | Runs the *original* tests (plus hidden ones the author never saw) in a sandbox; detects tampering; compile and lint checks; verdict PASS, FAIL or UNVERIFIED |
| **AEGIS** (Sentinel) | The independent reviewer | A fresh-context model with no write access that sees only the diff and the evidence. It can add findings; it can never overturn a red gate |
| **RADAR** (Initiator) | Read-only explorer | Gathers cited context. Its notes are marked untrusted, never "rules" |

The dispatcher still sizes the squad per request, and policy rules still override the model ("model proposes, policy disposes"): nothing ships without WARDEN, and sensitive paths always get AEGIS.

## Principles

1. **Facts over opinions.** A gate result is an exit code, a test count and a hash, not a model's `passed: true`.
2. **The author never grades itself.** Separation of duties: the agent that wrote the code cannot change the tests that judge it, and the reviewer cannot write code.
3. **Least privilege by construction.** No single role holds untrusted input, secrets and a network connection at once.
4. **Evidence travels with the change.** Each verified change carries a record of what ran, on which inputs, with which result, that someone else can check.
5. **Say only what the code backs.** Every claim in this repo should be reproducible by a test or a command.

## Status

| Phase | Work | State |
|---|---|---|
| P0 | Remove unbacked claims; adversarial tests for every audit finding | Done |
| P1 | Deterministic gate computed by code; "no tests" is UNVERIFIED | Done (`squad/gate.py`) |
| P2 | Test integrity: tamper detection, pristine and hidden tests, baseline comparison, protected `.git` | Done |
| P3 | OS sandbox (Seatbelt / bubblewrap): no network, no home directory, allow-listed env; untrusted-content handling | Done (`squad/sandbox.py`) |
| P4 | Pluggable author (Claude Code as FORGE) and `agentic verify` for any agent's change | Done |
| P5 | Per-repo policy from the base commit; in-toto evidence signed in CI; GitHub Action; this repo gates its own PRs | Done |
| P6 | Live eval with hidden and impossible tasks, measuring what naive CI misses and what the gate catches | Done ([docs/eval](docs/eval/README.md)); harder tasks next |

Known limits, stated plainly:

- Only pytest suites are run. Other languages get compile checks (Java, JavaScript, JSON) and are otherwise UNVERIFIED.
- Special-casing a test's exact inputs is caught by a structural detector (UNVERIFIED) and by hidden tests; subtler overfitting needs hidden tests.
- On a machine with no OS sandbox the gate still runs, and the evidence says `sandbox: none`.

The research behind this direction is in [docs/research/](docs/research/agentic-ai-landscape-and-gaps.md).

## What we will not claim

- The old "squad beats solo" eval used a scripted model and an unfair baseline. It is not evidence, and it is not presented as such.
- Multi-agent is not a goal in itself. The evidence says extra agents mostly add cost; the only split we keep is the one that buys independence (author versus verifier).
