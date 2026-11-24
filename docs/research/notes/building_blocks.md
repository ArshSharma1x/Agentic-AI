# Building Blocks of Production Agentic Systems (state as of late 2026)

Research date: 2026-11-24. Source dates are given for each item. Items from 2024 or early 2025 that are still the standard reference are marked [OLDER]. Items that have been replaced are marked [SUPERSEDED].

## 1. Agent loop and tool use: agents vs workflows, recommended patterns

### Takeaway
The working definitions still come from Anthropic (Dec 2024) and OpenAI (Apr 2025). A workflow runs LLMs along predefined code paths. An agent is an LLM that directs its own steps and tool use in a loop, until it decides it is done. Both vendors say to start with the simplest option, which means a single agent or plain workflow, and to add multi-agent orchestration only when it is clearly needed. They also say to spend more effort on tool design (the "agent-computer interface") than on the prompt.

### Cited Findings
- [OLDER, still canonical] Anthropic, "Building effective agents" (Dec 19, 2024). It defines **workflows** as "systems where LLMs and tools are orchestrated through predefined code paths" and **agents** as "systems where LLMs dynamically direct their own processes and tool usage, maintaining control over how they accomplish tasks." The page itself notes that tooling has changed since publication. — [Anthropic](https://www.anthropic.com/engineering/building-effective-agents)
- The patterns in that post, from simplest to most autonomous:
  - **Augmented LLM**: the base building block, a model with retrieval, tools and memory.
  - **Prompt chaining**: sequential steps with programmatic gates between them.
  - **Routing**: classify the input, then send it to a specialized handler.
  - **Parallelization**: either sectioning (split the work) or voting (run the same task several times).
  - **Orchestrator-workers**: a central LLM breaks the task down at runtime and combines the workers' results.
  - **Evaluator-optimizer**: one model generates and another critiques, in a loop.
  - **Autonomous agents**: act on environment feedback over many turns, at "higher cost" and with a risk of "compounding errors."

  — [Anthropic](https://www.anthropic.com/engineering/building-effective-agents)
- Guidance from the same post: "we recommend finding the simplest solution possible, and only increasing complexity when needed". Frameworks "often create extra layers of abstraction that can obscure the underlying prompts", so start with direct API calls. — [Anthropic](https://www.anthropic.com/engineering/building-effective-agents)
- ACI / tool design advice from the same post: "invest just as much effort in creating good agent-computer interfaces (ACI)". It also advises "poka-yoke" (mistake-proof) tool arguments. In Anthropic's SWE-bench work, the team spent more time on tools than on the prompt, and requiring absolute file paths removed a whole class of errors. — [Anthropic](https://www.anthropic.com/engineering/building-effective-agents)
- [OLDER] OpenAI, "A practical guide to building agents" (Apr 2025):
  - An agent has three core components: **model, tools, instructions**.
  - It operates within "clearly defined guardrails."
  - Start with a **single-agent** loop and "evolve to multi-agent only when needed."
  - Multi-agent shapes are the **manager pattern**, where a central agent calls specialist agents as tools, and decentralized handoffs.

  — [OpenAI PDF](https://cdn.openai.com/business-guides-and-resources/a-practical-guide-to-building-agents.pdf); summary via [ibl.ai](https://ibl.ai/blog/openai-a-practical-guide-to-building-agents) (secondary; the guardrails section text was not fully retrieved)
- Rewriting tool descriptions with an agent's help "reduced task completion time by 40%" in Anthropic's research system. — [Anthropic multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system)
- MCP 2026-07-28 says input-validation failures should come back as tool execution errors that the model can see and correct, not as protocol errors. This was introduced in 2025-11-25 (SEP-1303). — [WorkOS summary](https://workos.com/blog/mcp-2025-11-25-spec-update) (secondary)

### Inferences
- An open-source multi-agent delivery tool should be able to say, for each stage, whether it is a workflow (fixed pipeline: plan, then code, then review, then merge) or an agent (open loop). Most production systems are workflows with agentic steps inside them.
- Tool and ACI quality is the cheapest lever with the largest effect. Concrete examples are absolute paths, clear errors, and deterministic tool ordering.

### Gaps
- I found no updated 2026 version of either the Anthropic or OpenAI pattern guide. Both foundational documents predate 2026.

## 2. Context engineering

### Takeaway
Anthropic (Sep 2025) describes context engineering as the follow-on to prompt engineering. The aim is to curate "the smallest possible set of high-signal tokens" across the whole loop, because of "context rot." The standard techniques are:
- compaction
- tool result clearing
- structured note-taking (memory files)
- sub-agents with isolated contexts that return condensed summaries
- just-in-time retrieval through lightweight identifiers, combined with a few files loaded up front (CLAUDE.md, AGENTS.md)

### Cited Findings
- Anthropic, "Effective context engineering for AI agents" (Sep 29, 2025) defines context engineering as "the set of strategies for curating and maintaining the optimal set of tokens" during inference. "Context, therefore, must be treated as a finite resource with diminishing marginal returns." The goal is to "find the smallest possible set of high-signal tokens that maximize the likelihood of some desired outcome." — [Anthropic](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- Context rot: as the token count grows, "the model's ability to accurately recall information from that context decreases". Transformers create n² pairwise relationships between tokens. — [Anthropic](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- **Compaction** summarizes the conversation near the context limit and restarts from the summary. Claude Code keeps the summary plus the 5 most recently accessed files. — [Anthropic](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- **Tool result clearing** is "one of the lightest-touch forms of compaction" and is shipped as a feature on the Claude Developer Platform. — [Anthropic](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- **Structured note-taking / memory**: the agent writes notes outside the context window and reloads them later. In the Claude-plays-Pokémon example, notes carried progress across 1,234+ steps. A file-based memory tool shipped in public beta with Sonnet 4.5. — [Anthropic](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- **Sub-agent context isolation**: each sub-agent may use tens of thousands of tokens but returns a condensed summary of roughly 1,000–2,000 tokens. — [Anthropic](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- **Just-in-time retrieval**: the agent holds file paths, queries or links and loads the content through tools such as glob and grep. Claude Code is a hybrid, loading CLAUDE.md up front and everything else on demand. — [Anthropic](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- Cognition's counterpoint (Jun 2025) is to use a dedicated **context-compression model** for long-running tasks. Cognition fine-tuned a smaller model for this and notes that it "is hard to do well." — [Cognition](https://cognition.com/blog/dont-build-multi-agents)
- On the protocol side, MCP 2026-07-28 says servers SHOULD return `tools/list` in a deterministic order "to improve LLM prompt cache hit rates." — [MCP changelog](https://modelcontextprotocol.io/specification/2026-07-28/changelog)

### Inferences
- In a multi-agent delivery tool, the hand-off artifact between agents is the main context-engineering decision. That artifact is the summary, the spec, or the diff.
- Loading every MCP tool definition up front works against just-in-time retrieval. Tool search or progressive loading should be considered.

### Gaps
- I did not retrieve quantitative studies of context rot (for example, Chroma's report) or 2026 Anthropic/OpenAI updates on server-side compaction APIs.

## 3. MCP and A2A: state in 2026, adoption, security

### Takeaway
MCP is now governed by the Linux Foundation's Agentic AI Foundation (since Dec 2025) and is the default way to connect tools.

| Revision | What changed |
|---|---|
| 2025-11-25 | Added Tasks, URL-mode elicitation, and Client ID Metadata Documents (CIMD) for auth |
| 2026-07-28 | Large redesign: stateless (no `initialize` handshake, no session IDs), a Multi Round-Trip Request pattern replaces server-initiated sampling and elicitation, Tasks moved to an extension, Roots, Sampling, Logging and Dynamic Client Registration deprecated |

Security is still the weak point. Tool poisoning, rug pulls and prompt injection through data (the confused-deputy pattern) are well documented, and enforcement has to live at the tool-execution layer, not in prompts. A2A v1.0 (stable, 2026) is the complementary agent-to-agent protocol, with 150+ supporting organizations.

### Cited Findings
- **Spec 2025-11-25** (first anniversary release):
  - experimental **Tasks** for durable, long-running requests with polling (SEP-1686)
  - **URL-mode elicitation** (SEP-1036)
  - **Client ID Metadata Documents** and Cross App Access for auth
  - formal governance (SEP-932) and SDK tiering (SEP-1730)

  — [MCP 2025-11-25 changelog](https://modelcontextprotocol.io/specification/2025-11-25/changelog); [MCP blog](https://blog.modelcontextprotocol.io/posts/2025-11-25-first-mcp-anniversary/); [Auth0](https://auth0.com/blog/mcp-november-2025-specification-update/)
- **Spec 2026-07-28** (current), major changes:
  - Protocol-level sessions and the `Mcp-Session-Id` header are removed (SEP-2567).
  - "Make MCP stateless: remove the `initialize`/`notifications/initialized` handshake." Every request carries its protocol version and client capabilities in `_meta`. A new `server/discover` RPC is added (SEP-2575).
  - `subscriptions/listen` replaces the GET endpoint and resource subscribe.
  - `ping` and `logging/setLevel` are removed.
  - SSE resumability is removed.

  — [MCP 2026-07-28 changelog](https://modelcontextprotocol.io/specification/2026-07-28/changelog)
- 2026-07-28, **MRTR (Multi Round-Trip Requests)**: this "replaces the previous approach of sending server-initiated requests, such as `roots/list`, `sampling/createMessage`, or `elicitation/create`." The server returns `resultType: "input_required"`, and the client retries the request with `inputResponses` (SEP-2322). The `elicitationId` and completion notification added in 2025-11-25 are removed. — [MCP changelog](https://modelcontextprotocol.io/specification/2026-07-28/changelog)
- 2026-07-28, **Tasks**: moved out of core into the official extension `io.modelcontextprotocol/tasks`, using `tasks/get` polling and `tasks/update` (SEP-2663). — [MCP changelog](https://modelcontextprotocol.io/specification/2026-07-28/changelog)
- 2026-07-28, **Deprecated**:
  - **Roots, Sampling, Logging** (SEP-2577). Suggested migrations: "integrate directly with LLM provider APIs instead of Sampling", and use stderr or OpenTelemetry instead of Logging.
  - The **HTTP+SSE transport**, replaced by Streamable HTTP.
  - **OAuth Dynamic Client Registration (RFC 7591)**, in favor of CIMD.
  - A 12-month minimum deprecation window now applies (SEP-2596). — [MCP changelog](https://modelcontextprotocol.io/specification/2026-07-28/changelog)
- 2026-07-28, **Auth hardening**:
  - clients MUST validate `iss` per RFC 9207 (SEP-2468)
  - credentials are bound to the issuing authorization server (SEP-2352)
  - `application_type` is required in DCR (SEP-837)

  — [MCP changelog](https://modelcontextprotocol.io/specification/2026-07-28/changelog)
- 2026-07-28, **Other changes**:
  - OpenTelemetry trace context (`traceparent`, `tracestate`, `baggage`) is propagated in `_meta` (SEP-414).
  - Cacheable list results carry `ttlMs` and `cacheScope` (SEP-2549).
  - JSON Schema 2020-12 is allowed for tool schemas (SEP-2106).

  — [MCP changelog](https://modelcontextprotocol.io/specification/2026-07-28/changelog)
- [SUPERSEDED] Anything describing MCP as session-based with an initialize handshake, or relying on server-initiated sampling and elicitation, reflects specs up to 2025-11-25.
- **Governance and adoption**:
  - Anthropic donated MCP to the **Agentic AI Foundation** (a Linux Foundation fund) on Dec 9, 2025, with Block and OpenAI as co-founders and AWS, Google, Microsoft, Cloudflare and Bloomberg as platinum members.
  - In Dec 2025, Anthropic cited more than 10,000 active public servers.

  — [Nordic APIs](https://nordicapis.com/10-interesting-mcp-statistics/), [digitalapplied](https://digitalapplied.com/blog/mcp-adoption-statistics-2026) (secondary)
- **Registry size** (the official registry launched Sep 2025, per [InfoQ](https://infoq.com/news/2025/09/introducing-mcp-registry)). The counts are inconsistent:

  | Count | Date | Source |
  |---|---|---|
  | 9,652 servers | May 2026 | [dev.to](https://dev.to/gentic_news/mcp-hits-10k-servers-97m-monthly-sdk-downloads-by-may-2026-1jbk) |
  | 30,375 servers | Sep 10, 2026 | [dev.to](https://dev.to/amareswer/the-mcp-registry-by-the-numbers-38nc) |
  | 52,042 servers | Oct 28, 2026 | single-blog API query (unverified) |

  97M monthly SDK downloads is also claimed (secondary). All of these are blog figures and unverified.
- **Tool poisoning**: malicious instructions are hidden in tool descriptions that the model reads but users usually cannot see. The Cloud Security Alliance groups three variants (description poisoning, **rug pulls**, **tool shadowing**) under one root cause: "MCP clients inherit trust from servers without continuous verification." — [CSA whitepaper, May 2026](https://labs.cloudsecurityalliance.org/research-rb/csa-whitepaper-mcp-security-tool-poisoning-20260506-csa-styl/)
- **Research**:
  - An arXiv study (Mar 2026) tested 7 MCP clients against 4 tool-poisoning attack types and found tool poisoning the most prevalent client-side weakness. — [arXiv 2603.22489](https://arxiv.org/html/2603.22489v1)
  - Another preprint reports that Claude Desktop, Claude Code and Cursor are susceptible to tool-poisoning prompt injection. — [arXiv 2603.21642](https://arxiv.org/html/2603.21642)
- **Incidents (confused deputy / data-borne injection)**:
  - the May 2025 GitHub MCP server prompt injection, where a malicious issue led to private-repo exfiltration
  - the "lethal trifecta" support-ticket case
  - an Amazon Q VS Code malicious PR
  - CVE-2025-68143/68144/68145 in Anthropic's mcp-server-git
  - a Feb 2026 registry-poisoning case (cloned malicious server)

  — [UpGuard](https://www.upguard.com/blog/mcp-security-incidents); [dev.to incident roundup](https://dev.to/luckypipewrench/the-state-of-mcp-security-2026-incidents-attack-patterns-and-defense-coverage-2h45) (secondary)
- **Mitigations**:
  - OWASP: restrictions enforced only in system prompts can be overridden by injected instructions, so enforcement belongs at the tool-execution layer. — [OWASP](https://owasp.org/www-community/attacks/MCP%5FTool%5FPoisoning)
  - Others recommend hash-pinning approved tool definitions and no auto-approval for untrusted servers. — [CSA](https://labs.cloudsecurityalliance.org/research-rb/csa-whitepaper-mcp-security-tool-poisoning-20260506-csa-styl/)
- **A2A**:
  - Google published A2A in Apr 2025 and donated it to the Linux Foundation in Jun 2025. Founding organizations included AWS, Cisco, Microsoft, Salesforce, SAP and ServiceNow. — [Google](https://developers.googleblog.com/en/google-cloud-donates-a2a-to-linux-foundation/)
  - As of Apr 9, 2026: v1.0 is "the protocol's first stable specification", "more than 150 organizations" support it (up from 50+), and it is integrated into Azure AI Foundry, Copilot Studio and Amazon Bedrock AgentCore Runtime. — [Linux Foundation](https://www.linuxfoundation.org/press/a2a-protocol-surpasses-150-organizations-lands-in-major-cloud-platforms-and-sees-enterprise-production-use-in-first-year)
- **A2A vs MCP**: "A2A defines how agents communicate and coordinate with each other across organizational boundaries," while "MCP defines how agents connect to internal tools and data sources." — [Linux Foundation](https://www.linuxfoundation.org/press/a2a-protocol-surpasses-150-organizations-lands-in-major-cloud-platforms-and-sees-enterprise-production-use-in-first-year)
- **A2A discovery**: the Agent Card is served at `/.well-known/agent-card.json`. In v1.0, `url` and `preferred_transport` were replaced by `supported_interfaces`. — [AAIF builder's guide](https://aaif.io/blog/a2a-v1-0-a-builder-s-guide-part-1-discovery-tasks-and-clients); [docs.rs](https://docs.rs/a2a-rs-core/1.0.0/a2a_rs_core/struct.AgentCard.html) (crate docs, not the spec)

### Inferences
- A tool that builds on MCP in late 2026 should target the stateless 2026-07-28 model. It should avoid adopting Sampling or Roots, and should use CIMD rather than DCR.
- For a software-delivery tool, the highest-risk combination is untrusted repo content plus write tools plus network egress. Permission checks belong in the harness, not the prompt.
- A2A matters only if agents are exposed across organizational or vendor boundaries. Agents inside one tool can use plain function calls or sub-agents.

### Gaps
- A2A governance is unclear. One source says A2A moved into the Agentic AI Foundation in Aug 2026, but I could not confirm this from a primary source.
- The official MCP registry server count is not confirmed by the MCP team.
- I found no primary 2026 vendor advisory for a named tool-poisoning exploit.

## 4. Multi-agent: when it helps and when it hurts

### Takeaway
Multi-agent pays off for **parallel, read-heavy, high-value** work like breadth-first research. Anthropic measured +90.2% on its research eval, at about 15x chat token cost. It hurts when agents write in parallel and make conflicting implicit decisions.

Both camps have since converged (Cognition, Apr 2026) on one design:
- **single-threaded writes**
- read-only sub-agents
- **generator-verifier review with a clean-context reviewer**
- manager-child delegation in map-reduce form

Unstructured swarms remain "mostly a distraction."

### Cited Findings
- Anthropic, "How we built our multi-agent research system" (Jun 13, 2025):
  - **Performance**: an Opus 4 lead with Sonnet 4 sub-agents beat single-agent Opus 4 by **90.2%** on an internal research eval.
  - **Token cost**: agents use about **4x** the tokens of chat, and multi-agent systems about **15x**.
  - **What drives results**: on BrowseComp, token usage alone explains **80%** of performance variance, and adding tool-call count and model choice brings it to **95%**.
  - **Parallelism**: running sub-agents and tool calls in parallel cut research time by up to **90%** for complex queries.

  — [Anthropic](https://www.anthropic.com/engineering/multi-agent-research-system)
- Effort scaling rules from the same post:
  - simple fact-finding: 1 agent, 3–10 tool calls
  - comparisons: 2–4 sub-agents with 10–15 calls each
  - complex research: 10+ sub-agents
  - the lead spawns 3–5 sub-agents in parallel
  - an early failure mode was spawning 50 sub-agents for simple queries

  — [Anthropic](https://www.anthropic.com/engineering/multi-agent-research-system)
- Where it fits poorly: domains where all agents must share context or that have many dependencies. "Most coding tasks have fewer parallelizable subtasks than research." — [Anthropic](https://www.anthropic.com/engineering/multi-agent-research-system)
- Cognition, "Don't Build Multi-Agents" (Walden Yan, Jun 12, 2025):
  - Principle 1: "Share context, and share full agent traces, not just individual messages."
  - Principle 2: "Actions carry implicit decisions, and conflicting decisions carry bad results."
  - Flappy Bird example: parallel sub-agents built a Mario-style background and a mismatched bird.
  - Default: a single-threaded linear agent, plus context compression.

  — [Cognition](https://cognition.com/blog/dont-build-multi-agents)
- Cognition, "Multi-Agents: What's Actually Working" (Apr 22, 2026). Its core claim is that multi-agent works when "writes stay single-threaded" and extra agents contribute intelligence, not actions. Parallel-writer swarms still lack meaningful adoption. — [Cognition](https://cognition.com/blog/multi-agents-working)
- Patterns that work, from the same post:
  1. **Generator-verifier.** Devin plus Devin Review, where "the coding and review agents do not share any context beforehand"; "clean context leads to a notable improvement in capabilities when using a generator-verifier loop". Devin Review finds an average of **2 bugs per PR**, about **58% severe**.
  2. **"Smart friend" escalation** to a stronger model. It "works today when both models are strong". SWE-1.5 paired with Sonnet 4.5 did not work well.
  3. **Manager-child delegation** coordinated through an internal MCP. It is live but "still needs work."

  — [Cognition](https://cognition.com/blog/multi-agents-working)
- Late-2026 practice: Cognition's Devin Bots open tickets, assign them to individual Devin sessions, and merge after CI and Devin Review pass. Cognition has not explained how conflicts between agents are handled. — [The New Stack](https://thenewstack.io/cognition-devin-bots-management/) (secondary)
- A claim of "~50% single-agent vs 25% for two agents splitting work" circulates but could not be verified against Cognition's original. — [echai.ventures](https://echai.ventures/how-founders-use-ai/r/multi-agents-what-s-actually-working--944) (secondary; unverified)

### Inferences
- For a software-delivery tool, the evidence favors the following design. Parallel coders are only defensible with strict isolation (separate worktrees and disjoint files) and a single integrator.

| Role | Shape |
|---|---|
| Planner / manager | One |
| Code-writer | One per change (one writer per worktree or branch) |
| Researchers / explorers | Read-only, can run in parallel |
| Reviewer / verifier | Separate agent with fresh context that sees only the diff |

- A 15x token multiplier means multi-agent should be reserved for tasks where the value covers the cost.

### Gaps
- Neither Cognition post gives cost or success-rate numbers for the multi-agent patterns.
- I found no independent controlled study comparing single- and multi-agent coding systems in 2026.

## 5. Memory and planning

### Takeaway
Long-running coding agents rely on **external state on disk**, not in-context memory:
- progress logs
- structured feature or to-do lists, preferably JSON
- git commits as checkpoints
- an `init.sh`
- memory or instruction files (CLAUDE.md / AGENTS.md)

A fresh context window then rebuilds its state from these files.

### Cited Findings
- Anthropic, "Effective harnesses for long-running agents" (Nov 26, 2025) uses a two-agent harness:
  - An **initializer agent** runs first and creates `init.sh`, `claude-progress.txt`, a JSON feature list (200+ features for a claude.ai clone, each with steps and a `passes` flag, all starting as failing), and an initial git commit.
  - A **coding agent** then makes one feature's worth of progress per session.
  - The two differ only in their initial user prompt.

  — [Anthropic](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
- JSON was chosen over Markdown for the feature list because models are less likely to overwrite JSON inappropriately. Coding agents may only flip `passes`. "It is unacceptable to remove or edit tests." — [Anthropic](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
- **Git as checkpoint**: commit after each change so the agent can "use git to revert bad code changes and recover working states." Each session ends with a commit and a progress update, leaving the code in a mergeable state. — [Anthropic](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
- Observed failure modes:
  - trying to one-shot the app
  - declaring the project done too early
  - marking features done without verifying them
  - wasting time working out how to run the app

  Fixes: work on one feature at a time, verify before marking a feature passing, and give the agent end-to-end testing tools ("dramatically improved performance"). — [Anthropic](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
- An agentic memory tool (file-based, in public beta with Sonnet 4.5) and note-taking outside the context window, for example in the Pokémon agent. — [Anthropic context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- AGENTS.md is one of the projects under the Agentic AI Foundation alongside MCP and goose. — [AAIF builder's guide](https://aaif.io/blog/a2a-v1-0-a-builder-s-guide-part-1-discovery-tasks-and-clients) (secondary for this point)
- Planning as orchestration: Anthropic's research lead saves its plan to memory because context beyond 200,000 tokens gets truncated. — [Anthropic multi-agent](https://www.anthropic.com/engineering/multi-agent-research-system)

### Inferences
- A delivery tool's "memory" should be versioned repo artifacts (plan file, task list, progress log, commits). Opaque vector stores are harder to audit and roll back.

### Gaps
- I did not retrieve sources on vector or graph long-term memory products (for example Mem0, Letta, Zep) or benchmarks comparing them.
- I did not retrieve primary documentation for Claude Code or Codex checkpoint and rewind features.

## 6. Evals

### Takeaway
Anthropic's Jan 2026 guide is the current reference:
- grade **outcomes** (environment state), not paths
- combine code-based, model-based and human graders
- run multiple trials, and report **pass@k** (at least one success) or **pass^k** (all succeed) depending on the product
- keep separate capability and regression suites
- start with 20–50 tasks taken from real failures

Public benchmarks are saturating. SWE-bench Verified went from about 40% to over 80% in a year, and vals.ai stopped running Terminal-Bench 2.0 on new models. Harness choice moves scores substantially.

### Cited Findings
- Anthropic, "Demystifying evals for AI agents" (Jan 9, 2026) defines task, trial, grader, **transcript/trajectory**, **outcome** (for example, checking that the reservation exists in the database, not that the agent said it booked), evaluation harness, and agent harness. "Evaluating 'an agent' means evaluating the harness and model together." — [Anthropic](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
- **pass@k** rises with k, and **pass^k** falls with k. At 75% per-trial success, pass^3 is about 42%. Use pass^k when consistency matters, as in customer-facing agents. — [Anthropic](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
- **Graders**:
  - code-based: fast, objective, but brittle
  - model-based (rubrics, pairwise comparison): flexible, but non-deterministic and needs human calibration
  - human: the gold standard, but slow

  Use "deterministic graders where possible, LLM graders where necessary, and human graders judiciously", and give partial credit on multi-part tasks. — [Anthropic](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
- Capability evals should start at a low pass rate. Regression evals should be near 100%. Capability tasks "graduate" into the regression suite. "20-50 simple tasks drawn from real failures is a great start." "Read the transcripts!" — [Anthropic](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
- Benchmarks referenced in the same guide:

  | Benchmark | What it tests |
  |---|---|
  | SWE-bench Verified | coding, graded by test suite; ~40% to >80% in one year |
  | Terminal-Bench 2.0 | end-to-end terminal tasks |
  | τ-Bench / τ2-Bench | multi-turn retail and airline tasks |
  | BrowseComp | finding hard-to-locate information on the web |
  | WebArena | browser tasks |
  | OSWorld | full operating-system control |

  The guide also cites CORE-Bench and METR as examples where grading bugs depressed scores. — [Anthropic](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
- **LLM-as-judge in practice**: Anthropic's research system uses "a single LLM call with a single prompt outputting scores from 0.0-1.0 and a pass-fail grade". The rubric covers factual accuracy, citation accuracy, completeness, source quality and tool efficiency. The initial eval set had about 20 queries. — [Anthropic multi-agent](https://www.anthropic.com/engineering/multi-agent-research-system)
- **SWE-bench Pro** (Scale AI): the public set has 731 tasks across Python, Go, TypeScript and JavaScript. It was designed to resist contamination and saturation. — [Scale](https://scale.com/blog/swe-bench-pro); [Scale leaderboard](https://labs.scale.com/leaderboard/swe_bench_pro_public)
- Late-2026 SWE-bench Pro scores (aggregators only, unverified):
  - best open-weights results about 62% (Qwen3.8-Flash-Next 62.5%, GLM-5.2 62.1%)
  - a vendor-reported 89.9% for Claude Opus 5.5, not from Scale's standardized runs

  — [benchmarklist](https://benchmarklist.com/benchmarks/swe_bench_pro_v2/)
- **Terminal-Bench 2.0** scores conflict by harness:
  - Apr 2026: Codex on GPT-5.5 at 82.0%
  - Jun 2026: GPT-5.5 (Terminus 2) at 73.2%, Claude Opus 4.8 (Terminus 2) at 70.0%
  - vals.ai no longer runs it on new models because performance has saturated

  — [morphllm](https://www.morphllm.com/terminal-bench-2); [vals.ai](https://vals.ai/benchmarks/terminal-bench-2)

### Inferences
- The same model scores 70–82% on Terminal-Bench depending on the harness. A delivery tool should therefore evaluate its own harness on its own task suite, because public leaderboards measure model plus harness.
- For a delivery tool, the natural outcome graders are: CI passes, tests that were not modified, and merge acceptance. pass^k is the right reliability metric for unattended runs.

### Gaps
- I did not retrieve OpenAI's current agent-eval guidance (for example, trace grading in the Agents SDK or Evals docs).
- I did not retrieve official tbench.ai or Scale leaderboard snapshots, and the score figures above are aggregator data.

## 7. Sandboxing, permissions and human-in-the-loop

### Takeaway
Production coding agents combine OS-level sandboxing with permission and approval policies:
- **Local agents**: Seatbelt on macOS, bubblewrap (and Landlock) on Linux.
- **Cloud or untrusted execution**: microVMs (Firecracker, as used by E2B) or gVisor.
- **Policies**: filesystem scoped to the workspace, network denied by default or limited to an allowlist, protected paths (.git), and escalating approval modes.

Sandboxing is what makes it safe to cut approval prompts.

### Cited Findings
- **Claude Code isolation**:
  - The sandbox is enforced at the OS level (Seatbelt on macOS, bubblewrap on Linux) and covers every subprocess, not just Claude's own file tools.
  - Two modes: auto-allow for sandboxed commands, or keep regular permission prompts.
  - Commands that cannot run sandboxed fall back to the permission flow, and a new network domain prompts for approval.

  — [Claude Code docs](https://code.claude.com/docs/en/sandboxing)
- Anthropic reports that in internal use, sandboxing "safely reduces permission prompts by 84%" (vendor figure). — [Anthropic engineering](https://anthropic.com/engineering/claude-code-sandboxing)
- **OpenAI Codex**:
  - Sandbox modes: `read-only`, `workspace-write` (the default low-friction mode; no network unless `network_access = true`), and `danger-full-access`.
  - Approval policies: on-request, never, and so on. The "Auto" preset is workspace-write plus on-request approvals.
  - `.git/` and `.codex/` stay read-only even in workspace-write.

  — [OpenAI Codex sandboxing](https://developers.openai.com/codex/concepts/sandboxing); [Agent approvals & security](https://developers.openai.com/codex/agent-approvals-security)
- Codex on Linux reportedly uses Landlock plus bubblewrap. — [Mintlify mirror](https://www.mintlify.com/openai/codex/concepts/sandboxing) (third-party)
- **Cloud sandboxes**:
  - E2B runs each sandbox in a Firecracker microVM with its own kernel. Firecracker also underpins AWS Lambda and Vercel Sandbox.
  - gVisor is a user-space kernel that intercepts syscalls, used by Cloud Run, GKE Sandbox and Modal.
  - MicroVMs are generally ranked stronger for fully untrusted code.
  - Neither approach blocks egress or enforces business permissions by default.

  — [Vercel: gVisor vs microVMs](https://vercel.com/i/gvisor-vs-microvms); [Fly.io](https://fly.io/learn/firecracker-vs-gvisor/) (vendor sources)
- Cold-start and resume figures vary: E2B cold start is about 150ms per one comparison, and resume measured 662ms in an independent benchmark. — [LogRocket](https://blog.logrocket.com/comparing-ai-agent-sandbox-platforms-e2b-modal-daytona-and-more/)
- Prompt-level restrictions are not a security boundary. Enforcement belongs at the tool-execution layer. — [OWASP](https://owasp.org/www-community/attacks/MCP%5FTool%5FPoisoning)

### Inferences
- A delivery tool that lets agents commit and push should enforce all of the following in code:
  - workspace-only writes
  - protected `.git` refs, or pushes only through a gated step
  - network egress allowlists
  - a human approval gate before merge or deploy

### Gaps
- I did not fetch primary documentation for Claude Code permission modes (plan, acceptEdits, bypass) or for OpenAI Agents SDK guardrails and human-in-the-loop features.

## 8. Observability

### Takeaway
OpenTelemetry's GenAI semantic conventions are the emerging standard for agent tracing, but they are still marked **Development** (not stable). They include agent spans such as `create_agent`, `invoke_agent {name}`, and `execute_tool {name}`. MCP 2026-07-28 now propagates W3C trace context through `_meta`, so a trace can be followed end to end across tool servers. Vendors gate support behind opt-in flags.

### Cited Findings
- The OTel spec page "Semantic Conventions for GenAI agent and framework spans" has **Development** status. It covers create-agent, invoke-agent (client and internal), plan, and execute-tool spans, and it extends the base GenAI span conventions. — [OpenTelemetry](https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-agent-spans/index.md); [GitHub source](https://raw.githubusercontent.com/open-telemetry/semantic-conventions-genai/main/docs/gen-ai/gen-ai-agent-spans.md)
- Span names follow `invoke_agent {agent_name}` and `execute_tool {tool_name}`, with `gen_ai.operation.name` set to `invoke_agent` / `execute_tool`. — [Honeycomb docs](https://docs.honeycomb.io/send-data/use-cases/agents.md)
- Datadog requires the `gen_ai_latest_experimental` opt-in to emit the v1.37+ GenAI conventions, a sign the conventions are still unstable. — [Datadog](https://docs.datadoghq.com/llm_observability/instrument/otel_instrumentation/)
- OpenLLMetry has a competing community draft (for example `gen_ai.agent.invoke`). — [OpenLLMetry issue](https://github.com/traceloop/openllmetry/issues/3460)
- MCP 2026-07-28 documents propagation of `traceparent`, `tracestate` and `baggage` in `_meta` (SEP-414), and recommends OpenTelemetry instead of the deprecated MCP Logging. — [MCP changelog](https://modelcontextprotocol.io/specification/2026-07-28/changelog)
- Anthropic stresses reading transcripts as a core eval and debug practice ("Read the transcripts!"). Its research system needed full production tracing to diagnose agent failures. — [Anthropic evals](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents); [Anthropic multi-agent](https://www.anthropic.com/engineering/multi-agent-research-system)

### Inferences
- Emitting OTel GenAI spans now, even though they are in Development, keeps a delivery tool vendor-neutral. Langfuse, LangSmith, Braintrust, Datadog and Honeycomb can all ingest OTel.

### Gaps
- I did not retrieve primary sources on LangSmith, Langfuse or Braintrust features, pricing or OTel support in 2026. This needs a follow-up.
- I could not confirm the exact current semconv version or whether any GenAI attributes reached Stable in 2026.
