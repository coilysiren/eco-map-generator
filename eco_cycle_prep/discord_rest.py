from functools import lru_cache

import httpx

from . import ssm

API_BASE = "https://discord.com/api/v10"
TIMEOUT = httpx.Timeout(15.0, connect=10.0)


@lru_cache(maxsize=1)
def _headers() -> dict[str, str]:
    token = ssm.get("/eco/discord-bot-token")
    return {"Authorization": f"Bot {token}"}


def get_messages(channel_id: str, limit: int = 100) -> list[dict]:
    """Most recent messages in a text channel, newest first."""
    r = httpx.get(
        f"{API_BASE}/channels/{channel_id}/messages",
        headers=_headers(),
        params={"limit": limit},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


def get_active_forum_threads(guild_id: str, forum_channel_id: str) -> list[dict]:
    """Active threads (posts) under a forum channel."""
    r = httpx.get(
        f"{API_BASE}/guilds/{guild_id}/threads/active",
        headers=_headers(),
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return [t for t in r.json().get("threads", []) if t.get("parent_id") == forum_channel_id]


def get_archived_public_forum_threads(
    forum_channel_id: str, before_iso: str | None = None, page_limit: int = 100
) -> list[dict]:
    """Paginate through archived public threads in a forum. Newest first.
    Yields all pages; callers filter by creation date if they want a cutoff."""
    out: list[dict] = []
    before = before_iso
    while True:
        params: dict[str, str | int] = {"limit": page_limit}
        if before:
            params["before"] = before
        r = httpx.get(
            f"{API_BASE}/channels/{forum_channel_id}/threads/archived/public",
            headers=_headers(),
            params=params,
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        page = r.json()
        threads = page.get("threads", [])
        if not threads:
            break
        out.extend(threads)
        if not page.get("has_more"):
            break
        # `before` is an ISO-8601 archive timestamp per Discord docs.
        before = threads[-1].get("thread_metadata", {}).get("archive_timestamp")
        if not before:
            break
    return out


def get_all_messages(channel_id: str, after_snowflake: str | None = None) -> list[dict]:
    """Paginate through all messages in a channel. Returned in chronological
    (oldest-first) order. If `after_snowflake` is set, only messages newer
    than that snowflake are returned."""
    out: list[dict] = []
    before: str | None = None
    while True:
        params: dict[str, str | int] = {"limit": 100}
        if before:
            params["before"] = before
        r = httpx.get(
            f"{API_BASE}/channels/{channel_id}/messages",
            headers=_headers(),
            params=params,
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        # Discord returns newest-first; walk backwards until we hit the cutoff.
        stop = False
        for m in batch:
            if after_snowflake and int(m["id"]) <= int(after_snowflake):
                stop = True
                break
            out.append(m)
        if stop or len(batch) < 100:
            break
        before = batch[-1]["id"]
    out.reverse()  # oldest first
    return out


def post_message(channel_id: str, content: str, file_path: str | None = None) -> dict:
    url = f"{API_BASE}/channels/{channel_id}/messages"
    if file_path:
        from pathlib import Path

        p = Path(file_path)
        with p.open("rb") as f:
            data = f.read()
        files = {"files[0]": (p.name, data, "image/gif")}
        r = httpx.post(
            url, headers=_headers(), data={"content": content}, files=files, timeout=TIMEOUT
        )
    else:
        r = httpx.post(url, headers=_headers(), json={"content": content}, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()
