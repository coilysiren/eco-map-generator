"""Fetch the world-preview GIF from the running Eco web server."""

import hashlib
import time
from dataclasses import dataclass
from pathlib import Path

import httpx
from tenacity import (
    Retrying,
    retry_if_exception_type,
    stop_after_delay,
    wait_fixed,
)

PREVIEW_URL = "http://eco.coilysiren.me:3001/Layers/WorldPreview.gif"


class _PreviewNotReady(Exception):
    """Retryable: fetched bytes are missing, stale, or not yet stable."""


@dataclass
class _PollState:
    last_hash: str = ""
    last_bytes: bytes = b""
    streak: int = 0


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
    - On timeout, returns the last seen bytes if any; otherwise raises TimeoutError.
    """
    state = _PollState()

    def _attempt() -> tuple[bytes, str]:
        try:
            r = _fetch()
        except httpx.HTTPError as e:
            raise _PreviewNotReady(f"fetch failed: {e}") from e

        if r.status_code != 200 or not r.content:
            raise _PreviewNotReady(f"bad response: {r.status_code}, {len(r.content)} bytes")

        h = hashlib.sha256(r.content).hexdigest()
        if prior_hash and h == prior_hash:
            raise _PreviewNotReady("stale (matches prior_hash)")

        if h == state.last_hash:
            state.streak += 1
        else:
            state.last_hash = h
            state.last_bytes = r.content
            state.streak = 1

        if state.streak >= stable_polls:
            return r.content, h
        raise _PreviewNotReady(f"hash {h[:8]} only seen {state.streak} time(s)")

    try:
        for attempt in Retrying(
            retry=retry_if_exception_type(_PreviewNotReady),
            stop=stop_after_delay(total_timeout_s),
            wait=wait_fixed(poll_interval_s),
            reraise=True,
        ):
            with attempt:
                return _attempt()
    except _PreviewNotReady:
        if state.last_bytes and state.last_hash:
            return state.last_bytes, state.last_hash
        raise TimeoutError(f"Preview never became available within {total_timeout_s}s") from None

    raise TimeoutError(f"Preview never became available within {total_timeout_s}s")


def save(data: bytes, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path
