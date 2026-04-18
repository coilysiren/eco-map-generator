"""Turn a Features record into three paragraphs of prose.

Each paragraph builder is independent: `_paragraph_shape`,
`_paragraph_biomes`, `_paragraph_geology`. `narrate()` composes them.
Tune wording here; feature extraction stays in features.py.
"""

import math

from .blocks import BIOME_SOIL_KINDS
from .features import Features


# Biome kinds in descending narrative priority (ranked by "how interesting
# is it as a feature"). Ice cap beats rainforest beats desert beats plain
# forest beats grassland.
BIOME_LABELS = {
    "rainforest": "rainforest",
    "cold_forest": "cold forest",
    "warm_forest": "warm forest",
    "wetland": "wetland",
    "taiga": "taiga",
    "tundra": "tundra",
    "desert": "desert",
    "ice": "ice cap",
    "snow": "snowfield",
    "grass": "grassland",
    "sand": "sand",
    "dirt": "bare earth",
}

# Config biome weight field → kind mapping, for realized-vs-target deltas.
# "cool_forest" in config = our "cold_forest" kind.
CONFIG_TO_KIND = {
    "desert": "desert",
    "warm_forest": "warm_forest",
    "cool_forest": "cold_forest",
    "rainforest": "rainforest",
    "wetland": "wetland",
    "taiga": "taiga",
    "tundra": "tundra",
    "ice": "ice",
}


def _top_biomes(features: Features, n: int = 5) -> list[tuple[str, float]]:
    """Return the top-N biome-indicating land kinds by fraction of land."""
    ranked: list[tuple[str, float]] = []
    for kind in BIOME_SOIL_KINDS | {"ice", "snow"}:
        frac = features.land_kind_fraction(kind)
        if frac >= 0.015:  # ≥1.5% of land
            ranked.append((kind, frac))
    ranked.sort(key=lambda kv: kv[1], reverse=True)
    return ranked[:n]


def _direction(cx: float, cy: float, *, edge_bias: float = 0.25) -> str:
    """Map a normalized centroid (cx, cy) with cx>0 east / cy>0 south into
    a compass-ish phrase. Returns "center" if the centroid sits near the
    origin relative to `edge_bias`. This uses image-up == north convention,
    which is how players read a top-down preview."""
    ns = -cy  # flip y so positive == north
    ew = cx
    if abs(ns) < edge_bias and abs(ew) < edge_bias:
        return "center of the map"

    def axis(mag: float, pos: str, neg: str) -> str:
        if mag > edge_bias:
            return pos
        if mag < -edge_bias:
            return neg
        return ""

    ns_word = axis(ns, "north", "south")
    ew_word = axis(ew, "east", "west")
    parts = [p for p in (ns_word, ew_word) if p]
    if len(parts) == 2:
        return f"{parts[0]}{parts[1]}"  # "northeast", "southwest", etc.
    if len(parts) == 1:
        return parts[0]
    return "center"


def _locational_phrase(kind: str, f: Features, *, terse: bool = False) -> str:
    """'in the southeast' / 'spread across the map' depending on spread.

    If terse=True, collapses long-form phrasings into compact forms
    suitable for appearing inside a comma-separated list."""
    center = f.kind_centroids.get(kind)
    spread = f.kind_spreads.get(kind, 0.0)
    if center is None:
        return ""
    direction = _direction(*center)
    central = direction == "center of the map"
    if spread <= 0.28:
        if central:
            return "clustered near the center"
        return f"clustered in the {direction}"
    if spread <= 0.40:
        if central:
            return "distributed unevenly across the interior"
        if terse:
            return f"favoring the {direction}"
        return f"concentrated toward the {direction}"
    if central:
        return "scattered across the map"
    if terse:
        return f"leaning {direction}"
    return f"spread broadly, leaning {direction}"


