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
    from eco_cycle_prep import prep as prep_module

    prep_module.run(ctx, cycle=int(cycle))


@task(help={"days": "How many days of suggestions-forum history to dump (default 60)"})
def forum_dump(ctx, days=60):
    from eco_cycle_prep import prep as prep_module

    prep_module.run_forum_dump(ctx, since_days=int(days))


@task(
    help={
        "cycle": "Cycle number (used for naming + full channel pull)",
        "days": "Lookback window for suggestions + forum (default 60)",
    }
)
def brief(ctx, cycle, days=60):
    from eco_cycle_prep import prep as prep_module

    prep_module.run_brief(ctx, cycle=int(cycle), days=int(days))


@task(help={"check": "Print lockdown state and exit without running anything"})
def mods_sync(ctx, check=False):
    """Clone eco-mods + eco-mods-public on kai-server and copy to the Eco install.
    Lockdown-gated (Network.eco must be PublicServer=false, Password=password)."""
    from eco_cycle_prep import mods, safety

    safety.assert_network_locked_down()
    if check:
        print("lockdown ok — would call eco.copy-private-mods + eco.copy-public-mods")
        return
    mods.sync(ctx)


@task(
    help={
        "cycle": "Cycle number",
        "start-ts": "Unix timestamp of go-live. Get it from "
        "https://r.3v.fi/discord-timestamps/",
        "sync-network": "Also write matching DetailedDescription back into "
        "eco-configs/Configs/Network.eco (default on).",
    }
)
def ad(ctx, cycle, start_ts, sync_network=True):
    """Emit the server-ad markdown block for the main Eco Discord.
    Prints to stdout (paste target) and saves a copy under rolls/_prep/.
    Pulls server-id + invite from SSM, collab/meteor/size from eco-configs,
    mod lists from eco-mods + eco-mods-public."""
    from eco_cycle_prep import announce

    announce.run(cycle=int(cycle), start_ts=int(start_ts))
    if sync_network:
        announce.sync_network_description(cycle=int(cycle))


@task(help={"cycle": "Cycle number"})
def eco_configs_post(ctx, cycle):
    """Emit the cycle kickoff post for Sirens' own #eco-configs channel.
    Different format from `inv ad`: longer prose, mod.io links, no invite
    or server-id headers. Prints to stdout and saves under rolls/_prep/."""
    from eco_cycle_prep import announce

    announce.run_eco_configs(cycle=int(cycle))


@task(
    help={
        "names": "Comma-separated mod folder names to remove (UserCode/<name>). "
        "Prefer deleting from the eco-mods repo instead; use this only for "
        "ephemeral overrides between syncs."
    }
)
def mods_disable(ctx, names):
    """rm -rf the listed mod folders from kai-server's EcoServer Mods/UserCode/.
    Note: the next `inv mods-sync` will re-deposit anything still in the
    eco-mods or eco-mods-public source repos."""
    from eco_cycle_prep import mods

    arr = [n.strip() for n in names.split(",") if n.strip()]
    if not arr:
        raise ValueError("--names is required; pass e.g. --names=DFBargeIndustries")
    mods.disable_on_server(ctx, arr)


@task(
    help={
        "cycle": "Current Eco cycle number",
        "count": "How many rolls to generate (default 1)",
        "seed": "Specific seed to use. If set, overrides random and forces count=1.",
    }
)
def roll(ctx, cycle, count=1, seed=None):
    from eco_cycle_prep import roll as roll_module

    roll_module.run(
        ctx,
        cycle=int(cycle),
        count=int(count),
        seed=int(seed) if seed is not None else None,
    )
