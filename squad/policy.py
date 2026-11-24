"""Per-repo policy, in `.agentic.toml`. It is always read from the BASE commit, so a change cannot loosen the rules
that judge it, and changing the file itself counts as tampering.

    network = "none"            # or "loopback": tests may use localhost, never the internet
    require_tests = false       # true: a change nothing can test is FAIL instead of UNVERIFIED
    allow_test_changes = false  # true: edits to existing tests are reported, and the edited tests are run
    sensitive = ["payments/**"] # changes here are UNVERIFIED until a human reviews them
    timeout = 180               # seconds per test run
"""

import fnmatch
import tomllib
from dataclasses import asdict, dataclass

from .sandbox import NETWORK_MODES

POLICY_FILE = ".agentic.toml"


class PolicyError(Exception):
    pass


@dataclass(frozen=True)
class Policy:
    network: str = "none"
    require_tests: bool = False
    allow_test_changes: bool = False
    sensitive: tuple[str, ...] = ()
    timeout: int = 180
    source: str = "default"

    def touches_sensitive(self, paths: list[str]) -> list[str]:
        return sorted(p for p in paths if any(fnmatch.fnmatch(p, g) for g in self.sensitive))

    def to_dict(self) -> dict:
        return asdict(self)


def parse(text: str | None, source: str) -> Policy:
    if not text:
        return Policy()
    try:
        raw = tomllib.loads(text)
    except tomllib.TOMLDecodeError as err:
        raise PolicyError(f"{POLICY_FILE} at {source} is not valid TOML: {err}") from err
    known = {"network", "require_tests", "allow_test_changes", "sensitive", "timeout"}
    if unknown := set(raw) - known:
        raise PolicyError(f"{POLICY_FILE}: unknown setting(s) {', '.join(sorted(unknown))}")
    policy = Policy(
        network=raw.get("network", "none"), require_tests=bool(raw.get("require_tests", False)),
        allow_test_changes=bool(raw.get("allow_test_changes", False)), sensitive=tuple(raw.get("sensitive", ())),
        timeout=int(raw.get("timeout", 180)), source=source,
    )
    if policy.network not in NETWORK_MODES:
        raise PolicyError(f"{POLICY_FILE}: network must be one of {NETWORK_MODES}")
    return policy
