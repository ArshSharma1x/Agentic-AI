"""The match trace: an append-only JSONL log that the CLI, the tests and a future game UI all read.

Every line is {"t": seconds since match start, "type": <event type>, ...fields}. Event types:
match_start, draft, phase, agent_start, tool_call, tool_result, agent_done,
blackboard, verdict, retry, approval, commit, match_end.
"""

import json
import time
from collections.abc import Callable
from pathlib import Path


class Trace:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self.events: list[dict] = []
        self.listeners: list[Callable[[dict], None]] = []
        self._start = time.monotonic()

    def emit(self, type: str, **fields) -> dict:
        event = {"t": round(time.monotonic() - self._start, 2), "type": type, **fields}
        self.events.append(event)
        if self.path:
            with self.path.open("a") as f:
                f.write(json.dumps(event) + "\n")
        for listener in self.listeners:
            listener(event)
        return event

    @staticmethod
    def load(path: Path) -> list[dict]:
        return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
