from .trace import Trace


class Blackboard:
    """Shared context. Agents hand work to each other through here, never directly."""

    def __init__(self, trace: Trace) -> None:
        self._data: dict = {}
        self._trace = trace

    def write(self, key: str, value, author: str) -> None:
        self._data[key] = value
        self._trace.emit("blackboard", key=key, author=author)

    def read(self, key: str, default=None):
        return self._data.get(key, default)

    def snapshot(self) -> dict:
        return dict(self._data)
