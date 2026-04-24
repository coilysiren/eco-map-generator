"""Entry points for the Eco cycle-prep workflow.

These pyinvoke tasks are the implementation layer. The canonical operator
entry point is `coily <verb>` (see .coily/coily.yaml); everything below is
reachable both ways but docs, commit messages, and drafted patch notes
reference the coily form.

Weekly prep:         coily prep --cycle=<N>
Discord intel:       coily brief --cycle=<N> [--days=<D>]  |  coily forum-dump [--days=<D>]
Map rolls (repeat):  coily roll --cycle=<N> [--seed=<S>]   # one seed per invocation
Re-post a roll:      coily post-roll --cycle=<N> [--roll=<R>]  # replay discord post only
Narrate a map:       coily narrate [--gif=PATH] [--config=PATH] [--features]
Mod management:      coily mods-sync  |  coily mods-disable --names=A,B,C
Announcements:       coily ad --cycle=<N> --start-ts=<unix>  |  coily sirens-post --cycle=<N> --start-ts=<unix>
Go live:             coily go-live   # runtime flip on kai-server; git Network.eco stays private
Go private:          coily go-private  # inverse: re-privatize the server mid-cycle
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


@task(
    help={
        "cycle": "Cycle number the roll lives under",
        "roll": "Specific roll number to re-post. Defaults to the highest "
        "roll number in the cycle dir.",
    }
)
def post_roll(ctx, cycle, roll=None):
    """Replay just the Discord post for an already-captured roll preview.

    Useful when `inv roll` generated the world + saved WorldPreview.gif but
    the Discord/SSM hop failed (stale SSO token, 5xx, etc.). Does not
    re-roll the world — only posts the existing gif and writes metadata.json.
    """
    from eco_cycle_prep import roll as roll_module

    roll_module.post_existing(
        cycle=int(cycle),
        roll=int(roll) if roll is not None else None,
    )


@task(
    help={
        "gif": "Path to a local WorldPreview.gif. Default: fetch the live "
        "server at eco.coilysiren.me:3001.",
        "config": "Path to a WorldGenerator.eco config. Default: the "
        "checked-in copy at eco-configs/Configs/WorldGenerator.eco.",
        "features": "Also print the raw feature breakdown before the narrative. "
        "Useful while tuning thresholds and wording.",
    }
)
def narrate(ctx, gif=None, config=None, features=False):
    """Describe a generated map in prose.

    Reads the preview GIF + world config, extracts biome/land-shape
    features, and prints a short narrative suitable for pasting into a
    Discord post. Standalone for now — not yet wired into `inv roll`
    while we iterate on wording.
    """
    from pathlib import Path

    from eco_cycle_prep import narrative as narrative_module

    narrative_module.run(
        gif_path=Path(gif) if gif else None,
        config_path=Path(config) if config else None,
        show_features=bool(features),
    )


@task(
    help={
        "channel": "Channel alias: general-public (patch notes) or eco-status (status feed).",
        "body": "Message body inline. Mutually exclusive with --from-file.",
        "from-file": "Read message body from this file path.",
    }
)
def discord_post(ctx, channel, body=None, from_file=None):
    """Post a one-off content message to a named Sirens Discord channel.

    Posts via the sirens-echo bot. Use this for patch notes and other
    manual announcements. Before drafting a patch-note body, consult
    the private `../eco-voice/` repo for voice and tone guidance.
    """
    from eco_cycle_prep import discord_post as dp

    if bool(body) == bool(from_file):
        raise ValueError("pass exactly one of --body=... or --from-file=...")
    content = body if body else open(from_file, encoding="utf-8").read()
    r = dp.post_content(channel, content)
    print(f"posted id={r['id']} channel_id={r['channel_id']} len={len(r.get('content', ''))}")


@task(help={"reason": "Optional one-liner shown as the embed description."})
def restart_notice(ctx, reason=None):
    """Post the pre-restart heads-up embed to #eco-status.

    Run this immediately before any command that restarts the Eco server
    on kai-server. Mirrors DiscordLink's Server Started / Server Stopped
    embed format so it slots in visually with the auto-posted feed.
    """
    from eco_cycle_prep import discord_post as dp

    r = dp.restart_notice(reason=reason)
    print(f"posted id={r['id']} channel_id={r['channel_id']}")


@task(help={"command": "Literal invoke command text (with secrets redacted)."})
def ops_notice(ctx, command):
    """Post the literal text of an ops command to #eco-status before running.

    Primarily intended to be called from other invoke tasks as their first
    step, but exposed here for manual use too. See `eco_cycle_prep.discord_post.ops_notice`
    for the full contract, especially the caller's responsibility to redact
    secrets before passing them in.
    """
    from eco_cycle_prep import discord_post as dp

    r = dp.ops_notice(command)
    print(f"posted id={r['id']} channel_id={r['channel_id']}")


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


@task(help={"restart": "Restart the server after the flip (default on)"})
def go_private(ctx, restart=True):
    """Flip the running Eco server back to private + password-locked on kai-server.

    Inverse of `inv go-live`. Syncs git's (locked) Network.eco onto the
    server, re-asserts PublicServer=false + the locked password on disk,
    then restarts so the flip takes effect.

    Requires git's eco-configs/Configs/Network.eco to already be in the
    locked private state — fails loudly otherwise.
    """
    from eco_cycle_prep import goprivate

    goprivate.run(ctx, restart=restart)


# --- local Eco server (Windows / Mac) -----------------------------------------
# Copied from coilysiren/infrastructure/src/eco.py during the migration to
# make eco-cycle-prep the single source of truth for Eco ops. See issue for
# the kai-server / remote side of the move.


@task(help={"offline": "Launch without fetching /eco/server-api-token from SSM"})
def server_run(ctx, offline=False):  # noqa: ARG001
    """Prep Configs for private-local dev and launch the local EcoServer."""
    from eco_cycle_prep import server_local

    server_local.prep_for_local(offline=offline)
    server_local.launch(offline=offline)


@task(help={"offline": "Launch without fetching /eco/server-api-token from SSM"})
def server_launch(ctx, offline=False):  # noqa: ARG001
    """Launch the local EcoServer as-is, without rewriting any configs."""
    from eco_cycle_prep import server_local

    server_local.launch(offline=offline)


@task
def server_copy_configs(ctx):  # noqa: ARG001
    """Copy Configs/ from the sibling eco-configs repo into the local server."""
    from eco_cycle_prep import server_local

    server_local.copy_configs_from_sibling()


@task
def server_copy_public_mods(ctx):  # noqa: ARG001
    """Copy Mods/ from the sibling eco-mods-public repo into the local server."""
    from eco_cycle_prep import server_local

    server_local.copy_mods_from_sibling(server_local.PUBLIC_MODS_SIBLING)


@task
def server_copy_private_mods(ctx):  # noqa: ARG001
    """Copy Mods/ from the sibling eco-mods repo into the local server."""
    from eco_cycle_prep import server_local

    server_local.copy_mods_from_sibling(server_local.PRIVATE_MODS_SIBLING)


@task(
    help={
        "dll": "Path to the pre-built mod DLL",
        "name": "Mods/<name>/ subdir (defaults to DLL stem)",
    }
)
def server_deploy_mod(ctx, dll, name=None):  # noqa: ARG001
    """Drop a pre-built mod DLL into Server/Mods/<name>/ on the local box."""
    from pathlib import Path

    from eco_cycle_prep import server_local

    server_local.deploy_mod_dll(Path(dll), mod_name=name)


@task(help={"seed": "Heightmap seed (default 0)"})
def server_regen_new(ctx, seed=0):  # noqa: ARG001
    """Wipe Storage + Logs; force a fresh random world at the given seed."""
    from eco_cycle_prep import server_local

    server_local.regen_new_world(seed=int(seed))


@task
def server_regen_same(ctx):  # noqa: ARG001
    """Wipe Storage + Logs; keep the current WorldGenerator.eco seed."""
    from eco_cycle_prep import server_local

    server_local.regen_same_world()
