"""Fetch the world-preview GIF from the running Eco web server."""

import hashlib
import time
from pathlib import Path

import httpx

PREVIEW_URL = "http://eco.coilysiren.me:3001/Layers/WorldPreview.gif"


def _fetch(discriminator: int | None = None) -> httpx.Response:
    # `discriminator` is a cache-buster on Eco's web server; sending a fresh
    # value each call keeps us from seeing stale CDN/proxy responses.
    params = {"discriminator": discriminator if discriminator is not None else int(time.time())}
    return httpx.get(PREVIEW_URL, params=params, timeout=httpx.Timeout(20.0, connect=10.0))


def wait_for_preview(
    *,
    prior_hash: str | None = None,
    total_timeout_s: int = 600,
    poll_interval_s: int = 5,
    stable_polls: int = 2,
) -> tuple[bytes, str]:
    """Poll the preview URL until we see a non-stale, stable GIF.

    Returns (gif_bytes, sha256_hex).

    - Ignores bytes whose hash matches `prior_hash` (stale cache from previous roll).
    - Waits until the same hash repeats `stable_polls` times in a row (i.e. render
      settled).
    """
    deadline = time.monotonic() + total_timeout_s
    last_hash: str | None = None
    streak = 0
    last_bytes: bytes | None = None

    while time.monotonic() < deadline:
        try:
            r = _fetch()
        except httpx.HTTPError:
            time.sleep(poll_interval_s)
            continue

        if r.status_code != 200 or not r.content:
            time.sleep(poll_interval_s)
            continue

        h = hashlib.sha256(r.content).hexdigest()

        if prior_hash and h == prior_hash:
            # Stale preview left over from the previous world.
            time.sleep(poll_interval_s)
            continue

        if h == last_hash:
            streak += 1
            if streak >= stable_polls:
                return r.content, h
        else:
            streak = 1
            last_hash = h
            last_bytes = r.content

        time.sleep(poll_interval_s)

    if last_bytes and last_hash:
        # Took too long to stabilize; return what we've got so the user can decide.
        return last_bytes, last_hash
    raise TimeoutError(f"Preview never became available within {total_timeout_s}s")


def save(data: bytes, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path
