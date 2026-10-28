"""Projects a match can work on: the demo sandboxes plus any folders passed to `squad start`."""

from dataclasses import dataclass
from pathlib import Path

from .paths import SANDBOX_DIR


@dataclass(frozen=True)
class Project:
    name: str
    path: Path


def discover(extra: list[Path] = ()) -> dict[str, Project]:
    found = {p.name: Project(p.name, p) for p in sorted(SANDBOX_DIR.iterdir()) if p.is_dir() and not p.name.startswith(".")}
    for path in extra:
        path = Path(path).expanduser().resolve()
        if not path.is_dir():
            raise ValueError(f"not a folder: {path}")
        found[path.name] = Project(path.name, path)
    return found
