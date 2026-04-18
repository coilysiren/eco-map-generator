"""Entry points for the Eco cycle-prep workflow.

Weekly prep:         inv prep --cycle <N>
Discord intel:       inv brief --cycle <N> [--days <D>]  |  inv forum-dump [--days <D>]
Map rolls (repeat):  inv roll --cycle <N> [--seed <S>]   # one seed per invocation
Mod management:      inv mods-sync  |  inv mods-disable --names=A,B,C
Announcements:       inv ad --cycle <N> --start-ts <unix>  |  inv eco-configs-post --cycle <N>
Go live:             inv go-live   # runtime flip on kai-server; git Network.eco stays private
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
    }
)
def ad(ctx, cycle, start_ts):
    """Emit the eco-server-ad markdown block for the main Eco Discord /
    Reddit. Under 100 lines, structured. Prints to stdout (paste target)
    and saves a copy under rolls/_prep/."""
    from eco_cycle_prep import announce

    announce.run(cycle=int(cycle), start_ts=int(start_ts))


@task(
    help={
        "cycle": "Cycle number",
        "start-ts": "Unix timestamp of go-live. Get it from "
        "https://r.3v.fi/discord-timestamps/",
    }
)
def sirens_post(ctx, cycle, start_ts):
    """Emit the verbose cycle-kickoff post for Sirens' own #eco-configs
    channel. Budgeted to Discord's 2000-char message cap. Prints to stdout
    and saves under rolls/_prep/."""
    from eco_cycle_prep import announce

    announce.run_sirens_configs(cycle=int(cycle), start_ts=int(start_ts))


@task(
    help={
        "cycle": "Cycle number",
        "sync": "Also write the rendered values into eco-configs/Configs/"
        "Network.eco (Name + DetailedDescription). Default off — render "
        "first, review, then rerun with --sync.",
    }
)
def ingame(ctx, cycle, sync=False):
    """Render the in-game server Name (250-char cap) and DetailedDescription
    (500-char cap) strings that show up in Eco's master-server browser.
    Uses Unity rich-text color tags around 'Eco' and 'Sirens'."""
    from eco_cycle_prep import announce

    announce.run_ingame(cycle=int(cycle))
    if sync:
        announce.sync_ingame_to_network(cycle=int(cycle))


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
        "seed": "Specific seed to use. If omitted, a fresh random seed is picked.",
    }
)
def roll(ctx, cycle, seed=None):
    """Roll one worldgen seed end-to-end: set + push to eco-configs, sync
    to kai-server, wipe storage, restart, wait for preview, post preview
    GIF and seed to the current cycle's Discord channel."""
    from eco_cycle_prep import roll as roll_module

    roll_module.run(
        ctx,
        cycle=int(cycle),
        seed=int(seed) if seed is not None else None,
    )


@task(help={"restart": "Restart the server after the flip (default on)"})
def go_live(ctx, restart=True):
    """Flip the running Eco server to public + no-password on kai-server.

    Edits `Configs/Network.eco` ON THE SERVER directly. The git-tracked
    Network.eco always stays in its private, password-protected state.

    Order: runs `eco.copy-configs --with-world-gen` on kai-server so it
    has the final cycle settings, then flips Network.eco on disk, then
    optionally restarts the server.

    Do NOT run `inv roll` or `inv mods-sync` after this — both invoke
    `eco.copy-configs` under the hood, which would overwrite Network.eco
    with the git (private) version and take the server back off-public.
    """
    from eco_cycle_prep import golive

    golive.run(ctx, restart=restart)
