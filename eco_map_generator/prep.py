"""Weekly prep phase: sync source + aggregate community requests for review."""

from datetime import datetime, timezone
from pathlib import Path

from invoke.context import Context

from . import discord_rest, local, remote, ssm, worldgen

PREP_DIR = Path(__file__).resolve().parent.parent / "rolls" / "_prep"


def _fmt_msg(m: dict) -> str:
    author = m.get("author", {}).get("global_name") or m.get("author", {}).get("username") or "?"
    ts = m.get("timestamp", "")[:19]
    content = (m.get("content") or "").strip()
    if not content and m.get("attachments"):
        content = f"[{len(m['attachments'])} attachment(s)]"
    return f"[{ts}] {author}: {content}"


def _dump_channel(name: str, channel_id: str, limit: int = 100) -> list[str]:
    msgs = discord_rest.get_messages(channel_id, limit=limit)
    lines = [f"## {name}  ({channel_id})  — {len(msgs)} messages\n"]
    # Discord returns newest first; reverse to read oldest → newest in the dump.
    for m in reversed(msgs):
        lines.append(_fmt_msg(m))
    lines.append("")
    return lines


def _dump_forum(name: str, guild_id: str, forum_id: str, per_thread: int = 30) -> list[str]:
    threads = discord_rest.get_active_forum_threads(guild_id, forum_id)
    lines = [f"## {name}  ({forum_id})  — {len(threads)} active threads\n"]
    for t in threads:
        tname = t.get("name", "(unnamed)")
        tid = t.get("id")
        lines.append(f"### {tname}  ({tid})")
        try:
            tmsgs = discord_rest.get_messages(tid, limit=per_thread)
            for m in reversed(tmsgs):
                lines.append(_fmt_msg(m))
        except Exception as e:  # noqa: BLE001
            lines.append(f"  [error reading thread: {e}]")
        lines.append("")
    return lines


def run(ctx: Context, *, cycle: int) -> None:
    print(f"\n=== prep for cycle {cycle} ===\n")

    # Step 1: confirm cycle-current channel ID is still right.
    cycle_channel = ssm.get("/discord/channel/cycle-current")
    print(f"/discord/channel/cycle-current → {cycle_channel}")
    print(
        "If this channel is NOT cycle "
        f"{cycle}'s channel, STOP and update SSM:\n"
        "  aws ssm put-parameter --name /discord/channel/cycle-current "
        "--type SecureString --value '<new id>' --overwrite\n"
    )

    # Step 2: sync sources.
    print("-- updating Eco server binaries via steamcmd (ssh kai-server)")
    remote.steamcmd_update(ctx)

    print("-- pulling eco-configs locally")
    local.git(worldgen.ECO_CONFIGS, "pull", "--ff-only")

    print("-- pulling infrastructure on kai-server")
    remote.infra_pull(ctx)

    # Step 3: aggregate community requests.
    print("-- fetching discord history")
    guild_id = ssm.get("/discord/server-id")
    sugg_channel = ssm.get("/discord/channel/suggestions")
    sugg_forum = ssm.get("/discord/channel/suggestions-forum")

    out: list[str] = []
    out.append(f"# Prep digest for cycle {cycle}\n")
    out.append(f"Generated {datetime.now(timezone.utc).isoformat()}\n")
    out.extend(_dump_channel("suggestions (text channel)", sugg_channel))
    out.extend(_dump_forum("suggestions-forum", guild_id, sugg_forum))
    out.extend(_dump_channel(f"cycle-current (= cycle {cycle}?)", cycle_channel))

    PREP_DIR.mkdir(parents=True, exist_ok=True)
    digest_path = (
        PREP_DIR / f"cycle-{cycle}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.md"
    )
    digest_path.write_text("\n".join(out), encoding="utf-8")

    print(f"\ndigest written to {digest_path}")
    print(
        "review the digest, then manually edit\n"
        f"  {worldgen.WORLDGEN_PATH}\n"
        "— specifically the HeightmapModule section — to reflect any reasonable requests.\n"
        f"when ready, run:  inv roll --cycle {cycle} --count N"
    )
