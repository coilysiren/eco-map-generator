"""Pre-flight safety checks for server-mutating tasks.

Kai keeps the Eco server in a private, password-locked state while iterating
on cycle setup (world-gen rolls, config tweaks, mod installs, etc). Letting
the server go public with the rolling seeds and half-finished mod set would
leak a broken cycle to real players. These checks enforce the invariant.
"""

import json
from pathlib import Path

from . import worldgen

NETWORK_CONFIG = worldgen.ECO_CONFIGS / "Configs" / "Network.eco"

LOCKED_PUBLIC_SERVER = False
LOCKED_PASSWORD = "password"

GO_LIVE_PUBLIC_SERVER = True
GO_LIVE_PASSWORD = ""


class NetworkLockdownError(RuntimeError):
    pass


def assert_network_locked_down() -> None:
    """Fail loudly if eco-configs/Configs/Network.eco would push the server
    to a public state. Call this before any task that copies configs to
    kai-server or restarts the server."""
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
            "Network.eco is NOT in cycle-prep lockdown: "
            + "; ".join(bad)
            + f"\n  path: {NETWORK_CONFIG}\n"
            "Fix this (and commit/push eco-configs) before running "
            "any server-mutating task."
        )


def go_live(_: Path = NETWORK_CONFIG) -> None:
    """Flip Network.eco to its public/go-live state. Caller is responsible
    for committing + pushing eco-configs and then running `inv eco.copy-configs`."""
    data = json.loads(NETWORK_CONFIG.read_text(encoding="utf-8"))
    data["PublicServer"] = GO_LIVE_PUBLIC_SERVER
    data["Password"] = GO_LIVE_PASSWORD
    NETWORK_CONFIG.write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        f"flipped {NETWORK_CONFIG} to go-live "
        f"(PublicServer={GO_LIVE_PUBLIC_SERVER}, Password={GO_LIVE_PASSWORD!r}).\n"
        "next: commit + push eco-configs, then `inv eco.copy-configs` on kai-server."
    )
