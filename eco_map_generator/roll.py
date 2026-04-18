"""The per-roll pipeline: seed → push → remote reset → wait for preview → post."""

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from invoke.context import Context

from . import discord_rest, preview, remote, ssm, worldgen

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


def _git(ctx: Context, cwd: Path, cmd: str, *, echo: bool = True) -> str:
    r = ctx.run(f"git -C {cwd} {cmd}", echo=echo, hide="stdout" if not echo else False)
    return r.stdout.strip() if r else ""


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

    worldgen.set_seed(seed)
    worldgen.snapshot(out_dir / "WorldGenerator.eco")

    eco_configs = worldgen.ECO_CONFIGS
    _git(ctx, eco_configs, "add Configs/WorldGenerator.eco")
    if _git(ctx, eco_configs, "status --porcelain Configs/WorldGenerator.eco", echo=False):
        _git(ctx, eco_configs, f'commit -m "cycle-{cycle} roll {roll_n}: seed {seed}"')
        _git(ctx, eco_configs, "push")
    else:
        print("(seed unchanged; skipping commit)")

    remote.infra_pull(ctx)
    remote.copy_configs(ctx)
    remote.reset_world_storage(ctx)

    prior_hash = _load_prior_hash(cycle_dir)

    # Start streaming eco-server logs *before* the restart so the full
    # shutdown → steamcmd pre → boot → world-gen → preview sequence is visible.
    with remote.stream_server_logs():
        if not remote.server_is_activating(ctx):
            remote.restart_server(ctx)
        else:
            print("server already restarting; skipping inv eco.restart")

        print("waiting for preview (streaming eco-server logs until stable)...")
        gif, gif_hash = preview.wait_for_preview(prior_hash=prior_hash)
    gif_path = preview.save(gif, out_dir / "WorldPreview.gif")
    print(f"preview captured: {gif_path} ({len(gif)} bytes, sha256={gif_hash[:12]})")

    cycle_channel = ssm.get("/discord/channel/cycle-current")
    content = (
        f"**cycle {cycle} · roll {roll_n}**\n"
        f"seed: `{seed}`\n"
        f"preview sha256: `{gif_hash[:16]}`"
    )
    msg = discord_rest.post_message(cycle_channel, content, file_path=str(gif_path))
    print(f"posted to discord: message id {msg.get('id')}")

    (out_dir / "metadata.json").write_text(
        json.dumps(
            {
                "cycle": cycle,
                "roll": roll_n,
                "seed": seed,
                "started_at": started_at,
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "preview_sha256": gif_hash,
                "discord_message_id": msg.get("id"),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return out_dir


def run(ctx: Context, *, cycle: int, count: int = 1, seed: int | None = None) -> None:
    if seed is not None and count > 1:
        raise ValueError("--seed and --count > 1 are mutually exclusive")

    for i in range(count):
        s = seed if seed is not None else worldgen.random_seed()
        _one_roll(ctx, cycle, s)
        if i < count - 1:
            # brief spacing so we don't race Discord rate limits
            time.sleep(2)
