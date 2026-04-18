"""Read a WorldPreview.gif + WorldGenerator.eco into a Features record.

Pure extraction — no text generation happens here. Callers pass the
Features instance to narrative.text.narrate() (or read the fields
directly for debugging / tuning).
"""

from collections import Counter, deque
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Iterable

from PIL import Image

from .blocks import LAND_KINDS, classify_rgb


@dataclass
class Features:
    # Image
    width: int
    height: int
    palette_entries_used: int
    # Palette index → (r, g, b, kind, block_name, pixel_count)
    palette_map: dict[int, dict] = field(default_factory=dict)
    # Pixel breakdown
    total_pixels: int = 0
    water_pixels: int = 0
    land_pixels: int = 0
    kind_pixels: dict[str, int] = field(default_factory=dict)
    # Shapes
    continent_count: int = 0
    island_count: int = 0
    landmass_sizes: list[int] = field(default_factory=list)  # sorted descending
    largest_landmass_pixels: int = 0
    largest_landmass_centroid: tuple[float, float] = (0.0, 0.0)  # normalized [-1, 1]
    lake_count: int = 0
    open_ocean_pixels: int = 0
    coastline_pixels: int = 0
    ice_cap_north: bool = False
    ice_cap_south: bool = False
    # Per-kind spatial stats in normalized image-space coordinates. Origin
    # at image center, +x right, +y down, range [-1, 1]. Absolute values
    # are not meaningful narratively — the Eco world is a torus and the
    # GIF's seam is arbitrary. Only *pairwise* torus distances between
    # centroids convey stable information (see text._torus_distance).
    # `spread` is the mean pixel distance from centroid in the same
    # normalized space (0 = all in one spot, ~0.5 = map-wide).
    kind_centroids: dict[str, tuple[float, float]] = field(default_factory=dict)
    kind_spreads: dict[str, float] = field(default_factory=dict)
    # Config
    seed: int = 0
    world_w: int = 0
    world_h: int = 0
    map_preset: str = ""
    crater_enabled: bool = False
    biome_weights: dict[str, float] = field(default_factory=dict)
    num_continents_range: tuple[int, int] = (0, 0)
    num_islands_range: tuple[int, int] = (0, 0)
    num_lakes_range: tuple[int, int] = (0, 0)
    num_rivers_range: tuple[int, int] = (0, 0)

    @property
    def land_fraction(self) -> float:
        return self.land_pixels / self.total_pixels if self.total_pixels else 0.0

    @property
    def water_fraction(self) -> float:
        return self.water_pixels / self.total_pixels if self.total_pixels else 0.0

    def land_kind_fraction(self, kind: str) -> float:
        return self.kind_pixels.get(kind, 0) / self.land_pixels if self.land_pixels else 0.0

    @property
    def world_meters(self) -> int:
        """World edge in meters. GIF is 1 pixel per voxel-column, which
        is 1m × 1m in Eco."""
        return self.width


def _load_image(gif: bytes | Path) -> Image.Image:
    if isinstance(gif, (str, Path)):
        im = Image.open(gif)
    else:
        im = Image.open(BytesIO(gif))
    im.seek(0)
    if im.mode != "P":
        im = im.convert("P")
    return im


def _components(mask: list[list[bool]]) -> list[int]:
    """Pixel-counts of 4-connected components where mask[y][x] is True."""
    h = len(mask)
    w = len(mask[0]) if h else 0
    seen = [[False] * w for _ in range(h)]
    sizes: list[int] = []
    for y0 in range(h):
        for x0 in range(w):
            if not mask[y0][x0] or seen[y0][x0]:
                continue
            size = 0
            q: deque[tuple[int, int]] = deque([(x0, y0)])
            seen[y0][x0] = True
            while q:
                x, y = q.popleft()
                size += 1
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < w and 0 <= ny < h and mask[ny][nx] and not seen[ny][nx]:
                        seen[ny][nx] = True
                        q.append((nx, ny))
            sizes.append(size)
    return sizes