def _paragraph_shape(f: Features) -> str:
    water_pct = round(f.water_fraction * 100)
    land_pct = 100 - water_pct
    world_m = f.world_meters
    chunks = f.world_w  # Dimensions.WorldWidth is in chunks

    if f.continent_count == 0:
        return (
            f"A {world_m}-meter square world that reads as almost pure ocean "
            f"({water_pct}% open water). No landmass is large enough to call "
            "a continent; whatever land appears is scattered micro-islands."
        )

    continent_words = {1: "A single continent", 2: "Two continents",
                       3: "Three continents", 4: "Four continents",
                       5: "Five continents"}
    continent_word = continent_words.get(f.continent_count,
                                          f"{f.continent_count} continents")
    continent_verb = "occupies" if f.continent_count == 1 else "occupy"

    largest_frac = f.largest_landmass_pixels / f.total_pixels if f.total_pixels else 0
    largest_dir = _direction(*f.largest_landmass_centroid, edge_bias=0.20)

    if f.island_count == 0:
        island_clause = "with no separate islands of note"
    elif f.island_count == 1:
        island_clause = "plus one outlying island"
    elif f.island_count <= 4:
        island_clause = f"flanked by {f.island_count} smaller islands"
    else:
        island_clause = f"ringed by an archipelago of {f.island_count} islands"

    lead = (
        f"{continent_word} {continent_verb} {land_pct}% of a {world_m}-meter "
        f"({chunks}-chunk) square world, {island_clause}."
    )

    anchor_line = ""
    if f.continent_count == 1 and largest_dir != "center of the map":
        anchor_line = f" The main landmass is anchored in the {largest_dir}."
    elif f.continent_count > 1 and largest_frac > 0.40:
        if largest_dir != "center of the map":
            anchor_line = (f" The biggest landmass anchors the {largest_dir} "
                           f"and dwarfs its neighbors.")
        else:
            anchor_line = " One landmass fills the middle of the world and dwarfs the rest."
    elif f.continent_count > 1 and 0.25 < largest_frac <= 0.40:
        anchor_line = " The continents differ noticeably in scale but none overwhelms the others."

    lake_words = {0: "no inland lakes",
                  1: "one inland lake",
                  2: "two inland lakes",
                  3: "three inland lakes",
                  4: "four inland lakes",
                  5: "five inland lakes",
                  6: "six inland lakes",
                  7: "seven inland lakes"}
    lake_phrase = lake_words.get(f.lake_count, f"{f.lake_count} inland lakes")

    coast_desc = ""
    if f.land_pixels > 0:
        # Ratio of coast-adjacent land pixels to sqrt(land area). Calibrated
        # from samples: ~0.9 for a single smooth island, ~1.1+ for moderately
        # ragged, 1.5+ for finger-like coasts.
        ruggedness = f.coastline_pixels / (math.sqrt(f.land_pixels) * 4.0)
        if ruggedness > 1.5:
            coast_desc = "deeply indented, full of inlets and peninsulas"
        elif ruggedness > 1.1:
            coast_desc = "moderately ragged, with a few pronounced bays"
        else:
            coast_desc = "smooth, with few bays or peninsulas"

    if f.lake_count == 0:
        water_line = f" No lakes break up the interior; the coastlines are {coast_desc}." if coast_desc else ""
    else:
        lake_verb = "breaks" if f.lake_count == 1 else "break"
        water_line = (
            f" {lake_phrase.capitalize()} {lake_verb} up the interior, and "
            f"the coastlines are {coast_desc}." if coast_desc
            else f" {lake_phrase.capitalize()} {lake_verb} up the interior."
        )

    return lead + anchor_line + water_line


def _paragraph_biomes(f: Features) -> str:
    top = _top_biomes(f, n=5)
    if not top:
        return "The preview doesn't resolve clear biome signatures from soil colors alone."

    first_kind, first_frac = top[0]
    first_label = BIOME_LABELS.get(first_kind, first_kind)
    first_loc = _locational_phrase(first_kind, f, terse=True)
    if first_frac >= 0.30:
        lead = f"The land is dominated by {first_label}"
    elif first_frac >= 0.20:
        lead = f"{first_label.capitalize()} leads the biome mix"
    elif first_frac >= 0.10:
        lead = f"{first_label.capitalize()} is the single biggest biome"
    else:
        lead = f"{first_label.capitalize()} narrowly edges out the others"

    lead += f" ({round(first_frac * 100)}% of land, {first_loc})"

    # Runners-up with their own locations — keeps the paragraph from
    # being a flat list. Terse locational phrasing inside the list so
    # three back-to-back entries don't all repeat "spread broadly."
    runner_bits: list[str] = []
    for kind, frac in top[1:4]:
        label = BIOME_LABELS.get(kind, kind)
        loc = _locational_phrase(kind, f, terse=True)
        runner_bits.append(f"{label} at {round(frac * 100)}% {loc}")
    if runner_bits:
        if len(runner_bits) == 1:
            lead += f". Behind it, {runner_bits[0]}"
        else:
            lead += (". Behind it, "
                     + ", ".join(runner_bits[:-1])
                     + f", and {runner_bits[-1]}")
    lead += "."

    # "Didn't make the preview" callouts. We deliberately don't expose
    # target percentages here — the Discord audience has no way to know
    # the server's configured biome weights, so numeric comparisons read
    # as noise. The useful signal is "you won't find this biome on this
    # world," which is real player-facing info. Only fire when the server
    # was tuned to include a meaningful share (≥5%) of the biome in
    # question, and the preview shows essentially none of it.
    missing: list[str] = []
    for cfg_key, kind in CONFIG_TO_KIND.items():
        target = f.biome_weights.get(cfg_key, 0.0)
        if target < 0.05:
            continue
        realized = f.land_kind_fraction(kind)
        if realized < 0.01:
            missing.append(BIOME_LABELS.get(kind, kind))

    absence_line = ""
    if missing:
        if len(missing) == 1:
            absence_line = f" No visible {missing[0]} made it onto the preview."
        elif len(missing) == 2:
            absence_line = (f" No visible {missing[0]} or {missing[1]} "
                            "made it onto the preview.")
        else:
            joined = ", ".join(missing[:-1]) + f", or {missing[-1]}"
            absence_line = f" No visible {joined} made it onto the preview."

    cap = ""
    if f.ice_cap_north and f.ice_cap_south:
        cap = " Ice caps ride both the northern and southern edges."
    elif f.ice_cap_north:
        cap = " A visible ice cap rides the northern edge."
    elif f.ice_cap_south:
        cap = " A visible ice cap rides the southern edge."

    # Overall climate characterization from the biome mix.
    hot = f.land_kind_fraction("desert") + f.land_kind_fraction("rainforest") + f.land_kind_fraction("warm_forest")
    cold = f.land_kind_fraction("cold_forest") + f.land_kind_fraction("taiga") + f.land_kind_fraction("tundra") + f.land_kind_fraction("ice") + f.land_kind_fraction("snow")
    wet = f.land_kind_fraction("rainforest") + f.land_kind_fraction("wetland")
    dry = f.land_kind_fraction("desert")
    mood_bits: list[str] = []
    if hot - cold > 0.12:
        mood_bits.append("warm overall")
    elif cold - hot > 0.12:
        mood_bits.append("cool overall")
    if wet - dry > 0.08:
        mood_bits.append("wet")
    elif dry - wet > 0.06:
        mood_bits.append("dry")
    mood = ""
    if mood_bits:
        mood = f" Climate reads {' and '.join(mood_bits)}."

    return lead + mood + absence_line + cap


