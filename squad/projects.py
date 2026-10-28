"""Projects a match can work on: the demo sandboxes plus any folders passed to `squad start`."""

import os
from dataclasses import dataclass
from pathlib import Path

from .paths import SANDBOX_DIR


@dataclass(frozen=True)
class Project:
    name: str
    path: Path


def discover(extra: list[Path] = (), *, demo: bool = False, cwd: Path | None = None) -> dict[str, Project]:
    """The folder you start in (copied, never edited in place), any --project folders, and the demo sandboxes if asked."""
    found: dict[str, Project] = {}
    if cwd is not None:
        found[cwd.name] = Project(cwd.name, cwd)
    if demo:
        found |= {p.name: Project(p.name, p) for p in sorted(SANDBOX_DIR.iterdir()) if p.is_dir() and not p.name.startswith(".")}
    for path in extra:
        path = Path(path).expanduser().resolve()
        if not path.is_dir():
            raise ValueError(f"not a folder: {path}")
        found[path.name] = Project(path.name, path)
    return found


def overview(path: Path, limit: int = 60) -> list[str]:
    """A short file listing so triage knows what kind of project it is looking at."""
    skip = {".git", ".venv", "venv", "node_modules", "runs", "__pycache__", "dist", "build"}
    names: list[str] = []
    for root, dirs, files in os.walk(path):
        dirs[:] = sorted(d for d in dirs if d not in skip)
        names += [str((Path(root) / f).relative_to(path)) for f in sorted(files)]
        if len(names) >= limit:
            break
    return names[:limit]
