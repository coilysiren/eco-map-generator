"""Weekly prep phase: sync source + aggregate community requests for review."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

from invoke.context import Context

from . import discord_rest, local, remote, ssm, worldgen

PREP_DIR = Path(__file__).resolve().parent.parent / "rolls" / "_prep"

DISCORD_EPOCH_MS = 1420070400000


def _fmt_msg(m: dict) -> str:
    author = m.get("author", {}).get("global_name") or m.get("author", {}).get("username") or "?"
    ts = m.get("timestamp", "")[:19]
    content = (m.get("content") or "").strip()
    if not content and m.get("attachments"):
        content = f"[{len(m['attachments'])} attachment(s)]"
    return f"[{ts}] {author}: {content}"


def _snowflake_for_datetime(dt: datetime) -> str:
    """Discord snowflake whose embedded timestamp equals `dt` (UTC)."""
    ms = int(dt.timestamp() * 1000)
    return str((ms - DISCORD_EPOCH_MS) << 22)


def _datetime_for_snowflake(snowflake: str) -> datetime:
    ms = (int(snowflake) >> 22) + DISCORD_EPOCH_MS
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


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


def dump_forum_since(
    name: str, guild_id: str, forum_id: str, since: datetime
) -> list[str]:
    """Return a digest of every thread in `forum_id` whose activity or
    creation falls on or after `since` (UTC). Walks active + archived, pulls
    all messages per thread (paginated)."""
    active = discord_rest.get_active_forum_threads(guild_id, forum_id)
    archived = discord_rest.get_archived_public_forum_threads(forum_id)
    by_id: dict[str, dict] = {t["id"]: t for t in active + archived}

    after_snowflake = _snowflake_for_datetime(since)

    def _thread_latest_ts(t: dict) -> datetime:
        # Best signal: last_message_id; fallback to thread creation.
        lmid = t.get("last_message_id")
        if lmid:
            return _datetime_for_snowflake(lmid)
        return _datetime_for_snowflake(t["id"])

    recent = sorted(
        (t for t in by_id.values() if _thread_latest_ts(t) >= since),
        key=_thread_latest_ts,
        reverse=True,
    )

    lines = [
        f"## {name}  ({forum_id})  — {len(recent)} threads with activity since "
        f"{since.isoformat()} (of {len(by_id)} total: "
        f"{len(active)} active + {len(archived)} archived)\n"
    ]
    for t in recent:
        tname = t.get("name", "(unnamed)")
        tid = t["id"]
        created = _datetime_for_snowflake(tid).isoformat()
        archived_flag = t.get("thread_metadata", {}).get("archived", False)
        lines.append(f"### {tname}  ({tid})")
        lines.append(
            f"created: {created}  · "
            f"{'archived' if archived_flag else 'active'}  · "
            f"latest: {_thread_latest_ts(t).isoformat()}"
        )
        try:
            msgs = discord_rest.get_all_messages(tid, after_snowflake=after_snowflake)
            if not msgs:
                # Thread was created in-window but has no messages newer than
                # `since`; fall back to fetching the first page unconditionally
                # so the thread's opening post still shows up.
                msgs = discord_rest.get_all_messages(tid)
            for m in msgs:
                lines.append(_fmt_msg(m))
        except Exception as e:  # noqa: BLE001
            lines.append(f"  [error reading thread: {e}]")
        lines.append("")
    return lines


def dump_channel_full(name: str, channel_id: str) -> list[str]:
    msgs = discord_rest.get_all_messages(channel_id)
    lines = [f"## {name}  ({channel_id})  — {len(msgs)} messages (full history)\n"]
    for m in msgs:
        lines.append(_fmt_msg(m))
    lines.append("")
    return lines


def dump_channel_since(name: str, channel_id: str, since: datetime) -> list[str]:
    after = _snowflake_for_datetime(since)
    msgs = discord_rest.get_all_messages(channel_id, after_snowflake=after)
    lines = [
        f"## {name}  ({channel_id})  — {len(msgs)} messages since "
        f"{since.isoformat()}\n"
    ]
    for m in msgs:
        lines.append(_fmt_msg(m))
    lines.append("")
    return lines


def run_brief(_: Context, *, cycle: int, days: int = 60) -> Path:
    """Collect full cycle-N channel history + last `days` of suggestions +
    last `days` of suggestions-forum into one Markdown brief."""
    guild_id = ssm.get("/discord/server-id")
    cycle_channel = ssm.get("/discord/channel/cycle-current")
    sugg_channel = ssm.get("/discord/channel/suggestions")
    sugg_forum = ssm.get("/discord/channel/suggestions-forum")
    since = datetime.now(timezone.utc) - timedelta(days=days)

    print(f"-- cycle {cycle} channel: full history")
    print(f"-- suggestions + forum: since {since.isoformat()}")

    lines: list[str] = [
        f"# pre-cycle {cycle} brief\n",
        f"Generated {datetime.now(timezone.utc).isoformat()}\n",
        f"Cycle-{cycle} channel: full history. "
        f"Suggestions + suggestions-forum: last {days} days.\n",
    ]
    lines.extend(dump_channel_full(f"cycle-{cycle} channel", cycle_channel))
    lines.extend(dump_channel_since("suggestions", sugg_channel, since))
    lines.extend(
        dump_forum_since("suggestions-forum", guild_id, sugg_forum, since)
    )

    PREP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = PREP_DIR / f"brief-cycle-{cycle}-{days}d-{stamp}.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"brief written to {out}")
    return out


def run_forum_dump(_: Context, *, since_days: int = 60) -> Path:
    """Standalone: dump suggestions-forum for the last `since_days` days."""
    guild_id = ssm.get("/discord/server-id")
    forum_id = ssm.get("/discord/channel/suggestions-forum")
    since = datetime.now(timezone.utc) - timedelta(days=since_days)

    print(
        f"-- dumping suggestions-forum since {since.isoformat()} "
        f"({since_days}d ago)"
    )
    lines = [
        f"# suggestions-forum dump — last {since_days} days\n",
        f"Generated {datetime.now(timezone.utc).isoformat()}\n",
        f"Cutoff: {since.isoformat()}\n",
    ]
    lines.extend(dump_forum_since("suggestions-forum", guild_id, forum_id, since))

    PREP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = PREP_DIR / f"suggestions-forum-{since_days}d-{stamp}.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"digest written to {out}")
    return out


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
