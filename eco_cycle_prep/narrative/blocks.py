"""Block-color catalog and pixel → kind classification.

Everything in this module is about turning a (r, g, b) palette entry
from a WorldPreview.gif into a block name + a narrative "kind" label
(water, grass, sand, <biome>_soil, granite, etc.). Kept separate from
features.py and text.py so the catalog is the obvious single source
of truth — update here when SLG adds new biome-soil blocks or changes
an existing color.
"""

# Palette match tolerance. The server keeps block colors stable across
# generations, so we mostly see exact hits; the small window absorbs the
# occasional off-by-one from GIF quantization.
COLOR_TOLERANCE = 6

# Distinct RGB → block-name table. Distilled from the block color map
# the server ships with; each entry corresponds to a block that can
# plausibly show up on top of a chunk column in a freshly generated
# world. `kind` groups blocks into narrative buckets.
# kind values: water, grass, sand, desert, rainforest, cold_forest,
# warm_forest, wetland, taiga, tundra, ice, snow, dirt, limestone,
# sandstone, granite, basalt, ocean_floor, tree_debris, ore, flower, other
BLOCK_CATALOG: list[tuple[int, str, str]] = [
    (0x2B4695, "Water", "water"),
    (0x2B4696, "Water", "water"),
    (0x69AE29, "Grass", "grass"),
    (0xE8D781, "Sand", "sand"),
    (0xD3AD0F, "DesertSand", "desert"),
    (0x007149, "RainforestSoil", "rainforest"),
    (0x2E6739, "ColdForestSoil", "cold_forest"),
    (0x617315, "WarmForestSoil", "warm_forest"),
    (0x467865, "WetlandsSoil", "wetland"),
    (0xB0D1C3, "TaigaSoil", "taiga"),
    (0xB6D5D6, "TundraSoil", "tundra"),
    (0xE2E2E2, "Ice", "ice"),
    (0xF5F5F5, "Snow", "snow"),
    (0x714A32, "Dirt", "dirt"),
    (0xE1E6D2, "Limestone", "limestone"),
    (0xBE7F6C, "Sandstone", "sandstone"),
    (0xA1A1A1, "Granite", "granite"),
    (0x4C4C4C, "Basalt", "basalt"),
    (0x716C53, "OceanSand", "ocean_floor"),
    (0x87673E, "TreeDebris", "tree_debris"),
    (0x303030, "Coal", "ore"),
    (0x975752, "IronOre", "ore"),
    (0xB07620, "CopperOre", "ore"),
    (0xEAC80C, "GoldOre", "ore"),
    (0xFFDBFF, "Fireweed", "flower"),
]

# Kinds that come from biome soil blocks and therefore directly imply
# a biome. Kinds like "grass" or "sand" are ambiguous across biomes.
BIOME_SOIL_KINDS = {
    "rainforest", "cold_forest", "warm_forest", "wetland",
    "taiga", "tundra", "desert",
}

# Kinds that cover land regardless of biome.
LAND_KINDS = {
    "grass", "sand", "desert", "rainforest", "cold_forest", "warm_forest",
    "wetland", "taiga", "tundra", "ice", "snow", "dirt", "limestone",
    "sandstone", "granite", "basalt", "tree_debris", "ore", "flower",
    "other",
}


def classify_rgb(r: int, g: int, b: int) -> tuple[str, str]:
    """Return (block_name, kind). Nearest-neighbour over BLOCK_CATALOG;
    fallback to 'Unknown'/'other' if nothing is within tolerance."""
    best: tuple[str, str] = ("Unknown", "other")
    best_d = 10_000
    for hex_rgb, name, kind in BLOCK_CATALOG:
        br = (hex_rgb >> 16) & 0xFF
        bg = (hex_rgb >> 8) & 0xFF
        bb = hex_rgb & 0xFF
        d = max(abs(r - br), abs(g - bg), abs(b - bb))
        if d < best_d:
            best_d = d
            best = (name, kind)
    if best_d > COLOR_TOLERANCE:
        return "Unknown", "other"
    return best
