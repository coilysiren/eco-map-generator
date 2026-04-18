"""Pre-flight safety checks for server-mutating tasks.

Kai keeps the git-tracked `eco-configs/Configs/Network.eco` in a private,
password-locked state AT ALL TIMES — even during live cycles. Going public
is a runtime flip applied directly on kai-server's on-disk copy (see
`golive.py`); git never carries a public version. That way a hasty
`copy-configs` during live never accidentally re-privatizes the server,
and a hasty one during prep never accidentally publishes.
"""

import json

from . import worldgen

NETWORK_CONFIG = worldgen.ECO_CONFIGS / "Configs" / "Network.eco"

LOCKED_PUBLIC_SERVER = False
LOCKED_PASSWORD = "password"


class NetworkLockdownError(RuntimeError):
    pass


def assert_network_locked_down() -> None:
    """Fail loudly if eco-configs/Configs/Network.eco in git has drifted
    off the locked values. Git should always carry the private state."""
    data = json.loads(NETWORK_CONFIG.read_text(encoding="utf-8"))
    public = data.get("PublicServer")
    password = data.get("Password")
    bad: list[str] = []
    if public is not LOCKED_PUBLIC_SERVER:
        bad.append(f"PublicServer={public!r} (expected {LOCKED_PUBLIC_SERVER!r})")
    if password != LOCKED_PASSWORD:
        bad.append(f"Password={password!r} (expected {LOCKED_PASSWORD!r})")
    if bad:
        raise NetworkLockdownError(
            "Network.eco (git) is NOT in locked state: "
            + "; ".join(bad)
            + f"\n  path: {NETWORK_CONFIG}\n"
            "Fix this in eco-configs and re-commit before proceeding."
        )
