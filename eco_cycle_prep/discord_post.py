"""High-level Discord post helpers for Sirens server communications.

All posts here go through the sirens-echo bot (SSM param
`/sirens-echo/discord-bot-token`). The eco-sirens bot (`/eco/discord-bot-token`,
owned by DiscordLink) is intentionally not used here: it auto-posts
server-status embeds and bridges in-game chat, and mixing the two bots in
one channel blurs what's automated vs. manual.

Channel aliases let callers say `post_content("general-public", ...)` instead
of juggling SSM parameter names. Add new aliases here rather than inlining
parameter paths at call sites.
"""

from __future__ import annotations

from typing import Optional

import httpx

from . import discord_rest, ssm

CHANNEL_ALIASES: dict[str, str] = {
    "general-public": "/discord/channel/general-public",
    "eco-status": "/discord/channel/server-status-feed",
}

# Color used by DiscordLink for the Server Started / Server Stopped embeds.
# Matching it keeps manual restart notices visually consistent with the feed.
STATUS_EMBED_COLOR = 7506394


def resolve_channel(alias: str) -> str:
    """Resolve a friendly channel alias to a Discord channel ID via SSM."""
    if alias not in CHANNEL_ALIASES:
        known = ", ".join(sorted(CHANNEL_ALIASES))
        raise ValueError(f"unknown channel alias {alias!r}. known: {known}")
    return ssm.get(CHANNEL_ALIASES[alias])


def post_content(channel: str, body: str) -> dict:
    """Post a plain-content message to a named channel."""
    return discord_rest.post_message(resolve_channel(channel), body)


def post_embed(
    channel: str,
    title: str,
    description: Optional[str] = None,
    color: int = STATUS_EMBED_COLOR,
) -> dict:
    """Post a single-embed message with optional description."""
    channel_id = resolve_channel(channel)
    embed: dict = {"title": title, "color": color}
    if description:
        embed["description"] = description
    r = httpx.post(
        f"{discord_rest.API_BASE}/channels/{channel_id}/messages",
        headers=discord_rest._headers(),
        json={"embeds": [embed]},
        timeout=discord_rest.TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


def restart_notice(reason: Optional[str] = None) -> dict:
    """Post the pre-restart heads-up embed to #eco-status.

    Mirrors DiscordLink's Server Started / Server Stopped format: title-only
    (or title + one-line description), matching color, two-space emoji
    spacing. Call this immediately before restarting kai-server.
    """
    return post_embed(
        "eco-status",
        title="Server Restarting  :arrows_counterclockwise:",
        description=reason,
    )
