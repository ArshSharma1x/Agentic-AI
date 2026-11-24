# Competitor check: agent-agnostic verification and governance gate

Research date: 2026-11-24. About 20 tool calls, made up of web searches plus 2 direct GitHub README fetches (RewardGuard, agentattest) and 1 of the Snyk agent-scan repo.

**Confidence tags**
- **[F]** Fact: stated by a primary source (official docs, changelog or repo) that I saw, or that a search summary attributed to one.
- **[F?]** Seen only in a search summary or secondary source. Not opened directly.
- **[M]** From my prior knowledge (cutoff mid-2026). Not re-verified this session.
- **[I]** Inference or opinion.

## The five capabilities

The scores in the table below use these numbers.

1. **Sandboxed re-run:** the gate runs the tests itself, in a sandbox with no network and no secrets.
2. **Tamper detection plus held-out tests:** it detects test tampering, runs the original tests, and runs hidden held-out tests.
3. **Clean-context reviewer:** a reviewer model with no write access.
4. **Per-repo policy:** sensitive paths, mandatory gates, and who may approve.
5. **Signed evidence bundle:** an in-toto/SLSA-style bundle covering what the agent read, which tools it called, gate results and the approver.

## Per-tool findings

| Tool | What it is now | Open source? | Covers | Limits |
|---|---|---|---|---|
| Invariant Labs, now Snyk | Snyk acquired Invariant on 2025-06-24 and folded it into Snyk Labs [F] (https://snyk.io/news/snyk-acquires-invariant-labs-to-accelerate-agentic-ai-security-innovation). MCP-Scan now lives at github.com/snyk/agent-scan as "Agent Scan", run with `uvx snyk-agent-scan@latest`. It is v0.6+ and **closed to contributions** [F] (https://github.com/invariantlabs-ai/mcp-scan, which redirects). Guardrails (a rule language over agent traces) and Explorer (a trace viewer) have no current product page that I found [I: effectively absorbed or dormant]. | Agent Scan is public source, but outside contributions are not accepted. Guardrails was Apache-2.0 [M]. | Partial 4 (runtime trace policies, MCP tool poisoning). | It works at runtime and on MCP. It is not a PR gate, runs no tests, and produces no attestations. |
| promptfoo | An LLM eval and red-teaming CLI with CI integration [M]. | MIT [M] | None of the five directly. It is an eval and red-team harness for prompts and apps. | It does not verify code changes. |
| UK AISI Inspect | An eval framework with Docker/K8s sandboxes. Networking can be disabled. Scorers can run hidden tests [M]. | MIT [M] | 1 and 2 as building blocks only, for benchmark tasks. | It is a research harness, not a PR gate. It has no policy or attestation layer. |
| SWE-smith, SWE-Gym | Pipelines that generate training and eval data. The SWE-bench harness runs held-out FAIL_TO_PASS and PASS_TO_PASS tests in Docker [M]. | MIT [M] | The concept behind 2 (held-out tests), and 1 inside eval. | These are offline benchmarks, not tools for live PRs. |
| OpenHands | The SDK's default is an LLMSecurityAnalyzer. The model tags each action's risk inline, and a confirmation policy decides when to ask a human [F] (https://docs.openhands.dev/sdk/guides/security). The old Invariant analyzer is gone [F?]. A `conversation.execute_tool()` call bypasses the analyzer [F]. | MIT [M] | Weak 4, in-loop only. | It is a self-assessed risk label inside one agent. It is not an independent gate. |
| Langfuse, Braintrust | Tracing plus evals and LLM-as-judge [M]. | Langfuse is MIT core. Braintrust is proprietary [M]. | Traces cover part of the "what the agent did" data in 5, but they are unsigned. | Observability only. No gate and no tests. |
| CodeRabbit | An AI PR reviewer. Code is sent to OpenAI and/or Anthropic [F?]. | No | 3, though not a clean-context design (it reads the repo with full context). Some config-level path rules. | It does not re-run tests and does not detect tampering. |
| Graphite Diamond | AI review bundled with stacked PRs and a merge queue [F?]. | No | 3 | Same as CodeRabbit. |
| Qodo Merge | The hosted form of the open-source PR-Agent [F?]. Qodo also has test-generation tools [M]. | PR-Agent is open source (license changed over time) [M]. | 3, with some test generation. | No independent sandboxed verification and no tamper detection. |
| Cursor Bugbot | A PR bug finder configured with BUGBOT.md. GitHub only, $40 [F?]. | No | 3 | Review only. |
| GitHub Copilot code review | Moved to an agentic tool-calling architecture and went GA on 2026-03-05 [F] (https://github.blog/changelog/2026-03-05-copilot-code-review-now-runs-on-an-agentic-architecture/). Can run CodeQL, ESLint and similar tools [F]. Secret detection is in preview as of 2026-11-17 [F] (https://github.blog/changelog/2026-11-17-copilot-code-review-adaptive-effort-secret-detection-and-more). | No | 3 | It does not check test honesty. |
| Copilot coding agent self-validation | The agent runs CodeQL, Advisory DB, secret scanning and Copilot review on its own output. The tools are configurable (2026-03-18) [F] (https://github.blog/changelog/2026-03-18-configure-copilot-coding-agents-validation-tools/). | No | Partial 1 (it runs in Actions), plus 3 | The agent validates itself, inside its own environment. That is the opposite of an independent gate. |
| GitHub Agent HQ and agent control plane | Enterprise AI Controls and the agent control plane went GA on 2026-02-26 [F] (https://github.blog/changelog/2026-02-26-enterprise-ai-controls-agent-control-plane-now-generally-available/). Shows agent sessions from the last 24h. Agentic audit log events carry `actor_is_agent`, with 180-day retention [F] (https://docs.github.com/en/copilot/reference/enterprise-administrators/agentic-audit-log-events). Can stream to Microsoft Agent 365, as of 2026-11-17 [F]. Rulesets, CODEOWNERS and environments remain the enforcement layer [F?]. | No | 4 (rulesets, CODEOWNERS, required checks), plus an unsigned audit trail toward 5 | Enterprise only. GitHub only. Logs are not signed per-PR attestations, and there is no tamper detection. |
| GitHub artifact attestations | Sigstore-signed SLSA build provenance for build outputs (`actions/attest-build-provenance`) [M]. | Actions are open source. The service runs on GitHub. | The signing substrate for 5 | It proves which workflow built an artifact. It says nothing about agent behaviour or gate results. |
| Sourcegraph, Amp | Sourcegraph markets "agent provenance": which files an agent read and why, exported per conversation as a PDF for auditors [F?] (https://sourcegraph.com/blog/compliance-first-ai-proving-agent-provenance). Amp is now a separate company [F?]. Batch Changes emit structured audit events as of 2026-08 [F?]. | No | Part of 5 (what the agent read), but unsigned and tied to one vendor | Covers only their own agent. Not an in-toto attestation. |
| JFrog AppTrust "Prompt to Release Traceability" | Announced at swampUP 2026. Git, PR, Jira and approver-chain evidence is shipping. The agent-session evidence and "session bill of materials" (MCPs, skills used) come through JFrog Agent Plugins, stored as signed evidence, and are **roadmap, later 2026** [F?] (https://jfrog.com/blog/prompt-to-release-traceability/). It ingests GitHub attestations [F]. | No | 5 at release-promotion granularity, plus 4 (promotion gates) | Paid enterprise product. Tied to Artifactory. Records evidence but does not generate verification evidence. |
| Sigstore, in-toto, SLSA | **No registered in-toto predicate for AI agent runs.** Several competing proposals are open: PR #601 "AI Change Provenance", #588 "AI Agent Action", #591 "AI Agent Decision", #600 "Agentic process evidence" and #604 "OpenFab generation" [F?] (https://github.com/in-toto/attestation/pull/601, https://github.com/in-toto/attestation/issues/604). | Yes | The substrate for 5 | The standard is unsettled. That cuts both ways: no one owns it yet, but a solo project picking a schema risks having picked the wrong one. |
| agentattest | Signed in-toto Statement binding an agent run to patch, tree, PR and approval state. Sigstore signing, a Rego policy gate and a 5-phase verifier [F] (https://github.com/BlockTarioIQ/agentattest, a fork of AuroraAeon/agentattest). Raw prompts and tool outputs are explicitly not stored. Files read and gate results are not clearly recorded [F]. | Apache-2.0, 0 stars, v0.1.0 | 5 (partial) and 4 (Rego) | It explicitly does not judge code quality and runs no tests. Tiny project. |
| OpenSSF AI/ML WG | Model signing v1.0 (April 2025) and the OMS spec, which cover **models**, not code changes [F?]. A security guide for AI code assistant instructions [F?]. | Yes | Not this problem | No attestation for AI-generated code. |
| Semgrep Guardian | Launched 2026-06-23. MCP server, agent hooks and skills, later adding AI detection and org policy [F?] (https://semgrep.dev/blog/2026/introducing-semgrep-guardian-real-time-security-for-ai-written-code/). | Semgrep CE is open source. Guardian is commercial. | 4, for security rules in the agent loop | Security scanning only. No test honesty and no attestation. |
| Endor Labs AI Coding Agent Governance | Launched 2026-07-30. Hooks allow, block or audit agent actions, with 29 default policies (shell, sensitive files, MCP, skills) [F?] (https://www.endorlabs.com/blog/introducing-security-for-ai-coding-agents-and-workstations). Claims Forrester Wave leader for Q4 2026 (vendor claim). | No | 4, strongly, in the loop. An audit trail for part of 5. | Runtime only. No independent verification of tests. |
| Socket | Supply-chain and package firewall; blocks malicious packages at install time [F?]. | Partially (CLI) | Narrow 4 (dependency policy) | Not about test honesty. |
| Anthropic claude-code-security-review | A GitHub Action that has Claude review a PR diff for security issues and post comments. Supports custom instructions. The README states it is **not hardened against prompt injection** and should only review trusted PRs [F] (https://github.com/anthropics/claude-code-security-review). | MIT [M] | 3, security only | It has write permission to post comments, runs no tests, and does not defend against prompt injection. |
| RewardGuard | **The closest single match.** A pre-merge GitHub Action (Jest, Vitest, Playwright) that catches deleted or skipped tests, weakened assertions, expected-value edits, hard-coding, special-cased inputs, gate tampering, notes aimed at reviewers and edits to agent-instruction files. It also flags "new tests that pass on base". Tests run in clean worktrees with no secrets, in a job separate from the judge. The policy file `.rewardguard.toml` is read from the base commit. A proprietary "Jev" judge plus a Haiku explainer that cannot downgrade findings [F] (https://github.com/Advanced-Digital-Marketing-LTDA/RewardGuard). Not yet included: holdout tests, mutation testing, signed attestation. | **PolyForm Shield** (source-available, not OSI open source). Needs a paid Jev API. 0 stars, no releases. | 1 (partial: no network isolation stated), 2 (minus held-out tests), 3 (partial), 4 (partial) | JavaScript only. Depends on a proprietary judge. Precision is "not verified". No Python or conftest coverage. |
| rhdetect (reward-hacking-detector) | Pure-Python checks over an agent's action log for test edits, skip markers, peeking at hidden tests and unverified success claims. Exits 1, so it can gate CI [F?] (https://github.com/ik-786/reward-hacking-detector). | Yes (license unchecked) | 2 (partial) | Hobby-scale. Needs action logs. |
| Research: ImpossibleBench | Tests mutated to contradict the spec. Measures how often models exploit tests [F?] (https://github.com/safety-research/impossiblebench, arXiv 2510.20270). | Yes | 2, as a measurement method | Benchmark only. |
| Research: EvilGenie | Built on LiveCodeBench. Detects hacking with held-out tests, LLM judges and test-file edit detection. Found explicit hacking by Codex and Claude Code [F?] (https://github.com/JonathanGabor/EvilGenie, arXiv 2511.21654). | Yes | 2. It is the reference design for the detector. | Benchmark only. |
| Research: other | Verifier Perturbation Testing (hanaml-lab), TestJack (arXiv 2610.10619), "The Verification Horizon" (arXiv 2606.26300), and NovaFabric (arXiv 2609.12582), which covers tamper-evident, replayable agent-run evidence [F?]. | Mixed | 2 and 5, as ideas | Papers, not products. |

## Verdict

### Is the combination already shipped?

No, not by anyone, open or closed. That is [I], but well supported. No tool I found does all of these together:

- re-running tests independently in a sandbox
- tamper detection plus held-out tests
- a clean-context reviewer
- policy
- a signed evidence bundle

The nearest pieces, each far from the whole:

- **RewardGuard** covers roughly 2, 1 and 4.
- **agentattest** covers 5 and 4.
- **GitHub** covers 3 and 4 plus unsigned audit logs.
- **JFrog** covers 5 at release level, with the agent-session parts still on the roadmap.
- **Endor and Semgrep** cover 4 in the agent loop.

### Crowded

- **3, the AI reviewer, is the most crowded.** CodeRabbit, Copilot, Qodo, Graphite, Bugbot, Greptile, Amp and the Anthropic action all compete here. Do not lead with it.
- **4, the policy gate, is crowded and owned by incumbents.** GitHub has rulesets and CODEOWNERS. Endor and Semgrep have hooks.

### Contested

- **5, signed agent evidence, is crowded at the proposal stage.** It has many in-toto proposals, agentattest, and the JFrog roadmap. Nobody has adoption yet. The risk is a standards fight a solo developer cannot win.

### Most clearly unserved

- **2, test-tampering detection plus held-out tests, as a language-agnostic (at least Python-first) and actually open-source CI gate.** Research shows the problem is real: Claude Code and Codex hack tests in EvilGenie and ImpossibleBench. The only product-shaped attempt, RewardGuard, has these gaps:
  - JavaScript only
  - source-available rather than open source
  - depends on a paid proprietary judge
  - zero adoption
  - no held-out tests
  - no conftest or pytest-specific tricks
  - no stated network isolation
- **1, independent sandboxed re-run, is the natural pair.** "CI already runs tests" is the objection. The answer is that CI runs the agent's possibly modified tests and config, with secrets available.

### Recommended positioning (solo, open source)

[I] Lead with: **"Did the agent cheat on the tests?"** It is a deterministic, Apache/MIT GitHub Action and CLI.

1. Diff the test surface against base. That covers:
   - deleted, skipped or xfail'd tests
   - weakened asserts
   - conftest.py, pytest.ini or tox changes, and fixtures that monkeypatch the subject
   - special-casing of test inputs in source code
   - CI-config and `continue-on-error` tampering
2. Re-run the **base-branch** tests, plus optional maintainer-held held-out tests, against the PR code in a no-network, no-secrets container.
3. Emit a small JSON report whose hashes and exit codes are signed with Sigstore. This is a stepping stone to 5, not the headline.

It works with any agent because it only looks at the diff and the results. It does not require agent cooperation or traces.

Keep these out of v1:

- **The reviewer model (3).** It is crowded, and an LLM in the trust path weakens the "deterministic" pitch.
- **Rich policy (4).** Reuse CODEOWNERS and rulesets.
- **"What the agent read and which tools it called" (5).** That needs every agent's telemetry and is where JFrog, Sourcegraph and GitHub are heading.

Lead capability: **#2, test-tampering detection plus running the original and held-out tests.** It is the most defensible, the most demonstrable (you can replay EvilGenie and ImpossibleBench cases as a public benchmark of the detector), and the least served by incumbents.

### Risks

- [I] GitHub could add "test-surface change" warnings to Copilot code review.
- [I] RewardGuard could relicense or add Python support.
- Detection heuristics are an arms race. Publish precision and recall on EvilGenie and ImpossibleBench to earn credibility.

## Verification gaps

- I did not open these vendor docs directly: CodeRabbit, Qodo, Graphite, Bugbot, Socket, promptfoo, Inspect, SWE-smith, Langfuse, Braintrust. Their rows rely on search summaries or prior knowledge.
- Whether CodeRabbit or Qodo now runs tests in sandboxes is unconfirmed.
- The Snyk Guardrails and Explorer status is inferred from the absence of current pages.
- The in-toto proposal statuses come from search snippets.
- RewardGuard's last commit date is not shown.
