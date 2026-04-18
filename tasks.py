"""Entry points for the Eco map evaluation workflow.

Phase 1 (weekly):   inv prep --cycle 13
Phase 2 (repeated): inv roll --cycle 13 [--count N] [--seed N]
"""

import sys

# Force UTF-8 on stdout/stderr so unicode in Discord content and Eco logs
# doesn't blow up on Windows (default cp1252).
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from invoke import task  # noqa: E402


@task(help={"cycle": "Current Eco cycle number (e.g. 13)"})
def prep(ctx, cycle):
    from eco_map_generator import prep as prep_module

    prep_module.run(ctx, cycle=int(cycle))


@task(help={"days": "How many days of suggestions-forum history to dump (default 60)"})
def forum_dump(ctx, days=60):
    from eco_map_generator import prep as prep_module

    prep_module.run_forum_dump(ctx, since_days=int(days))


@task(
    help={
        "cycle": "Cycle number (used for naming + full channel pull)",
        "days": "Lookback window for suggestions + forum (default 60)",
    }
)
def brief(ctx, cycle, days=60):
    from eco_map_generator import prep as prep_module

    prep_module.run_brief(ctx, cycle=int(cycle), days=int(days))


@task(help={"check": "Print lockdown state and exit without running anything"})
def mods_sync(ctx, check=False):
    """Clone eco-mods + eco-mods-public on kai-server and copy to the Eco install.
    Lockdown-gated (Network.eco must be PublicServer=false, Password=password)."""
    from eco_map_generator import mods, safety

    safety.assert_network_locked_down()
    if check:
        print("lockdown ok — would call eco.copy-private-mods + eco.copy-public-mods")
        return
    mods.sync(ctx)


@task(
    help={
        "names": "Comma-separated mod folder names to remove (UserCode/<name>). "
        "Defaults to every DF* mod — Deepflame asked for a disable in cycle 13."
    }
)
def mods_disable(ctx, names=""):
    """rm -rf the listed mod folders from kai-server's EcoServer Mods/UserCode/.
    Run AFTER mods-sync (sync reinstalls everything from git)."""
    from eco_map_generator import mods

    if names:
        arr = [n.strip() for n in names.split(",") if n.strip()]
    else:
        arr = [
            "DFBargeIndustries",
            "DFEasierShopCart",
            "DFEngineering",
            "DFGlobalPlanetaryDefense",
        ]
    mods.disable_on_server(ctx, arr)


@task(
    help={
        "cycle": "Current Eco cycle number",
        "count": "How many rolls to generate (default 1)",
        "seed": "Specific seed to use. If set, overrides random and forces count=1.",
    }
)
def roll(ctx, cycle, count=1, seed=None):
    from eco_map_generator import roll as roll_module

    roll_module.run(
        ctx,
        cycle=int(cycle),
        count=int(count),
        seed=int(seed) if seed is not None else None,
    )