def _water_components(water_mask: list[list[bool]]) -> tuple[int, int, int]:
    """Return (open_ocean_pixels, lake_count, ocean_component_count).

    Heuristic: the component(s) touching the image edge are ocean; interior
    components ≥ MIN_LAKE_PIXELS are lakes. Anything smaller is noise
    (river segment artefacts, isolated single-pixel submerged cells)."""
    h = len(water_mask)
    w = len(water_mask[0]) if h else 0
    MIN_LAKE_PIXELS = max(16, (w * h) // 2000)  # ~0.05% of world
    seen = [[False] * w for _ in range(h)]
    open_ocean = 0
    lakes = 0
    oceans = 0
    for y0 in range(h):
        for x0 in range(w):
            if not water_mask[y0][x0] or seen[y0][x0]:
                continue
            size = 0
            touches_edge = False
            q: deque[tuple[int, int]] = deque([(x0, y0)])
            seen[y0][x0] = True
            while q:
                x, y = q.popleft()
                size += 1
                if x == 0 or y == 0 or x == w - 1 or y == h - 1:
                    touches_edge = True
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < w and 0 <= ny < h and water_mask[ny][nx] and not seen[ny][nx]:
                        seen[ny][nx] = True
                        q.append((nx, ny))
            if touches_edge:
                open_ocean += size
                oceans += 1
            elif size >= MIN_LAKE_PIXELS:
                lakes += 1
    return open_ocean, lakes, oceans


def _largest_component_centroid(
    mask: list[list[bool]],
) -> tuple[int, tuple[float, float]]:
    """Return (size_of_largest, centroid_normalized). Centroid is (cx, cy)
    in normalized image-space: origin at the image center, +x right, +y
    down, range [-1, 1]. These aren't compass directions — the Eco world
    is a torus — so callers must only use centroids *relative* to each
    other, not as absolute positions."""
    h = len(mask)
    w = len(mask[0]) if h else 0
    if not w or not h:
        return 0, (0.0, 0.0)
    seen = [[False] * w for _ in range(h)]
    best_size = 0
    best_cx = 0.0
    best_cy = 0.0
    for y0 in range(h):
        for x0 in range(w):
            if not mask[y0][x0] or seen[y0][x0]:
                continue
            size = 0
            sx = 0
            sy = 0
            q: deque[tuple[int, int]] = deque([(x0, y0)])
            seen[y0][x0] = True
            while q:
                x, y = q.popleft()
                size += 1
                sx += x
                sy += y
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < w and 0 <= ny < h and mask[ny][nx] and not seen[ny][nx]:
                        seen[ny][nx] = True
                        q.append((nx, ny))
            if size > best_size:
                best_size = size
                best_cx = (sx / size) / (w / 2) - 1.0
                best_cy = (sy / size) / (h / 2) - 1.0
    return best_size, (best_cx, best_cy)


def _coastline_count(
    water_mask: list[list[bool]], land_mask: list[list[bool]]
) -> int:
    """Count land pixels with at least one 4-neighbor water pixel.

    High counts relative to the square-root of land area indicate a ragged,
    inlet-heavy coastline; low counts indicate smooth continental edges."""
    h = len(water_mask)
    w = len(water_mask[0]) if h else 0
    count = 0
    for y in range(h):
        for x in range(w):
            if not land_mask[y][x]:
                continue
            if (
                (x > 0 and water_mask[y][x - 1]) or
                (x < w - 1 and water_mask[y][x + 1]) or
                (y > 0 and water_mask[y - 1][x]) or
                (y < h - 1 and water_mask[y + 1][x])
            ):
                count += 1
    return count


def _kind_spatial_stats(
    pixel_rows: list[list[int]],
    palette_map: dict[int, dict],
    width: int,
    height: int,
) -> tuple[dict[str, tuple[float, float]], dict[str, float]]:
    """Return per-kind centroids (normalized [-1, 1]) and per-kind
    dispersion (mean pixel distance from centroid in normalized units).

    Single pass over all pixels: accumulate sum_x, sum_y, sum_x2, sum_y2,
    and count per kind, then solve for mean + stddev."""
    sums: dict[str, list[int]] = {}  # kind -> [sum_x, sum_y, sum_x2, sum_y2, n]
    for y, row in enumerate(pixel_rows):
        for x, idx in enumerate(row):
            kind = palette_map.get(idx, {}).get("kind", "other")
            s = sums.get(kind)
            if s is None:
                s = [0, 0, 0, 0, 0]
                sums[kind] = s
            s[0] += x
            s[1] += y
            s[2] += x * x
            s[3] += y * y
            s[4] += 1

    hx, hy = width / 2, height / 2
    centroids: dict[str, tuple[float, float]] = {}
    spreads: dict[str, float] = {}
    for kind, (sx, sy, sx2, sy2, n) in sums.items():
        if n == 0:
            continue
        mx = sx / n
        my = sy / n
        var_x = max(0.0, sx2 / n - mx * mx)
        var_y = max(0.0, sy2 / n - my * my)
        centroids[kind] = (mx / hx - 1.0, my / hy - 1.0)
        spread = ((var_x + var_y) ** 0.5) / max(hx, hy)
        spreads[kind] = spread
    return centroids, spreads


def _ice_caps(
    pixel_rows: list[list[int]],
    palette_map: dict[int, dict],
    height: int,
    width: int,
) -> tuple[bool, bool]:
    """Detect ice/snow bands at the top or bottom edge of the map.

    True if any of the top (or bottom) BAND rows have at least
    MIN_ICE_FRACTION of their width covered by ice/snow pixels."""
    BAND = max(3, height // 20)  # top/bottom 5% band
    MIN_ICE_FRACTION = 0.06
    ice_kinds = {"ice", "snow"}

    def _band_has_ice(y_range: Iterable[int]) -> bool:
        ice = 0
        for y in y_range:
            row = pixel_rows[y]
            for idx in row:
                kind = palette_map.get(idx, {}).get("kind")
                if kind in ice_kinds:
                    ice += 1
        return ice >= MIN_ICE_FRACTION * BAND * width

    return _band_has_ice(range(BAND)), _band_has_ice(range(height - BAND, height))


def extract_features(gif: bytes | Path, config: dict) -> Features:
    im = _load_image(gif)
    w, h = im.size
    palette = im.getpalette() or []
    pixels = list(im.get_flattened_data()) if hasattr(im, "get_flattened_data") else list(im.getdata())
    counts = Counter(pixels)

    palette_map: dict[int, dict] = {}
    kind_pixels: dict[str, int] = {}
    water_pixels = 0
    land_pixels = 0
    for idx, count in counts.items():
        r = palette[idx * 3] if len(palette) > idx * 3 else 0
        g = palette[idx * 3 + 1] if len(palette) > idx * 3 + 1 else 0
        b = palette[idx * 3 + 2] if len(palette) > idx * 3 + 2 else 0
        name, kind = classify_rgb(r, g, b)
        palette_map[idx] = dict(rgb=(r, g, b), name=name, kind=kind, count=count)
        kind_pixels[kind] = kind_pixels.get(kind, 0) + count
        if kind == "water":
            water_pixels += count
        elif kind in LAND_KINDS:
            land_pixels += count

    # Reshape pixels into rows for connected-component work.
    pixel_rows: list[list[int]] = [pixels[y * w : (y + 1) * w] for y in range(h)]
    water_mask = [[palette_map[p]["kind"] == "water" for p in row] for row in pixel_rows]
    land_mask = [[palette_map[p]["kind"] in LAND_KINDS for p in row] for row in pixel_rows]

    land_sizes = sorted(_components(land_mask), reverse=True)
    largest_size, largest_centroid = _largest_component_centroid(land_mask)
    open_ocean, lake_count, _ = _water_components(water_mask)
    coastline_pixels = _coastline_count(water_mask, land_mask)
    kind_centroids, kind_spreads = _kind_spatial_stats(pixel_rows, palette_map, w, h)

    # Continent vs island split: anything ≥ 1% of total pixels is a continent.
    total_pixels = w * h
    continent_threshold = max(400, total_pixels // 100)
    continent_count = sum(1 for s in land_sizes if s >= continent_threshold)
    # Drop tiny "islands" that are almost certainly single stray pixels
    # from quantization or one-pixel peninsulas.
    min_island = max(4, total_pixels // 10_000)
    island_count = sum(1 for s in land_sizes if min_island <= s < continent_threshold)

    ice_cap_n, ice_cap_s = _ice_caps(pixel_rows, palette_map, h, w)

    # Config slice
    inner = config.get("HeightmapModule", {}).get("Source", {}).get("Config", {})
    crater = config.get("Crater", {}) or {}
    dims = config.get("Dimensions", {}) or {}
    weights = {
        "desert": inner.get("DesertWeight", 0.0),
        "warm_forest": inner.get("WarmForestWeight", 0.0),
        "cool_forest": inner.get("CoolForestWeight", 0.0),
        "taiga": inner.get("TaigaWeight", 0.0),
        "tundra": inner.get("TundraWeight", 0.0),
        "ice": inner.get("IceWeight", 0.0),
        "rainforest": inner.get("RainforestWeight", 0.0),
        "wetland": inner.get("WetlandWeight", 0.0),
        "steppe": inner.get("SteppeWeight", 0.0),
        "high_desert": inner.get("HighDesertWeight", 0.0),
    }

    def _range(d: dict, field: str) -> tuple[int, int]:
        r = d.get(field, {}) or {}
        return int(r.get("min", 0)), int(r.get("max", 0))

    return Features(
        width=w,
        height=h,
        palette_entries_used=len(counts),
        palette_map=palette_map,
        total_pixels=total_pixels,
        water_pixels=water_pixels,
        land_pixels=land_pixels,
        kind_pixels=kind_pixels,
        continent_count=continent_count,
        island_count=island_count,
        landmass_sizes=land_sizes,
        largest_landmass_pixels=largest_size,
        largest_landmass_centroid=largest_centroid,
        lake_count=lake_count,
        open_ocean_pixels=open_ocean,
        coastline_pixels=coastline_pixels,
        kind_centroids=kind_centroids,
        kind_spreads=kind_spreads,
        ice_cap_north=ice_cap_n,
        ice_cap_south=ice_cap_s,
        seed=int(inner.get("Seed", 0)),
        world_w=int(dims.get("WorldWidth", w)),
        world_h=int(dims.get("WorldLength", h)),
        map_preset=str(config.get("MapSizePreset", "")),
        crater_enabled=bool(crater.get("Frequency", 0)) and bool(crater.get("RadiusRange", {}).get("max", 0)),
        biome_weights=weights,
        num_continents_range=_range(inner, "NumContinentsRange"),
        num_islands_range=_range(inner, "NumSmallIslandsRange"),
        num_lakes_range=_range(inner, "NumLakesRange"),
        num_rivers_range=_range(inner, "NumRiversRange"),
    )
