"""User configuration: the Anthropic key and the MCP servers, read from squad.config.json (never committed)."""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from .paths import ROOT

PLACEHOLDER = "REPLACE_ME"


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Config:
    api_key: str | None = None
    mcp_servers: dict = field(default_factory=dict)


def config_path() -> Path:
    return Path(os.environ.get("SQUAD_CONFIG", ROOT / "squad.config.json"))


def load_config(path: Path | None = None) -> Config:
    """The ANTHROPIC_API_KEY environment variable overrides the file. A placeholder key counts as unset."""
    path = path or config_path()
    raw: dict = {}
    if path.is_file():
        try:
            raw = json.loads(path.read_text())
        except ValueError as err:
            raise ConfigError(f"{path} is not valid JSON: {err}") from err
    key = os.environ.get("ANTHROPIC_API_KEY") or (raw.get("anthropic") or {}).get("api_key")
    if not key or PLACEHOLDER in key:
        key = None
    servers = raw.get("mcpServers") or {}
    for name, spec in servers.items():
        if not isinstance(spec, dict) or "command" not in spec:
            raise ConfigError(f"{path}: mcpServers.{name} needs a \"command\"")
    return Config(api_key=key, mcp_servers=servers)
