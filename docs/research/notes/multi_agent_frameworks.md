# Multi-agent frameworks and the evidence on whether multi-agent systems work (as of 24 Nov 2026)

Method note: GitHub star counts, last-push dates and archive status were pulled live from the public GitHub REST API (`api.github.com/repos/<owner>/<repo>`) on 2026-11-24. Paper numbers come from the arXiv pages fetched the same day. Feature descriptions of frameworks (abstractions, HITL, observability) were NOT all re-verified page-by-page in this session; where a claim rests only on the framework's README/docs URL without a fetched quote, it is marked "(docs, not re-verified)".

## Q1. Framework comparison: core abstraction, state/memory, HITL, observability, adoption, status

### Takeaway
The field has consolidated into (a) graph/workflow runtimes with durable state (LangGraph, Microsoft Agent Framework, Google ADK) and (b) thin "agent loop + tools + handoffs/subagents" SDKs (OpenAI Agents SDK, Claude Agent SDK, Pydantic AI, smolagents), while the role-play "AI software company" frameworks (MetaGPT, ChatDev) remain popular by stars but are research artefacts with weak independent evidence. AutoGen is now archived; its successors are Microsoft Agent Framework (GA April 2026) and the community fork AG2.

### Cited Findings

Adoption and status snapshot (GitHub API, 2026-11-24):

| Framework | Repo | Stars | Last push | Status |
|---|---|---|---|---|
| MetaGPT | FoundationAgents/MetaGPT | 71,436 | 2026-01-21 | Active-ish; no push for ~10 months (stalled) |
| AutoGen | microsoft/autogen | 61,964 | 2026-11-12 | **Archived** |
| CrewAI | crewAIInc/crewAI | 61,207 | 2026-11-23 | Active |
| LangGraph | langchain-ai/langgraph | 45,319 | 2026-11-24 | Active |
| ChatDev | OpenBMB/ChatDev | 34,859 | 2026-11-06 | Active ("ChatDev 2.0") |
| OpenAI Agents SDK (Python) | openai/openai-agents-python | 30,844 | 2026-11-23 | Active |
| smolagents | huggingface/smolagents | 30,502 | 2026-11-23 | Active |
| Google ADK (Python) | google/adk-python | 22,330 | 2026-11-23 | Active |
| Pydantic AI | pydantic/pydantic-ai | 21,355 | 2026-11-24 | Active |
| SWE-agent | SWE-agent/SWE-agent | 20,855 | 2026-11-23 | Active |
| Claude Agent SDK (Python) | anthropics/claude-agent-sdk-python | 8,633 | 2026-11-23 | Active |
| AG2 (AutoGen fork) | ag2ai/ag2 | 5,084 | 2026-11-23 | Active |
| Microsoft Agent Framework | microsoft/agent-framework | n/a | n/a | API and github.com both returned HTTP 404 on 2026-11-24 (repo may have been renamed/moved; could not verify) |

