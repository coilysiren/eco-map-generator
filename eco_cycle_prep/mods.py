"""Mod workflow helpers for cycle prep:

- sync: clone eco-mods + eco-mods-public on kai-server and copy into
  the Eco install (via existing `inv eco.copy-*-mods` tasks in
  infrastructure/src/eco.py).
- check: query mod.io for each third-party mod listed in eco-mods/README.md
  and report latest version vs. what's installed.
- disable: list of mod folder names to remove from the install post-sync
  (used for cycle-by-cycle disables like Deepflame 2026-04 request).
"""

import re
from pathlib import Path

from invoke.context import Context

from . import remote, safety

ECO_MODS = Path.home() / "projects" / "eco-mods"
ECO_MODS_PUBLIC = Path.home() / "projects" / "eco-mods-public"
MODS_README = ECO_MODS / "README.md"

MODIO_RE = re.compile(r"mod\.io/g/eco/m/([\w\-]+)")


def list_modio_slugs() -> list[tuple[str, str]]:
    """Return (display_name, mod.io slug) pairs parsed from eco-mods/README.md."""
    out: list[tuple[str, str]] = []
    for line in MODS_README.read_text(encoding="utf-8").splitlines():
        m = MODIO_RE.search(line)
        if not m:
            continue
        # Bullet lines look like: `- [DisplayName](mod.io/g/eco/m/slug)`
        name_match = re.search(r"\[([^\]]+)\]", line)
        display = name_match.group(1) if name_match else m.group(1)
        out.append((display, m.group(1)))
    return out


def sync(ctx: Context) -> None:
    """Re-clone eco-mods + eco-mods-public on kai-server and copy them into
    the Eco install. Guarded by Network.eco lockdown (we will not sync mods
    into a public server)."""
    safety.assert_network_locked_down()
    print("-- syncing private mods (eco-mods) on kai-server")
    remote.ssh(ctx, f"cd {remote.INFRA_DIR} && {remote.REMOTE_INV} eco.copy-private-mods")
    print("-- syncing public mods (eco-mods-public) on kai-server")
    remote.ssh(ctx, f"cd {remote.INFRA_DIR} && {remote.REMOTE_INV} eco.copy-public-mods")


def disable_on_server(ctx: Context, names: list[str]) -> None:
    """Delete the given mod folder names from the server's UserCode dir.
    Idempotent; missing names are a no-op. Guarded by lockdown."""
    safety.assert_network_locked_down()
    if not names:
        return
    paths = [
        f"{remote.ECO_SERVER_DIR}/Mods/UserCode/{n}" for n in names
    ]
    print(f"-- disabling {len(names)} mods on kai-server: {', '.join(names)}")
    remote.ssh(ctx, "rm -rfv " + " ".join(paths))
