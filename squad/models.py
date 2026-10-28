from dataclasses import dataclass, field
from enum import Enum


class Role(str, Enum):
    DUELIST = "Duelist"
    INITIATOR = "Initiator"
    CONTROLLER = "Controller"
    SENTINEL = "Sentinel"


@dataclass(frozen=True)
class Ability:
    """One of an agent's MCP tools, keyed like a game ability bar."""

    key: str
    label: str
    tool: str


@dataclass(frozen=True)
class AgentSpec:
    name: str
    role: Role
    model: str
    system: str
    abilities: tuple[Ability, ...]
    deliverable: str  # the local tool the agent calls to hand in its work

    @property
    def tools(self) -> set[str]:
        return {a.tool for a in self.abilities}


@dataclass(frozen=True)
class Ticket:
    id: str
    title: str
    type: str
    description: str
    labels: tuple[str, ...]
    repos: tuple[str, ...]
    sandbox: str
    linked_docs: tuple[str, ...] = ()
    acceptance_criteria: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, raw: dict) -> "Ticket":
        return cls(
            id=raw["id"], title=raw["title"], type=raw["type"], description=raw["description"],
            labels=tuple(raw.get("labels", ())), repos=tuple(raw.get("repos", ())),
            sandbox=raw["sandbox"], linked_docs=tuple(raw.get("linked_docs", ())),
            acceptance_criteria=tuple(raw.get("acceptance_criteria", ())),
        )


@dataclass
class AgentRun:
    agent: str
    deliverable: dict
    steps: int
    tool_calls: int
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class MatchResult:
    success: bool
    ticket_id: str
    squad: list[str]
    attempts: int
    commit: str | None
    reason: str
    run_dir: str
    trace_path: str
    stats: dict = field(default_factory=dict)
    answer: str = ""