def _paragraph_geology(f: Features) -> str:
    """Third paragraph: surface stone, ore, notable geological features."""
    bits: list[str] = []

    granite = f.land_kind_fraction("granite")
    sandstone = f.land_kind_fraction("sandstone")
    limestone = f.land_kind_fraction("limestone")
    basalt_frac = f.kind_pixels.get("basalt", 0) / f.total_pixels if f.total_pixels else 0
    ocean_floor = f.kind_pixels.get("ocean_floor", 0) / f.total_pixels if f.total_pixels else 0
    dirt_frac = f.land_kind_fraction("dirt")

    stone_bits: list[str] = []
    if granite > 0.04:
        stone_bits.append(f"granite ({round(granite * 100)}%) cutting through the forested zones")
    elif granite > 0.01:
        stone_bits.append(f"granite outcrops ({round(granite * 100)}%)")
    if limestone > 0.02:
        stone_bits.append(f"limestone ({round(limestone * 100)}%) exposed across grassland and coast")
    elif limestone > 0.005:
        stone_bits.append(f"limestone ({round(limestone * 100)}%)")
    if sandstone > 0.02:
        stone_bits.append(f"sandstone ({round(sandstone * 100)}%) rising out of the desert")
    elif sandstone > 0.005:
        stone_bits.append(f"sandstone ({round(sandstone * 100)}%)")

    if stone_bits:
        if len(stone_bits) == 1:
            bits.append("Visible stone is mostly " + stone_bits[0])
        else:
            bits.append("Visible stone is mixed: "
                       + ", ".join(stone_bits[:-1])
                       + f", and {stone_bits[-1]}")
    else:
        bits.append("Stone exposure is light; most rock sits under soil rather than breaking through")

    # Ore seams on the surface — a real player-facing tell.
    ore_px = f.kind_pixels.get("ore", 0)
    if ore_px > 0:
        ore_names: list[str] = []
        for idx_meta in f.palette_map.values():
            if idx_meta.get("kind") != "ore":
                continue
            name = idx_meta.get("name", "")
            if name == "IronOre":
                ore_names.append("iron")
            elif name == "Coal":
                ore_names.append("coal")
            elif name == "CopperOre":
                ore_names.append("copper")
            elif name == "GoldOre":
                ore_names.append("gold")
        ore_names = sorted(set(ore_names))
        if ore_names:
            bits.append("Seams of "
                       + ("/".join(ore_names))
                       + " break through to the surface — an early read on mining accessibility")
        else:
            bits.append("A few unidentified ore patches break through to the surface")

    # Ocean-floor glimpses (shallow water or coastal basalt).
    if basalt_frac > 0.01 or ocean_floor > 0.005:
        bits.append("shallow coastal water shows seafloor through it in places")

    # Tundra/dirt exposure implies frost damage; callers can read that as
    # 'tough starting biome'.
    if dirt_frac > 0.05:
        bits.append(
            f"bare earth occupies {round(dirt_frac * 100)}% of the land, usually a sign of tundra and high-elevation peaks"
        )

    # Crater-bearing worlds (disabled by default on Sirens).
    if f.crater_enabled:
        bits.append("and impact craters scar the terrain, visible as dark circular pits")

    if not bits:
        return ""
    if len(bits) == 1:
        return bits[0] + "."
    return bits[0] + ". " + ". ".join(b[0].upper() + b[1:] for b in bits[1:]) + "."


def narrate(features: Features) -> str:
    paras = [
        _paragraph_shape(features),
        _paragraph_biomes(features),
    ]
    geo = _paragraph_geology(features)
    if geo:
        paras.append(geo)
    return "\n\n".join(paras)
