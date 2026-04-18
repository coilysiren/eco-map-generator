"""Read/write WorldGenerator.eco in the local eco-configs repo."""

import json
import random
import shutil
from pathlib import Path

ECO_CONFIGS = Path(__file__).resolve().parent.parent.parent / "eco-configs"
WORLDGEN_PATH = ECO_CONFIGS / "Configs" / "WorldGenerator.eco"
SEED_MAX = 2_000_000_000  # Eco Seed is an int; keep well under int32 max


def random_seed() -> int:
    return random.randint(1, SEED_MAX)


def set_seed(seed: int) -> None:
    data = json.loads(WORLDGEN_PATH.read_text(encoding="utf-8"))
    data["HeightmapModule"]["Source"]["Config"]["Seed"] = int(seed)
    WORLDGEN_PATH.write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def get_seed() -> int:
    data = json.loads(WORLDGEN_PATH.read_text(encoding="utf-8"))
    return int(data["HeightmapModule"]["Source"]["Config"]["Seed"])


def snapshot(target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(WORLDGEN_PATH, target)
