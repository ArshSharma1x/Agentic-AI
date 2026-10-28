# Vision

A valorant themed, multi-agent software delivery team. Agents are drafted into a squad by role, like Valorant agents, and the squad takes a ticket from requirements to verified delivery, using MCP tools for the company's systems.

## Core concept

### Roles (Valorant-style classes)

| Class | Job in the SDLC | Example agents |
|---|---|---|
| **Duelist** | Executes: writes code and makes the change | SWE agent, refactor agent |
| **Initiator** | Gathers intel: pulls context from the company's systems before anyone acts | Research agent (Jira, Confluence, Figma, DB schema) |
| **Controller** | Plans and coordinates: breaks work down, sequences handoffs, tracks state | PM agent, architect agent |
| **Sentinel** | Holds and verifies: checks output against acceptance criteria before anything ships | QA agent, security reviewer, CFO/cost check |

Each agent's abilities are its MCP tools. An Initiator's abilities are read-only access to Jira, Confluence, Figma and the DB. A Duelist's abilities are Git and the filesystem.

### Agent select (squad drafting)

Before a match, the orchestrator drafts the squad for the task, the way a Valorant team picks agents at agent select. The draft rules are explicit and inspectable, and every pick is logged with its reasoning:

- Ambiguous requirements → add an Initiator first (gather context before building)
- Multi-repo or cross-team work → add a Controller (plan before executing)
- Security-sensitive or payments code → add a second Sentinel (extra verification gate)
- Small, well-specified bug → minimal squad: one Initiator, one Duelist, one Sentinel

## Game-style UI

The product is a graphical, video-game-style interface, not a terminal. Designs live in Figma: https://www.figma.com/design/pi5xQtEN5ZFzlOaWVtvaFA

- **Agent Select screen**: a mission brief on the left (ticket, detected signals, recommended draft), the roster in the middle, the selected agent's abilities on the right, and the squad bar with a LOCK IN button at the bottom.
- **Live Match HUD**: a phase tracker on top, the squad with status and budget bars on the left, a pipeline "battlefield" with the shared blackboard and live diff in the middle, a kill-feed-style match feed on the right, and a bottom bar with the active agent's abilities, match stats and an autonomy control (manual, semi-auto, full-auto) plus PAUSE and INTERVENE.
- **Characters**: each agent is a named character with a role emblem. Working names so far: FORGE and RIVET (Duelists), RADAR and CIPHER (Initiators), ATLAS and ARCHON (Controllers), AEGIS and WARDEN (Sentinels). Abilities (Q, E, C, X) are the agent's MCP tools, with X as the ultimate.
- **Planned**: a Match Result and replay screen.

## How a match plays out

1. **Agent select**: the orchestrator drafts the squad.
2. **Intel round**: Initiators pull context through MCP (Jira, Confluence, Figma, Git, DB, Slack).
3. **Plan**: the Controller writes the plan and acceptance criteria to a shared blackboard.
4. **Execute**: Duelists implement the change on a branch.
5. **Verify**: Sentinels run tests, review, and check against criteria. A failure sends the round back to the Duelist, up to a retry limit.
6. **Result**: a PR or report, plus a match replay showing every handoff and decision.

## Planned architecture

- **Orchestrator**: a state machine over the shared blackboard. It drafts the squad, handles handoffs and retries.
- **Agents**: a role prompt, an allowed tool list, and a model tier. Workers use `claude-sonnet-5-5`, drafting uses `claude-haiku-5-5`, and hard reasoning can use `claude-opus-5-5`.
- **MCP layer**: one MCP server per external system. Local stand-ins (filesystem, git, SQLite) come first, so the demo runs without company accounts.
- **Blackboard**: the shared context store. Agents read and write there, not to each other directly.
- **Match replay**: a timeline of agent decisions, tool calls, and verification results, for debugging and for demos.

## Roadmap

**Phase 1: MVP (one match)**
- Four roles and the draft logic
- Local MCP servers: filesystem, git, and a mock ticket source
- Sentinel gate with a retry limit
- Match replay as a JSON trace, rendered as a simple HTML page

**Phase 2: Real integrations**
- MCP servers for Jira, Confluence, Figma, and Slack
- Multi-repo support
- Cost tracking per match (the CFO agent's job)

**Phase 3: Autonomy and evaluation**
- The draft logic learns from match outcomes
- An eval suite of seeded tickets with known-good outcomes
- Agents can request a role swap mid-match, like a mid-round rotation

## What this demonstrates

- Multi-agent orchestration with explicit handoffs and verification gates
- MCP integration across the tools a real engineering team uses
- Explainable squad drafting, with the reasoning logged for each decision
- Evaluation: measured outcomes, not just demos
- Product thinking: a theme that makes the system easy to explain to non-engineers

## Status

Concept stage. No code yet.

## Open questions

- Language and framework preference (Python with the Anthropic SDK and the MCP Python SDK is the proposed default)
- Target demo: a CLI, or a local web UI with the match replay
- Which external system to wire first beyond the local stand-ins
- Agent identity: named characters with portraits and abilities, or abstract roles
