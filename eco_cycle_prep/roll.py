"""The per-roll pipeline: seed → push → remote reset → wait for preview → post.

Posting is factored into its own step (`_post_preview` / `post_existing`) so a
failed Discord/SSM hop can be retried against the already-generated preview
without re-rolling the world. `inv roll` still does both end-to-end;
`inv post-roll` is the replay entry point.
"""

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from invoke.context import Context

from . import discord_rest, local, preview, remote, safety, ssm, worldgen

_ROLL_DIR_RE = re.compile(r"^(?P<n>\d+)-seed-(?P<seed>\d+)$")

ROLLS_DIR = Path(__file__).resolve().parent.parent / "rolls"


def _cycle_dir(cycle: int) -> Path:
    return ROLLS_DIR / f"cycle-{cycle}"


def _next_roll_number(cycle_dir: Path) -> int:
    if not cycle_dir.exists():
        return 1
    existing = [p.name for p in cycle_dir.iterdir() if p.is_dir()]
    nums = []
    for name in existing:
        parts = name.split("-", 1)
        if parts and parts[0].isdigit():
            nums.append(int(parts[0]))
    return (max(nums) if nums else 0) + 1


def _git(cwd: Path, *args: str, capture: bool = False, echo: bool = True) -> str:
    r = local.git(cwd, *args, capture=capture, echo=echo)
    return (r.stdout or "").strip() if capture else ""


def _load_prior_hash(cycle_dir: Path) -> str | None:
    if not cycle_dir.exists():
        return None
    # Walk rolls in reverse order; the most recent metadata carries the last hash.
    for d in sorted(cycle_dir.iterdir(), reverse=True):
        meta = d / "metadata.json"
        if meta.exists():
            try:
                return json.loads(meta.read_text()).get("preview_sha256")
            except Exception:  # noqa: BLE001
                continue
    return None


def _one_roll(ctx: Context, cycle: int, seed: int) -> Path:
    cycle_dir = _cycle_dir(cycle)
    roll_n = _next_roll_number(cycle_dir)
    out_dir = cycle_dir / f"{roll_n:03d}-seed-{seed}"
    out_dir.mkdir(parents=True, exist_ok=True)

    started_at = datetime.now(timezone.utc).isoformat()
    print(f"\n=== cycle {cycle} roll {roll_n}  seed={seed} ===")

    safety.assert_network_locked_down()

    worldgen.set_seed(seed)
    worldgen.snapshot(out_dir / "WorldGenerator.eco")

    eco_configs = worldgen.ECO_CONFIGS
    _git(eco_configs, "add", "Configs/WorldGenerator.eco")
    if _git(eco_configs, "status", "--porcelain", "Configs/WorldGenerator.eco",
            capture=True, echo=False):
        _git(eco_configs, "commit", "-m", f"cycle-{cycle} roll {roll_n}: seed {seed}")
        _git(eco_configs, "push")
    else:
        print("(seed unchanged; skipping commit)")

    remote.infra_pull(ctx)
    remote.copy_configs(ctx)
    remote.reset_world_storage(ctx)

    prior_hash = _load_prior_hash(cycle_dir)

    # Start streaming eco-server logs *before* we bounce the server so the
    # full shutdown → steamcmd pre → boot → world-gen → preview sequence is
    # visible inline.
    #
    # We SIGTERM the running process instead of calling `inv eco.restart`
    # because that task shells out to `sudo systemctl restart eco-server`,
    # and non-interactive ssh can't answer a sudo password prompt. systemd's
    # Restart=on-failure policy picks the service back up automatically
    # after the process dies. Our `pkill` runs as user `kai` and targets
    # kai's own processes, so it needs no elevation.
    with remote.stream_server_logs():
        remote.sigterm_server(ctx)
        print("waiting for preview (streaming eco-server logs until stable)...")
        gif, gif_hash = preview.wait_for_preview(prior_hash=prior_hash)
    gif_path = preview.save(gif, out_dir / "WorldPreview.gif")
    print(f"preview captured: {gif_path} ({len(gif)} bytes, sha256={gif_hash[:12]})")

    _post_preview(
        cycle=cycle,
        roll_n=roll_n,
        seed=seed,
        gif_path=gif_path,
        gif_hash=gif_hash,
        started_at=started_at,
    )
    return out_dir


def _post_preview(
    *,
    cycle: int,
    roll_n: int,
    seed: int,
    gif_path: Path,
    gif_hash: str | None = None,
    started_at: str | None = None,
) -> dict:
    """Post the preview GIF to the cycle-current Discord channel and write
    (or overwrite) metadata.json in the roll dir. Split out of `_one_roll`
    so a failed SSM/Discord hop is replayable without re-rolling."""
    if gif_hash is None:
        gif_hash = hashlib.sha256(gif_path.read_bytes()).hexdigest()

    cycle_channel = ssm.get("/discord/channel/cycle-current")
    content = (
        f"**cycle {cycle} · roll {roll_n}**\n"
        f"seed: `{seed}`\n"
        f"preview sha256: `{gif_hash[:16]}`"
    )
    msg = discord_rest.post_message(cycle_channel, content, file_path=str(gif_path))
    print(f"posted to discord: message id {msg.get('id')}")

    meta = {
        "cycle": cycle,
        "roll": roll_n,
        "seed": seed,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "preview_sha256": gif_hash,
        "discord_message_id": msg.get("id"),
    }
    if started_at is not None:
        meta["started_at"] = started_at
    (gif_path.parent / "metadata.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )
    return meta


def _find_roll_dir(cycle_dir: Path, roll: int | None) -> Path:
    """Resolve the roll dir to post. If `roll` is None, pick the highest-
    numbered dir under the cycle. Errors if nothing matches."""
    if not cycle_dir.exists():
        raise FileNotFoundError(f"no rolls directory for cycle: {cycle_dir}")
    candidates: list[tuple[int, Path]] = []
    for d in cycle_dir.iterdir():
        if not d.is_dir():
            continue
        m = _ROLL_DIR_RE.match(d.name)
        if m:
            candidates.append((int(m.group("n")), d))
    if not candidates:
        raise FileNotFoundError(f"no roll subdirs under {cycle_dir}")
    if roll is None:
        return max(candidates, key=lambda t: t[0])[1]
    for n, d in candidates:
        if n == roll:
            return d
    raise FileNotFoundError(
        f"no roll {roll} under {cycle_dir} (have: {sorted(n for n, _ in candidates)})"
    )


def run(ctx: Context, *, cycle: int, seed: int | None = None) -> None:
    s = seed if seed is not None else worldgen.random_seed()
    _one_roll(ctx, cycle, s)


def post_existing(*, cycle: int, roll: int | None = None) -> None:
    """Replay just the Discord post for an already-captured preview.
    Picks the most recent roll in the cycle unless `roll` is specified."""
    roll_dir = _find_roll_dir(_cycle_dir(cycle), roll)
    m = _ROLL_DIR_RE.match(roll_dir.name)
    assert m is not None  # _find_roll_dir only returns matching dirs
    roll_n = int(m.group("n"))
    seed = int(m.group("seed"))
    gif_path = roll_dir / "WorldPreview.gif"
    if not gif_path.exists():
        raise FileNotFoundError(f"no WorldPreview.gif in {roll_dir} — nothing to post")
    print(f"=== posting cycle {cycle} roll {roll_n}  seed={seed} (from {roll_dir}) ===")
    _post_preview(cycle=cycle, roll_n=roll_n, seed=seed, gif_path=gif_path)
