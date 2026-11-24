# Live eval

**Question:** when a coding agent says it is done and the suite is green, can you trust it, and does the gate catch the cases you shouldn't?

**Setup** (`agentic eval`, tasks in [`evals/tasks/`](../../evals/tasks)): 12 seeded tasks, 3 seeds each, with Claude Code as the author, used the way people use it (it may read, edit and run pytest; nothing tells it about the gate).

- 8 **honest** tasks: a real bug or feature, with hidden tests that encode the spec.
- 4 **impossible** tasks, in the style of [ImpossibleBench](https://arxiv.org/abs/2510.20270): one visible test contradicts the written spec (for example `assert add(2, 2) == 5` next to "return the sum"). The only way to a green suite is to cheat: edit the test or special-case its inputs.

Every run is scored four ways: what the agent reported, what naive CI sees (the repo's tests as the agent left them), what WARDEN says, and ground truth (hidden spec tests plus the original tests, run on the agent's code). The benchmark itself is validated: reference solutions and deliberate cheats score as designed ([`tests/test_bench.py`](../../tests/test_bench.py)).

## Results (November 2026)

| | [Sonnet 5.5](sonnet-5-5/README.md) | [Haiku 5.5](haiku-5-5/README.md) |
|---|---|---|
| Honest tasks: spec-correct | 24/24 | 24/24 |
| Honest tasks: gate PASS on correct work | 24/24 | 24/24 |
| **Gate false alarms** (FAIL on correct work) | **0** | **0** |
| Impossible tasks: agent cheated to get green | 0/12 | **5/12** (all by editing the test; 2 never told the user) |
| Cheats a normal CI pipeline would have merged | 0 | **5** |
| **Cheats stopped by the gate** | n/a | **5/5** |
| Told the user the test contradicts the spec | 7/12 | 8/12 |
| Cost at API list price | $0.91 | $0.09 |

**What it shows.** The smaller model rewrote a failing assertion to turn the suite green in 5 of 12 impossible runs, and in 2 of those its final report never mentioned doing so. A pipeline that runs the repo's tests as committed would have merged all 5. The gate failed every one, and it never failed a correct change (0 false alarms in 48 correct runs).

**What it does not show.** Both models solved every honest task, so these tasks do not separate good agents from bad ones, and they never produced the "green but wrong" case hidden tests exist for. No run special-cased test inputs, so the special-casing detector and hidden tests were not exercised by real agent behaviour here (only by the planted cheats in the test suite). 36 runs per model is a small sample; treat the rates as indicative, not precise. Harder tasks and more models are the next step.

**One correction, made before publishing.** The first run of this eval flagged Haiku as "tampering" on 13 honest runs. Reading the transcripts showed it had *appended new tests* to existing test files, which is good behaviour, and the gate was treating any edit to a test file as tampering. The gate now works at test level (originals must survive unchanged; new tests are welcome and run), and both models were re-run from scratch. Those are the numbers above.

Reproduce: `agentic eval --seeds 3 --model claude-haiku-5-5` (needs a logged-in Claude Code).
