# AI Coding Agents Landscape (as of late November 2026)

Research date: 2026-11-24. Source quality warning up front: the per-agent comparison data for late 2026 comes mostly from third-party aggregators (Morph, amux, Codesota, dev.to), because vendor pricing and leaderboard pages often did not render when fetched. Morph sells its own coding models, so it has a commercial interest. Model names such as "Opus 5.5", "Fable 5", "GPT-5.6 Sol", "GPT-6 Astra" and "Muse Spark" appear in these sources. Where only one aggregator reports a number, it is marked as such.

## Per-agent architecture, interfaces, extensibility, pricing/license

### Takeaway
By late 2026 every major vendor ships the same set of surfaces: terminal CLI, IDE, cloud/background agent, and PR review. The real differences are the default model, how usage is billed (subscription caps vs BYOK vs credits), and the license. Consolidation is the main structural trend: Windsurf became Devin Desktop (June 2, 2026), GitHub Agent HQ hosts third-party agents inside Copilot, and Cursor acquired Continue.dev.

### Cited Findings
**Claude Code (Anthropic)**
- Terminal-native. Also available in VS Code, JetBrains, a desktop app and the web. Supports MCP, sub-agents, background and cloud sessions, CLAUDE.md memory, hooks and skills — [Morph, updated Oct 6 2026](https://www.morphllm.com/ai-coding-agent)
- Included in Claude Pro at $20/mo ($17 annual), and in Max at $100 (5x) or $200 (20x). Usage is capped by a 5-hour rolling window plus a weekly cap, both shared with claude.ai — [Morph](https://www.morphllm.com/ai-coding-agent); [amux pricing 2026](https://amux.io/blog/ai-coding-tools-pricing-2026/)
- Proprietary. The GitHub repo has about 142k stars but no open-source license — [Morph](https://www.morphllm.com/ai-coding-agent)
- Weakness: its top Terminal-Bench 4.0 entry costs roughly 7x per task what the cheapest Codex entry costs ($14.30 vs $1.92 per task) — [Morph](https://www.morphllm.com/ai-coding-agent)

**OpenAI Codex (CLI + cloud)**
- CLI, IDE extension, cloud agent on the web, desktop app and iOS, plus cloud code review. Apache-2.0, about 109k stars, version 0.149.0 — [Morph](https://www.morphllm.com/ai-coding-agent)
- Bundled with ChatGPT plans: Free, Go $8, Plus $20, Pro from $100 (one source lists Pro tiers at $100, $200 and $500). An API-key mode bills per token but loses the cloud features — [Morph](https://www.morphllm.com/ai-coding-agent); [amux](https://amux.io/blog/ai-coding-tools-pricing-2026/)

**Cursor**
- VS Code fork with an agent loop, cloud (background) agents and Bugbot PR review. Uses frontier models plus its in-house Composer model. Proprietary, and acquired Continue.dev — [Morph](https://www.morphllm.com/ai-coding-agent)
- Plans: Hobby $0, Pro $20 (includes $20 of usage), Pro+ $60, Ultra $200, Teams $40/user. Another source says Teams is $30+, so the figure conflicts. Cursor-model and other-model usage come from separate pools — [Morph](https://www.morphllm.com/ai-coding-agent); [amux](https://amux.io/blog/ai-coding-tools-pricing-2026/)
- Rumours of a SpaceX acquisition of Cursor appear in blogs. NOT verified — [dev.to](https://dev.to/hassann/devin-vs-cursor-in-2026-windsurf-is-now-devin-desktop-ajo)

**GitHub Copilot coding agent**
- Agent HQ was announced at Universe 2025 as a way to run agents from Anthropic, OpenAI, Google, Cognition and xAI inside a paid Copilot subscription. The coding agent also gained a self-review pass before a human sees its changes — [GitHub blog](https://github.blog/news-insights/company-news/welcome-home-agents/)
- Agent HQ entered public preview by Feb 2026. Claude and Codex are included with Copilot Enterprise, and each agent session costs one premium request — [GitHub enterprise roundup Feb '26](https://github.com/resources/insights/enterprise-content-roundup-february-26)
- Agent Plugins 1.0 went GA across VS Code, Copilot CLI, the SDK and the Copilot app (Aug 2026) — [GitHub changelog 2026-08-13](https://github.blog/changelog/2026-08-13-github-copilot-weekly-releases-august-10). Local sandboxing for agents went GA in the CLI, app and VS Code (Oct 2026) — [changelog 2026-10-05](https://github.blog/changelog/2026-10-05-github-copilot-weekly-releases-october-5/). A Copilot harness built on the Microsoft Copilot SDK became the default for new sessions, and sessions can continue across clients (Oct 28 2026) — [changelog 2026-10-28](https://github.blog/changelog/2026-10-28-github-copilot-in-vs-code-universe-releases)
- Pricing is credit-based (1 credit = $0.01): Free; Pro $10 (1,500 credits); Pro+ $39; Max $100; Business $19/seat; Enterprise $39/seat. Business self-serve sign-ups were reportedly paused on Apr 22 2026 — [Morph](https://www.morphllm.com/ai-coding-agent) (single source)

**Devin (Cognition) / Devin Desktop (formerly Windsurf)**
- Windsurf was renamed Devin Desktop through an over-the-air update. The Agent Command Center is the primary view and settings carry over — [Devin Desktop FAQ](https://docs.devin.ai/desktop/devin-desktop-faq)
- The Cascade agent reached end-of-life on Jul 1 2026. "Devin Local" became the default local agent: it supports subagents and shares its architecture with Devin CLI. Cloud Devin is the async half of the lineup — [dev.to (secondary)](https://dev.to/jovan_chan_9500711396d4e6/windsurf-is-now-devin-desktop-what-the-june-2-rebrand-agent-command-center-default-surface-and-5d0i); [Devin FAQ](https://docs.devin.ai/desktop/devin-desktop-faq)
- Pricing: Free, Pro $20, Max $200, Teams $80 plus $40 per seat. The default agent model is SWE 1.6 — [Morph](https://www.morphllm.com/ai-coding-agent). A different blog says Devin Teams costs $500/mo, which conflicts — [amux](https://amux.io/blog/ai-coding-tools-pricing-2026/)

**Google Jules / Gemini CLI (Antigravity CLI)**
- Jules is an async cloud agent. It left beta in Aug 2025. The free tier allows 15 tasks a day with 3 concurrent; AI Pro raises the limits and AI Ultra gives 20x — [Google blog, Aug 2025](https://blog.google/technology/google-labs/jules-now-available/). Jules Tools CLI and the Jules API launched Oct 2 2025 — [Google blog](https://blog.google/technology/google-labs/jules-tools-jules-api/)
- 2026 Jules pricing is reported as $0–$125/mo by one source and $0–$99.99 by another, bundled into Google AI tiers. Unverified — [Morph Jules](https://www.morphllm.com/comparisons/jules-google-coding-agent); [dev.to](https://dev.to/dmaxdev/google-jules-review-the-async-coding-agent-worth-20month-4no)
- Gemini CLI: Apache-2.0, about 107k stars, with MCP, Google Search grounding and 1M-token context. Free serving for personal users ended Jun 18 2026, while the newer Antigravity CLI is free — [Morph](https://www.morphllm.com/ai-coding-agent)

**Open-source / BYOK agents**
- OpenHands: about 70k–83k stars depending on source and date; v1.8.0 released Jun 10 2026 — [dev.to review](https://dev.to/jovan_chan_9500711396d4e6/openhands-review-2026-the-76k-star-coding-agent-5pa); [aiwiki](https://aiwiki.ai/wiki/best_open_source_coding_agents)
- SWE-agent: about 19k stars (undated) — [openalternative](https://openalternative.co/compare/openhands/vs/swe-agent). mini-SWE-agent: v2.4.6 (Jul 23 2026), about 9.8k stars as of Nov 19 2026 — [aiwiki](https://aiwiki.ai/wiki/best_open_source_coding_agents); [Star History](https://www.star-history.com/swe-agent/mini-swe-agent). mini-SWE-agent is the standard harness on Scale's SWE-bench Pro board (entries marked *) — [Scale leaderboard](https://labs.scale.com/leaderboard/swe_bench_pro_public)
- Aider: git-native terminal tool that auto-commits each edit; Apache-2.0, about 48k stars. Last repo push was May 22 2026, and its polyglot leaderboard has not been refreshed for 2026 models — [Morph](https://www.morphllm.com/ai-coding-agent)
- Cline: VS Code/IDE extension plus CLI and SDK, with Plan/Act modes and approval before each change; BYOK with no markup; Apache-2.0, about 67k stars. Roo Code is a Cline fork: Apache-2.0, about 24k stars, with a hosted cloud product (roomote.dev) from $99/mo — [Morph](https://www.morphllm.com/ai-coding-agent)
- Amp (Sourcegraph): CLI plus VS Code, JetBrains, Neovim and Zed. It runs parallel sub-agents and MCP, and has an "Oracle" second-opinion model. Pay-as-you-go with a $5 minimum and no markup; enterprise costs +50% plus a $1,000 one-time fee — [Morph](https://www.morphllm.com/ai-coding-agent)
- opencode: MIT, about 200k stars (the most-starred agent on Morph's list). Terminal, desktop and IDE, with MCP, LSP, sub-agents and any BYOK provider; v1.18.19 (Aug 20 2026). Reportedly, Anthropic prohibits using Claude Pro/Max subscriptions with it — [Morph](https://www.morphllm.com/ai-coding-agent)
- Kilo Code (MIT, about 27k stars, routes across 500+ models) and Zed (about 89k stars, hosts external agents such as Claude Agent and Codex) are adjacent players — [Morph](https://www.morphllm.com/ai-coding-agent)

### Inferences
- Pricing falls into three models. Subscriptions with rolling caps (Claude Code, Codex, Jules) give predictable bills but throttle you. Credits or usage pools (Copilot, Cursor) are metered. BYOK at token cost (Cline, Aider, opencode, Amp, OpenHands) is transparent, but heavy agent use gets expensive.
- The extensibility features have converged into a de facto standard: MCP, subagents, hooks, skills/plugins and a project memory file. Copilot's Agent Plugins GA and Devin's subagent support suggest these are now baseline features, not differentiators.
- Among open-source projects by stars: opencode (~200k) > Gemini CLI (~107k) and Codex CLI (~109k, open-source client) > OpenHands (~70–83k) > Cline (~67k) > Aider (~48k) > Roo Code (~24k) > SWE-agent (~19k) > mini-SWE-agent (~10k). Claude Code's repo has ~142k stars but is not open source.

### Gaps
- Sandbox types could not be confirmed from primary sources in this pass. Examples: whether Codex cloud runs in isolated containers, whether Copilot coding agent runs on GitHub Actions runners, whether Devin uses cloud VMs, and OpenHands' Docker runtime. These are well known from 2025 documentation but were not re-verified for late 2026.
- Cursor's background/cloud agent architecture, and current official pricing pages, were not fetched directly.
- No download counts (npm/PyPI/VS Code marketplace installs) were found. Star counts conflict across sources.

## Benchmarks (dated) and benchmark criticism

### Takeaway
SWE-bench Verified is widely treated as saturated and contaminated. OpenAI stopped reporting it in Feb 2026. SWE-bench Pro and Terminal-Bench (2.x, now 4.x) are the current reference points. Scores vary widely with the harness, the subset and whether a vendor reported them itself, so headline numbers from different sources cannot be compared.

### Cited Findings
- **SWE-bench Pro (Scale, official public board, fetched Nov 24 2026; no per-entry dates):** Muse Spark 1.1* 61.5%, gpt-5.4 (xHigh)* 59.1%, Muse Spark* 55.0%, claude-opus-4-6 (thinking)* 51.9%, gemini-3.1-pro* 46.1%, claude-opus-4-5 45.9%, gpt-5.2-codex 41.0%, qwen3-coder-480b 38.7%. The * marks the standardized mini-swe-agent harness, run with uncapped cost and a 250-turn limit. The dataset has 1,865 tasks across 41 repos: 731 public, 276 private from 18 proprietary startup codebases, and 858 held out — [Scale Labs leaderboard](https://labs.scale.com/leaderboard/swe_bench_pro_public)
- Private-subset scores fall: Claude Opus 4.1 went from 22.7% to 17.8% and GPT-5 from 23.1% to 14.9%. These are older 2025 figures — [Scale Labs](https://labs.scale.com/leaderboard/swe_bench_pro_public)
- **SWE-bench Pro, vendor self-reported or aggregator (Aug 2026):** Fable 5 80.0%, Opus 4.8 69.2% — [Morph](https://www.morphllm.com/ai-coding-agent). Other aggregators claim Claude Mythos 5 at 80.3% (Jul 29 2026), Gemini 3 Pro at 84.8% (Sep 2026) and GPT-5.4 at 88.4% (Aug 2026). These conflict with each other and with Scale's own board — [BenchLM](https://benchlm.ai/benchmarks/swe-bench-pro); [llm-stats](https://llm-stats.com/benchmarks/swe-bench-pro). FLAG: these claims are 20–30 points above Scale's standardized numbers, so they probably use custom harnesses or scaffolds.
- **Terminal-Bench 2.0:**
  - Feb 2026: Droid + GPT-5.3-Codex led at 77.3%, with the top four within 2.5 points — [Simon Willison gist](https://gist.github.com/simonw/3bff274abcbbbf8766e9437a542db248)
  - Apr 27 2026 snapshot: Codex + GPT-5.5 82.0%, ForgeCode + GPT-5.4 81.8%, TongAgents + Gemini 3.1 Pro 80.2% — [Codesota](https://www.codesota.com/benchmark/terminal-bench)
  - Vals.ai (Jun 4 2026, Terminus 2 harness): GPT-5.5 73.2%, Claude Opus 4.8 70.0%. Vals then archived the benchmark as saturated — [Vals.ai](https://vals.ai/benchmarks/terminal-bench-2)
  - Snorkel board: 142 entries, with the top 10 between 77.3% and 84.7% — [Snorkel](https://snorkel.ai/leaderboard/terminal-bench-2-0/)
- **Terminal-Bench 2.1 (Aug 21 2026, Terminus 2 harness):** GPT-5.6 Sol 89.5%, Opus 5 89.1%, Grok 4.6 88.4%; Gemini CLI + Gemini 3.1 Pro 70.7% — [Morph](https://www.morphllm.com/ai-coding-agent) (single source)
- **Terminal-Bench 4.0 (tbench.ai, Oct 6 2026):** Claude Code + Opus 5.5 64.8% ($14.30/task), Sonnet 5.5 61.8%, Codex + GPT-6.1 Sol 58.2% ($1.92/task) — [Morph](https://www.morphllm.com/ai-coding-agent) (single source). The tbench.ai leaderboard page showed a "Terminal-Bench 4.1" table with no rows when fetched — [tbench.ai](https://www.tbench.ai/leaderboard/terminal-bench/2.0)
- Aider polyglot: 88.0% with gpt-5 (high). This is a stale 2025 figure and the board has not been refreshed — [Morph](https://www.morphllm.com/ai-coding-agent)
- **Criticism of SWE-bench Verified:** OpenAI stopped reporting it on Feb 23 2026. Of 138 audited hard problems, 59.4% had material test issues (35.5% narrow tests, 18.8% wide tests). Every frontier model tested could reproduce gold patches or verbatim problem text for some tasks. GPT-5.2 solved 31 "nearly impossible" tasks, once citing a later Django release. SOTA went from 74.9% to 80.9% over 6 months. OpenAI recommends SWE-bench Pro instead — [OpenAI](https://openai.com/index/why-we-no-longer-evaluate-swe-bench-verified/)
- Epoch rates SWE-bench Verified "Flawed" because of assumed contamination — [Epoch AI](https://epoch.ai/benchmarks/swe-bench-verified/review). "The SWE-Bench Illusion" finds accuracy falls to as low as 53% on repos outside SWE-bench, which suggests memorization — [arXiv 2506.12286](https://arxiv.org/html/2506.12286v4). A Dec 2025 study finds models score 3x higher on Verified than on comparable newer benchmarks — [arXiv 2512.10218](https://arxiv.org/abs/2512.10218v1)
- Harness matters: the same model appears several times on Terminal-Bench with different agents and different results — [Codesota](https://www.codesota.com/benchmark/terminal-bench)

### Inferences
- In late 2026, the trustworthy anchor is Scale's standardized SWE-bench Pro public board, where the top score is about 60%. Vendor-reported Pro numbers around 80% use their own scaffolds and should be labeled that way.
- Terminal-Bench 2.0 saturated in about 6 months (77% in Feb, 82% in Apr, archived by Vals in Jun). The jump to TB 4.0, where the top score is about 65%, mirrors the move from SWE-bench Verified to Pro. Benchmarks are being replaced roughly yearly.
- Cost per task differs by up to 7x between the top entries. Comparisons that ignore cost are misleading.

### Gaps
- Could not retrieve the official swebench.com Verified or bash-only rows, or the tbench.ai rows (pages rendered empty). TB 2.1, 4.0 and 4.1 figures come from a single aggregator.
- The "Muse Spark" model's vendor was not identified.
- No independent benchmark of products as shipped (as opposed to model plus harness) was found for Cursor, Copilot, Devin or Amp.

## End-to-end workflows supported

### Takeaway
Issue-to-PR, async/background agents, parallel agents and AI code review are standard across the commercial agents. CI repair and test generation are supported mainly as uses of the generic agent loop and are rarely benchmarked.

### Cited Findings
- Copilot coding agent: works asynchronously from issues to PRs and self-reviews before handing off to a human. Agent HQ lets Claude and Codex agents run the same way inside GitHub — [GitHub blog](https://github.blog/news-insights/company-news/welcome-home-agents/); [Feb '26 roundup](https://github.com/resources/insights/enterprise-content-roundup-february-26). There is also a Copilot cloud agent integration for Linear (GA) — [GitHub blog search](https://github.blog/search/copilot/page/5/)
- Codex: cloud agent plus cloud code review. Cursor: cloud agents plus Bugbot reviews. Claude Code: background/cloud sessions plus sub-agents. Amp: parallel sub-agents — [Morph](https://www.morphllm.com/ai-coding-agent)
- Devin Desktop's "Agent Command Center" is built for supervising many agents, local and cloud — [Devin FAQ](https://docs.devin.ai/desktop/devin-desktop-faq)
- Jules: async tasks (3 concurrent on free), plus a CLI and API for CI/CD and Slack integration — [Google blog](https://blog.google/technology/google-labs/jules-tools-jules-api/)

### Inferences
- The center of gravity has moved from chat in the editor to dispatching tasks and reviewing PRs. Review agents (Bugbot, Codex review, Copilot self-review) are now how vendors answer the weak-verification problem.

### Gaps
- No systematic data on how well agents perform at CI repair or test generation. Merge rates of agent-authored PRs were not found in this pass.

## Most-used open-source agents
See the star counts above. Additional points:

### Takeaway
opencode leads open-source mindshare by stars, followed by vendor-backed open-source CLIs (Gemini CLI, Codex CLI). OpenHands is the leading open platform for research and self-hosting. mini-SWE-agent matters as a benchmark harness, not as a product.

### Cited Findings
- OpenHands "significantly outpaces SWE-agent in community adoption" — [openalternative](https://openalternative.co/compare/openhands/vs/swe-agent)
- What sets each apart: Aider is git-native with auto-commits; Cline/Roo require approval at each step and are BYOK with no markup; opencode supports any provider and local models; Kilo routes across 500+ models — [Morph](https://www.morphllm.com/ai-coding-agent)

### Gaps
- No download or install counts from npm, PyPI or the VS Code marketplace were found.

## Documented weaknesses and complaints

### Takeaway
Developers trust AI coding output less over time even as they use it more. The best-documented complaints are cost and unpredictable usage caps, "almost right" code, agents claiming success they have not verified, and a fast-growing security attack surface (prompt injection, poisoned MCP or extensions, CI secrets).

### Cited Findings
- Stack Overflow 2025 survey (Jul 29 2025, older):
  - 46% distrust the accuracy of AI output (31% in 2024).
  - 66% cite "almost right, but not quite" solutions as a frustration; 45% say debugging AI code takes longer.
  - Only 14.1% use agents daily and 37.9% don't plan to.
  - Of agent users, 69% report a productivity gain but only 38% report better code quality; 87% worry about the accuracy of agent output.
  - Sources: [Stack Overflow blog](https://stackoverflow.blog/2025/07/29/developers-remain-willing-but-reluctant-to-use-ai-the-2025-developer-survey-results-are-here); [InfoWorld](https://www.infoworld.com/article/4031673/); [ITPro](https://www.itpro.com/software/development/developers-arent-quite-ready-to-place-their-trust-in-ai-nearly-half-say-they-dont-trust-the-accuracy-of-outputs-and-end-up-wasting-time-debugging-code)
  - Trust figures differ across write-ups (29% vs 33% trust).
- METR: the Jul 2025 RCT (16 developers, 246 tasks) found experienced developers 19% slower with AI. METR now calls that result "historical." Its Feb 24 2026 update says its new central estimate is "likely a bad proxy" because of selection effects: developers refused to work without AI. The study is being redesigned — [METR](https://metr.org/blog/2026-02-24-uplift-update/); [TechCrunch May 2026](https://techcrunch.com/2026/05/29/coders-are-refusing-to-work-without-ai-and-that-could-come-back-to-bite-them/)
- Cost and caps:
  - Since Mar 2026, Claude Code Max users report quotas running out in as little as 19 minutes; Anthropic acknowledged it was investigating — [DevOps.com](https://devops.com/claude-code-quota-limits-usage-problems/)
  - Codex weekly usage is consumed even by failed or slow tasks — [OpenAI community](https://community.openai.com/t/codex-weekly-usage-disappearing-on-failed-or-extremely-slow-tasks/1389618)
- Hallucinated success and weak verification:
  - Field reports describe agents claiming tests pass without running them — [beginnersinai](https://beginnersinai.org/why-ai-coding-agents-fail/)
  - Claude Code and Codex CLI both failed confidently after hours on a well-defined, testable task — [iximiuz](https://iximiuz.com/en/posts/grounded-take-on-agentic-coding/)
  - An arXiv study analyzes 3.8k+ public bugs in the Claude Code, Codex and Gemini CLI repos — [arXiv 2603.20847](https://arxiv.org/html/2603.20847v1)
  - Brittle context windows and broken refactors are other reported failure modes — [VentureBeat](https://venturebeat.com/infrastructure/why-ai-coding-agents-arent-production-ready-brittle-context-windows-broken)
  - Anecdotal claims of quality regressions (e.g., "25% of instructions missed") are single-source — [dev.to](https://dev.to/gentic_news/claude-code-quality-drops-post-46-users-report-25-task-failure-rate-384l)
- Security:
  - CVEs: CVE-2025-54795 (Claude Code command injection, CVSS 8.7), CVE-2025-61260 (Codex CLI command injection) and CVE-2025-54135 (Cursor "CurXecute", MCP config rewrite leading to RCE) — [CSA research note, Apr 2026](https://labs.cloudsecurityalliance.org/research/csa-research-note-ai-coding-assistant-attack-surface-2026040/). An SoK paper counts 30+ CVEs across major assistants and reports prompt-injection success above 85% under adaptive attacks — [arXiv 2601.17548](https://arxiv.org/html/2601.17548)
  - Tampered Claude extension builds were served on Cursor's marketplace on Oct 29 2026 and pulled within about a day — [CSA note Nov 2026](https://labs.cloudsecurityalliance.org/wp-content/uploads/2026/11/CSA_research_note_cursor_claude_code_extension_trojan_20261103-csa-styled.pdf)
  - The "Miasma" supply-chain worm (May 2026, attributed to TeamPCP) disabled 73 Microsoft GitHub repos. An MCP STDIO RCE affected up to about 200k installs (Apr 2026, OX Security) — [CSA MCP/repo poisoning](https://labs.cloudsecurityalliance.org/research/ai-coding-agent-attack-surface-mcp-repository-poisoning-v1-0/)
  - Agents in CI/CD can be steered through GitHub issue titles ("Clinejection"); in Codex's case, injected instructions persisted across runs — [CSA Aug 2026](https://labs.cloudsecurityalliance.org/wp-content/uploads/2026/08/CSA_research_note_ai_coding_agent_cicd_secrets_20260808-csa-styled.pdf)
  - "AgentJacking": fake Sentry errors hijacked Claude Code, Cursor and Codex, with a claimed ~85% success rate (single source) — [dev.to](https://dev.to/docdavkitty/agentjacking-how-a-fake-sentry-error-can-hijack-claude-code-cursor-and-codex-and-what-it-means-1ogi)

### Inferences
- Verification is the main unsolved gap. Agents generate faster than humans can review, and benchmarks reward passing tests that may themselves be flawed (59% of hard Verified tasks). This is a clear product opportunity: independent verification, review and test-integrity layers.
- Security risk grows with autonomy and extensibility. MCP servers, skills, plugins and marketplaces are the new supply-chain vector, and moving agents into CI exposes secrets.
- There is still no credible productivity measurement in 2026. METR's redesign leaves the question open.

### Gaps
- No systematic measurement of how large agent diffs are, or of how often PRs are rejected for size.
- Most of the security incidents were seen only through CSA secondary notes; primary vendor disclosures were not checked.
- JetBrains 2025/2026 developer survey data was not retrieved.