Sources: [crewAI](https://github.com/crewAIInc/crewAI), [autogen](https://github.com/microsoft/autogen), [ag2](https://github.com/ag2ai/ag2), [langgraph](https://github.com/langchain-ai/langgraph), [MetaGPT](https://github.com/FoundationAgents/MetaGPT), [ChatDev](https://github.com/OpenBMB/ChatDev), [openai-agents-python](https://github.com/openai/openai-agents-python), [claude-agent-sdk-python](https://github.com/anthropics/claude-agent-sdk-python), [adk-python](https://github.com/google/adk-python), [pydantic-ai](https://github.com/pydantic/pydantic-ai), [smolagents](https://github.com/huggingface/smolagents), [SWE-agent](https://github.com/SWE-agent/SWE-agent)

AutoGen / AG2 / Microsoft Agent Framework:
- AutoGen README now says: "Project archived and no longer maintained... Microsoft is not providing bug fixes, security fixes, new features, or support... we continue to advise against production use. New users should start with Microsoft Agent Framework" and links a migration guide — [AutoGen README](https://github.com/microsoft/autogen); [migration guide](https://learn.microsoft.com/en-us/agent-framework/migration-guide/from-autogen/)
- Microsoft Agent Framework was introduced in public preview on 1 Oct 2025 as the unification of Semantic Kernel's "enterprise-ready foundations" with AutoGen's orchestration — [Microsoft Foundry blog, Oct 2025](https://devblogs.microsoft.com/foundry/introducing-microsoft-agent-framework-the-open-source-engine-for-agentic-ai-apps/)
- Agent Framework 1.0 GA shipped ~3 April 2026 for .NET and Python — [Microsoft Agent Framework blog, 3 Apr 2026](https://devblogs.microsoft.com/agent-framework/microsoft-agent-framework-version-1-0/); [Visual Studio Magazine, 6 Apr 2026](https://visualstudiomagazine.com/articles/2026/04/06/microsoft-ships-production-ready-agent-framework-1-0-for-net-and-python.aspx). Release-candidate migration guidance for SK and AutoGen was published 19 Feb 2026 — [MS blog](https://devblogs.microsoft.com/agent-framework/migrate-your-semantic-kernel-and-autogen-projects-to-microsoft-agent-framework-release-candidate/)
- Conflict: secondary coverage of the GA said AutoGen/SK would still get bug fixes and security patches — [VentureBeat](https://venturebeat.com/orchestration/microsoft-retires-autogen-and-debuts-agent-framework-to-unify-and-govern); but the AutoGen repo itself is now archived with no security fixes — [AutoGen README](https://github.com/microsoft/autogen). Treat the README as authoritative for AutoGen.
- AG2 describes itself as "AG2 (formerly AutoGen): The Open-Source AgentOS" (community fork that kept the original conversable-agent / GroupChat model); it has ~5k stars vs AutoGen's ~62k — [ag2 repo](https://github.com/ag2ai/ag2)
- Core abstractions: AutoGen/AG2 = conversable agents in group chats (conversation-centric); Agent Framework = agents plus typed graph "workflows" with checkpointing and human-in-the-loop request/response, OpenTelemetry tracing (docs, not re-verified) — [Agent Framework docs](https://learn.microsoft.com/en-us/agent-framework/)

CrewAI:
- Self-description: "Framework for orchestrating role-playing, autonomous AI agents" — [crewAI repo](https://github.com/crewAIInc/crewAI)
- Abstraction: Agents defined by role/goal/backstory, grouped into a Crew executing Tasks via sequential or hierarchical (manager) process; "Flows" add event-driven deterministic orchestration with state; built-in short/long-term/entity memory; `human_input` on tasks; tracing integrations and a commercial AMP/Enterprise control plane (docs, not re-verified) — [CrewAI docs](https://docs.crewai.com/)

LangGraph:
- Self-description: "Build resilient agents." — [langgraph repo](https://github.com/langchain-ai/langgraph)
- Abstraction: explicit state graph (nodes, edges, typed shared state); checkpointers give durable execution, time-travel and `interrupt()`-based human-in-the-loop; long-term memory store; observability via LangSmith; multi-agent via supervisor/swarm/handoff patterns built on the graph (docs, not re-verified) — [LangGraph docs](https://langchain-ai.github.io/langgraph/)

MetaGPT:
- Self-description: "The Multi-Agent Framework: First AI Software Company, Towards Natural Language Programming" — [MetaGPT repo](https://github.com/FoundationAgents/MetaGPT)
- Abstraction: roles (Product Manager, Architect, Project Manager, Engineer, QA) following SOPs, communicating via a shared message pool with publish/subscribe and structured documents (PRD, design, API spec) rather than free chat — [MetaGPT ICLR 2024 paper](https://proceedings.iclr.cc/paper_files/paper/2024/file/6507b115562bb0a305f1958ccc87355a-Paper-Conference.pdf)
- Status signal: last push 2026-01-21 despite 71k stars (highest of all) — [MetaGPT repo](https://github.com/FoundationAgents/MetaGPT)

ChatDev:
- Repo now branded "ChatDev 2.0: Dev All through LLM-powered Multi-Agent Collaboration" — [ChatDev repo](https://github.com/OpenBMB/ChatDev)
- Abstraction: "chat chain" of role pairs (CEO, CTO, programmer, reviewer, tester) moving through waterfall phases (design, coding, testing, documentation) — [ChatDev ACL 2024 paper](https://aclanthology.org/2024.acl-long.810.pdf)

OpenAI Agents SDK:
- Self-description: "A lightweight, powerful framework for multi-agent workflows" — [openai-agents-python](https://github.com/openai/openai-agents-python)
- Abstraction: Agents + tools + **handoffs** (agent-to-agent transfer) + guardrails + sessions; built-in tracing to the OpenAI dashboard (docs, not re-verified) — [Agents SDK docs](https://openai.github.io/openai-agents-python/)

Claude Agent SDK:
- Repo: anthropics/claude-agent-sdk-python, 8.6k stars — [repo](https://github.com/anthropics/claude-agent-sdk-python)
- Abstraction: the Claude Code agent loop as a library (tools, MCP, permissions/hooks for HITL, context compaction, subagents with isolated context) (docs, not re-verified) — [Agent SDK docs](https://docs.claude.com/en/api/agent-sdk/overview)
- Anthropic's own multi-agent pattern is orchestrator-worker (lead agent spawns parallel subagents) — [Anthropic engineering, 13 Jun 2025](https://www.anthropic.com/engineering/multi-agent-research-system)

Google ADK:
- Self-description: "An open-source, code-first Python toolkit for building, evaluating, and deploying sophisticated..." agents — [adk-python](https://github.com/google/adk-python)
- Abstraction: LLM agents plus workflow agents (Sequential, Parallel, Loop) composed hierarchically; sessions/state and memory services; built-in eval; A2A protocol interoperability (docs, not re-verified) — [ADK docs](https://google.github.io/adk-docs/)

Pydantic AI:
- Self-description now: "How Python does AI. Agents, realtime voice, image generation, embeddings. Every model..." — [pydantic-ai](https://github.com/pydantic/pydantic-ai)
- Abstraction: type-safe single agents with structured outputs and dependency injection; multi-agent via agent delegation or pydantic-graph; durable execution integrations; observability via Logfire/OpenTelemetry (docs, not re-verified) — [Pydantic AI docs](https://ai.pydantic.dev/)

smolagents:
- Self-description: "a barebones library for agents that think in code" — [smolagents](https://github.com/huggingface/smolagents)
- Abstraction: CodeAgent writes Python actions instead of JSON tool calls; managed agents allow simple hierarchies (docs, not re-verified) — [smolagents docs](https://huggingface.co/docs/smolagents)

### Inferences
- Stars are a poor proxy for production fitness: the two highest-starred repos (MetaGPT 71k, AutoGen 62k) are respectively stalled and archived. Momentum (recent pushes, vendor backing) favours LangGraph, CrewAI, OpenAI/Claude/Google SDKs and Pydantic AI.
- Vendor SDKs (OpenAI, Anthropic, Google, Microsoft) converged on a small set of primitives: tool-using agent loop, sub-agent/handoff, guardrails or hooks, tracing. Role-play metaphors (CEO/CTO) have not been adopted by any vendor SDK.
- Anyone still on AutoGen faces a forced migration (Agent Framework or AG2); the archive notice explicitly advises against production use.

### Gaps
- Microsoft Agent Framework star count and repo location could not be verified (404 on 2026-11-24).
- Enterprise adoption numbers (named customers, downloads) for each framework were not collected; vendor claims of "X% of Fortune 500" were not checked and should be treated as marketing.
- Per-framework HITL/observability feature details are from prior knowledge plus docs URLs, not re-fetched in this session.

## Q2. Do role-based "software company" agent teams beat single agents on real software benchmarks?

### Takeaway
No credible evidence that MetaGPT/ChatDev-style role-play teams beat strong single-agent scaffolds on shared, realistic benchmarks. Their headline wins are on self-made benchmarks or on saturated function-level benchmarks (HumanEval/MBPP) against weak baselines; on issue resolution (SWE-bench), the strongest results through mid-2026 come from single-agent scaffolds (mini-SWE-agent, Claude Code) or from narrow, verification-focused multi-agent designs, not org-chart role-play.

### Cited Findings
- MetaGPT (ICLR 2024) reports beating ChatDev on its own SoftwareDev dataset, with executability 3.75 out of 4 — [MetaGPT paper](https://proceedings.iclr.cc/paper_files/paper/2024/file/6507b115562bb0a305f1958ccc87355a-Paper-Conference.pdf)
- ChatDev (ACL 2024) reports raising "Quality" from 0.1523 (MetaGPT) to 0.3953, and that removing roles drops executability from 0.88 to 0.58 — [ChatDev paper](https://aclanthology.org/2024.acl-long.810.pdf)
- Each paper "wins" on its own benchmark (ChatDev claims ~88% executability; MetaGPT's paper reports ChatDev far lower), showing the incompatibility of self-made benchmarks — [Meiklejohn, "Benchmarks and What They Miss", 30 Apr 2026](https://christophermeiklejohn.com/ai/agents/mas-series/2026/04/30/mas-series-07-benchmarks.html) (secondary commentary)
- Independent check: MAST authors found ChatDev achieves only 33.33% correctness on their ProgramDev benchmark — [Berkeley MAST project page](https://sky.cs.berkeley.edu/project/mast/)
- AgentCoder (programmer + test designer + test executor): 96.3% / 91.8% pass@1 on HumanEval / MBPP with GPT-4 vs MetaGPT 79.3% / 84.4% (later version reports average 91.5% vs 75.5% prior SOTA) — [AgentCoder arXiv 2312.13010](https://arxiv.org/pdf/2312.13010)
- MapCoder (retrieval, planning, coding, debugging agents; ACL 2024): pass@1 HumanEval 93.9%, MBPP 83.1%, APPS 22.0%, CodeContests 28.5%, xCodeEval 45.3%; ~3% over Reflexion on HumanEval with GPT-4 — [MapCoder arXiv 2405.11403](https://arxiv.org/abs/2405.11403v1)
- Controlled re-test (GPT-4.1, 10 benchmarks, 3,302 instances/run): LLM-Debate gained +9.67 pts on HumanEval (94.66% vs 84.99%) over a single-agent controller but was 1.96 pts lower pooled at 1.39x tokens — [Fu et al., "Do More Agents Help?", arXiv 2606.05670, v2 Oct 2026](https://arxiv.org/html/2606.05670)
- E2EDevBench (Nov 2025): state-of-the-art agents fulfil ~50% of requirements in end-to-end development; success "critically dependent on the architectural strategy for task decomposition and collaboration"; main bottlenecks are omitted requirements and inadequate self-verification — [Zeng et al., arXiv 2511.04064](https://arxiv.org/abs/2511.04064)
- icat-agent (Jun 2026, decentralized multi-agent, event-based messaging, issue-quality-triaged workflow): +3.6–8.4% on SWE-bench Verified and +6.3–18.5% on SWE-bench Pro over SWE-agent, mini-SWE-agent and Claude Code with same models; 67.4% on SWE-bench Pro with GPT-5.4-xhigh vs prior best 59.10% (mini-SWE-agent + GPT-5.4-xhigh); $1.18/instance cheaper than the Claude Code baseline — [Chen et al., arXiv 2606.25514](https://arxiv.org/abs/2606.25514) (preprint, self-reported)
- Note that the prior SWE-bench Pro best cited by that paper was a minimal single-agent scaffold (mini-SWE-agent) — [arXiv 2606.25514](https://arxiv.org/abs/2606.25514)
- RTADev (ACL Findings 2025) beats MetaGPT and ChatDev on its own FSD-Bench, at higher time and token cost than MetaGPT — [RTADev](https://aclanthology.org/2025.findings-acl.80.pdf)
- A 2026 multi-vocal literature review of 114 studies on LLM multi-agent code generation catalogues 9 adoption motivations and 6 challenge categories (26 subcategories), but the abstract makes no claim that MAS outperforms single agents — [Rasheed et al., arXiv 2604.16321, JSS 2026](https://arxiv.org/abs/2604.16321)
- Cognition (makers of Devin) in production: Devin Review (a separate reviewer agent) catches ~2 bugs per PR, ~58% severe; parallel-writer swarms "remain largely unadopted" — [Cognition, "Multi-Agents: What's Actually Working", 22 Apr 2026](https://cognition.com/blog/multi-agents-working)

### Inferences
- What helps in code is not "roles" per se but *test/verification loops*: AgentCoder's gain comes from an independent test designer; MAST's best ChatDev fix was a verification step; Devin Review is a verifier. Role-play (CEO/CTO) adds tokens without independent evidence of value.
- HumanEval/MBPP are near-saturated; 2023-24 multi-agent gains there mostly reflected weaker base models and should not be extrapolated to 2026 frontier models.
- The only multi-agent results beating strong single-agent SWE-bench scaffolds (icat-agent) are self-reported preprints and use adaptive triage plus parallel patch validation, i.e. a sampling-and-verify design, not a software-company org chart.
- Hype flag: "First AI Software Company" (MetaGPT README) and "Dev All" (ChatDev) are marketing claims; neither has published results on SWE-bench Verified/Pro found in this research.

### Gaps
- No MetaGPT or ChatDev result on SWE-bench Verified/Pro was found.
- Current SWE-bench leaderboard composition (share of single vs multi-agent entries) was not fetched.
- E2EDevBench's three architectures and per-architecture scores were not visible in the abstract.

## Q3. Research on multi-agent failures and cost vs quality

### Takeaway
Failures in multi-agent systems are mostly system-design and verification failures, not model failures (MAST: 41–86.7% failure rates across 7 popular MAS). Controlled 2026 studies consistently find multi-agent setups cost 1.3–4.7x more tokens and 2.6–5.8x more latency, with accuracy gains that are usually small, task-specific, or negative; the main exception (Anthropic's research system) wins largely by spending more tokens on parallelizable breadth-first tasks.

### Cited Findings
MAST — "Why Do Multi-Agent LLM Systems Fail?" (Cemri et al., Berkeley; arXiv Mar 2025, NeurIPS 2025):
- 14 failure modes in 3 categories, built from expert analysis of 150 traces, inter-annotator kappa = 0.88; MAST-Data has 1,600+ (1,642) annotated traces across 7 frameworks; LLM-as-judge annotator released — [arXiv 2503.13657](https://arxiv.org/html/2503.13657v3); [NeurIPS 2025 poster](https://neurips.cc/virtual/2025/poster/121528)
- Systems studied: MetaGPT, ChatDev, HyperAgent, AppWorld, AG2 (MathChat), Magentic-One, OpenManus; failure rates 41% to 86.7% — [arXiv 2503.13657](https://arxiv.org/html/2503.13657v3)
- Prevalence across traces: System design issues ~44% (disobey task spec 11.8%, disobey role spec 1.5%, step repetition 15.7%, loss of conversation history 2.8%, unaware of termination conditions 12.4%); Inter-agent misalignment ~32% (conversation reset 2.2%, fail to ask clarification 6.8%, task derailment 7.4%, information withholding 0.85%, ignored other agent's input 1.9%, reasoning-action mismatch 13.2%); Task verification ~23.5% (premature termination 6.2%, no/incomplete verification 8.2%, incorrect verification 9.1%). Category totals are summed from mode percentages — [arXiv 2503.13657](https://arxiv.org/html/2503.13657v3)
- Interventions on ChatDev: improved role specs/CEO final say +9.4% task success; adding a high-level objective verification step +15.6% on ProgramDev; authors say tactical prompt/topology fixes gave "inconsistent, limited" gains and failures need structural redesign — [arXiv 2503.13657](https://arxiv.org/html/2503.13657v3)

Cognition:
- "Don't Build Multi-Agents" (Walden Yan, 12 Jun 2025): principles "Share context, and share full agent traces, not just individual messages" and "Actions carry implicit decisions, and conflicting decisions carry bad results"; Flappy Bird example where two subagents produced a Mario-style background and a mismatched bird; recommends single-threaded linear agents plus a history-compression model — [Cognition](https://cognition.com/blog/dont-build-multi-agents)
- Revised stance (22 Apr 2026): multi-agent works when "several agents contribute intelligence while only one agent writes"; working patterns = generator-verifier review loop with clean-context reviewer, "smart friend" escalation to a stronger model, manager-child delegation (still being refined); failing patterns = parallel-writer swarms, weak primary model escalating, over-prescriptive managers, agents assuming shared state, unstructured agent networks — [Cognition](https://cognition.com/blog/multi-agents-working)
- Devin Bots (persistent agent overseeing multiple Devin sessions) launched 18 Nov 2026; Cognition has not explained how conflicts between parallel agents are resolved — [The New Stack](https://thenewstack.io/cognition-devin-bots-management/)

Anthropic multi-agent research system (13 Jun 2025):
- Orchestrator-worker (Opus 4 lead + Sonnet 4 subagents) beat single-agent Opus 4 by 90.2% on an internal research eval — [Anthropic](https://www.anthropic.com/engineering/multi-agent-research-system)
- Agents use ~4x chat tokens; multi-agent ~15x; on BrowseComp three factors explain 95% of variance, token usage alone 80%; "Multi-agent systems work mainly because they help spend enough tokens to solve the problem" — [Anthropic](https://www.anthropic.com/engineering/multi-agent-research-system)
- Poor fit: tasks needing shared context or many inter-agent dependencies, "most coding tasks", low-value tasks — [Anthropic](https://www.anthropic.com/engineering/multi-agent-research-system)

2026 cost-vs-quality studies:
- Amazon/UW, SOP-Bench (13 enterprise SOPs, 2,124 tasks/arm, single model held fixed): single agent 67.4% success at 24.9k tokens, 24.0s; Orchestration-v1 58.2% (1.4x tokens, 2.6x latency); Orchestration-v2 75.6% (4.7x tokens, 3.1x latency; the only significant win, OR 1.72, p = 0.007); swarms 65.4–70.5% at 1.9–2.7x tokens and 4.2–5.8x latency. Conclusion: single agent is the efficient default; implementation quality matters more than single-vs-multi (v1 failed because workers abstained). Paper's abstract and conclusion state slightly different ranges (1.4–4.7x vs 1.5–4.8x; 13 vs 12 SOPs) — [Nandi et al., arXiv 2611.12953, Nov 2026](https://arxiv.org/html/2611.12953)
- "Do More Agents Help?" (GPT-4.1, 10 benchmarks): single-agent core 76.65% pooled; only EvoAgent beat it (79.70%, +3.05 pts, 1.27x tokens); the other five MAS (LLM-Debate, CAMEL, AutoGen, Jarvis, ChatEval) trailed by 1.71–8.76 pts; ChatEval used 4.34x tokens (103k/instance) for −1.71 pts pooled but +22.25 pts on IFEval; on GAIA Jarvis 46.67% vs core 37.58% at fewer tokens. "No workflow led on every benchmark" — [Fu et al., arXiv 2606.05670](https://arxiv.org/html/2606.05670)
- Tran & Kiela (Apr 2026): single agents "consistently match or outperform MAS on multi-hop reasoning tasks when reasoning tokens are held constant" (Qwen3, DeepSeek-R1-Distill-Llama, Gemini 2.5); argue via Data Processing Inequality; MAS becomes competitive when single-agent context utilisation degrades; flag API budget-control and benchmark artefacts that inflate MAS gains — [arXiv 2604.02460](https://arxiv.org/abs/2604.02460)
- Essay grading: multi-agent ~4x cost (four calls per essay), better on low-quality essays, comparable or worse mid-range — [arXiv 2601.22386](https://arxiv.org/html/2601.22386v1)
- Counter-example: in the CODS 2025 AssetOpsBench challenge, single-agent runs used ~2x tokens of multi-agent (121K vs 63K), but driven by a token-heavy scenario type — [arXiv 2605.08518](https://arxiv.org/pdf/2605.08518)

### Inferences
- The consistent pattern: once you equalise compute, multi-agent advantage largely disappears; where MAS wins (Anthropic research, GAIA-type browsing, IFEval with ChatEval critique), it is through parallel breadth or independent checking, and it costs more.
- The Anthropic 90.2% figure is an internal eval with no public replication and compares against a single agent with a lower token budget; per Anthropic's own analysis it is mostly a token-spend effect. Treat as "multi-agent is a way to spend more tokens in parallel", not "teams are smarter".
- MAST's largest single category (system design, ~44%) plus verification (~23.5%) suggest two-thirds of failures are addressable by engineering (specs, termination, verification), not better models.

### Gaps
- MAST per-system failure rates are only in Figure 5 (not extractable from text).
- Tran & Kiela's numeric results were not available from the abstract.
- No 2026 study found that measures multi-agent cost/quality specifically for full software-delivery pipelines (requirements to deployment) with frontier models.

## Q4. Design choices that make multi-agent systems reliable

### Takeaway
The evidence favours: single writer with read-only or reviewing helpers, independent verifiers with clean context, structured (document/schema) hand-offs instead of free chat, explicit termination and objective checks, durable checkpointed state, and outcome-based evals with tracing. Debate and role-play help only on narrow tasks and are not cost-effective as defaults.

### Cited Findings
- Verification step: adding a high-level task-objective verification to ChatDev gave +15.6% task success; verification failures are ~23.5% of MAS failures — [MAST arXiv 2503.13657](https://arxiv.org/html/2503.13657v3)
- Independent reviewer with clean context (sees only the diff) catches ~2 bugs/PR, ~58% severe; add a filtering bridge so reviewer feedback outside scope does not cause loops — [Cognition, Apr 2026](https://cognition.com/blog/multi-agents-working)
- Single-threaded writes: keep one writer; parallel writers make conflicting implicit decisions — [Cognition, Jun 2025](https://cognition.com/blog/dont-build-multi-agents); [Cognition, Apr 2026](https://cognition.com/blog/multi-agents-working)
- Share full context/traces rather than summaries; never assume shared state in hierarchies; design explicit upward reporting — [Cognition Jun 2025](https://cognition.com/blog/dont-build-multi-agents); [Cognition Apr 2026](https://cognition.com/blog/multi-agents-working)
- Structured hand-offs: MetaGPT's SOP-driven structured documents and publish/subscribe message pool were designed to reduce idle chatter and hallucination cascades — [MetaGPT paper](https://proceedings.iclr.cc/paper_files/paper/2024/file/6507b115562bb0a305f1958ccc87355a-Paper-Conference.pdf)
- Orchestrator prompts must give subagents explicit objectives, output formats, tool guidance and task boundaries, and embed effort-scaling rules; parallel subagents cut research time up to 90% — [Anthropic](https://www.anthropic.com/engineering/multi-agent-research-system)
- Tool descriptions matter: a tool-testing agent rewriting flawed descriptions cut task completion time 40% — [Anthropic](https://www.anthropic.com/engineering/multi-agent-research-system)
- Reliability engineering: checkpoints and resume-from-failure, retries, full production tracing, rainbow deployments; evals start with ~20 real queries, judge outcomes not paths, LLM-judge with rubric plus human testing — [Anthropic](https://www.anthropic.com/engineering/multi-agent-research-system)
- Workers must be made to commit to answers: the SOP-Bench orchestrator v1 underperformed a single agent (58.2% vs 67.4%) because workers abstained; redesign (v2) reached 75.6% — [arXiv 2611.12953](https://arxiv.org/html/2611.12953)
- Debate: +9.67 pts on HumanEval but −1.96 pts pooled at 1.39x tokens — [arXiv 2606.05670](https://arxiv.org/html/2606.05670)
- Adaptive workflow: triaging issue quality before choosing parallel patch-and-validate vs exploration, with event-based message passing instead of shared context, gave SWE-bench gains in a preprint — [arXiv 2606.25514](https://arxiv.org/abs/2606.25514)
- Test-designer agent independent from programmer is AgentCoder's core mechanism (96.3% HumanEval with GPT-4) — [AgentCoder](https://arxiv.org/pdf/2312.13010)
- Main end-to-end bottlenecks are omitted requirements and inadequate self-verification — [E2EDevBench arXiv 2511.04064](https://arxiv.org/abs/2511.04064)

### Inferences
- For a software-delivery agent team, the defensible design is: one implementing agent (single writer), plus a requirements-checker and an independent reviewer/tester with clean context, connected by structured artefacts (spec, plan, diff, test report), with explicit termination criteria and a human approval gate. "PM/Architect/Engineer/QA" roles are fine as labels for those artefact owners, but the evidence supports the verification function, not the persona.
- Start single-agent, measure, and add an agent only where it adds independent verification or true parallelism; budget 1.3–5x tokens for each multi-agent layer.

### Gaps
- No controlled study found comparing "shared state" (blackboard) vs "message passing" designs head-to-head in software delivery beyond the icat-agent preprint.
- Quantitative evidence on human-in-the-loop gates' effect on MAS reliability was not found.
