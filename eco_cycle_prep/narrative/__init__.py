"""Map-preview narrative: parse a WorldPreview.gif + WorldGenerator.eco
and print a short three-paragraph description of the generated world.

Public surface:

    from eco_cycle_prep.narrative import run, narrate, extract_features, Features

- `run(...)` is the CLI entry point wired to `inv narrate`.
- `narrate(features)` turns a Features record into text.
- `extract_features(gif, config)` does the pixel + config reading.
- `Features` is the dataclass that bridges the two halves.

Submodules:

- `blocks`    — RGB → block catalog and classifier
- `features`  — Features dataclass + extraction pipeline
- `text`      — paragraph builders and `narrate()`
"""

import json
import time
from pathlib import Path

import httpx

from .. import preview, worldgen
from .features import Features, extract_features
from .text import narrate

PREVIEW_URL = preview.PREVIEW_URL

__all__ = ["run", "narrate", "extract_features", "Features", "PREVIEW_URL"]


def _fetch_live_gif() -> bytes:
    r = httpx.get(PREVIEW_URL, params={"discriminator": int(time.time())},
                  timeout=httpx.Timeout(20.0, connect=10.0))
    r.raise_for_status()
    return r.content


def run(
    *,
    gif_path: Path | None = None,
    config_path: Path | None = None,
    show_features: bool = False,
) -> None:
    cfg_path = config_path or worldgen.WORLDGEN_PATH
    cfg = json.loads(Path(cfg_path).read_text(encoding="utf-8"))

    if gif_path is not None:
        gif_data: bytes | Path = Path(gif_path)
        source = str(gif_path)
    else:
        gif_data = _fetch_live_gif()
        source = PREVIEW_URL

    features = extract_features(gif_data, cfg)

    if show_features:
        print("=== features ===")
        print(f"source:                 {source}")
        print(f"size:                   {features.width}x{features.height}")
        print(f"palette entries used:   {features.palette_entries_used}")
        print(f"water / land:           "
              f"{features.water_fraction:.1%} / {features.land_fraction:.1%}")
        print(f"continents / islands:   "
              f"{features.continent_count} / {features.island_count}")
        print(f"lakes:                  {features.lake_count}")
        print(f"ice cap N / S:          "
              f"{features.ice_cap_north} / {features.ice_cap_south}")
        print(f"seed:                   {features.seed}")
        print(f"crater enabled:         {features.crater_enabled}")
        print(f"coastline pixels:       {features.coastline_pixels}")
        print(f"largest landmass ctr:   "
              f"({features.largest_landmass_centroid[0]:+.2f}, "
              f"{features.largest_landmass_centroid[1]:+.2f}) "
              f"[-1..1, +x east, +y south]")
        print("biome pixel breakdown (land fraction, centroid, spread):")
        for kind in sorted(features.kind_pixels, key=lambda k: -features.kind_pixels[k]):
            frac = features.land_kind_fraction(kind)
            if frac > 0 or kind == "water":
                label = "water" if kind == "water" else kind
                cx, cy = features.kind_centroids.get(kind, (0.0, 0.0))
                sp = features.kind_spreads.get(kind, 0.0)
                print(f"  {label:15s} {features.kind_pixels[kind]:>10d}  "
                      f"{frac * 100:5.1f}% of land  "
                      f"ctr=({cx:+.2f},{cy:+.2f}) spread={sp:.2f}")
        print()
        print("=== narrative ===")
    print(narrate(features))
