"""Turn a Features record into three paragraphs of prose.

Each paragraph builder is independent: `_paragraph_shape`,
`_paragraph_biomes`, `_paragraph_geology`. `narrate()` composes them.
Tune wording here; feature extraction stays in features.py.
"""

import math

from .biomes import BIOME_HIGHLIGHTS, BiomeHighlight
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


# Maximum distance between two points on a wrapped unit torus whose
# coordinates live in [-1, 1]. Used to normalize torus distances into a
# 0-1 closeness score.
_TORUS_MAX_DIST = 2 ** 0.5


def _torus_distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Distance between two normalized centroids on a wrapped [-1, 1]²
    torus. Eco's worlds wrap at every edge, so the shortest path between
    two points may cross a seam — this accounts for that."""
    dx = abs(a[0] - b[0])
    dy = abs(a[1] - b[1])
    dx = min(dx, 2.0 - dx)
    dy = min(dy, 2.0 - dy)
    return (dx * dx + dy * dy) ** 0.5


def _spread_phrase(spread: float, *, tight_only: bool = False) -> str:
    """Descriptive clustering character. Returns "" when the spread is
    unremarkable; only surfaces commentary on tight clusters or very
    scattered biomes. No absolute directions — the world is a torus.

    Pass `tight_only=True` for runners-up, where "scattered across the
    world" would usually duplicate the same phrasing on the dominant
    biome and drain the paragraph of variety."""
    if spread <= 0.28:
        return "concentrated in one patch"
    if not tight_only and spread >= 0.55:
        return "scattered across the world"
    return ""


def _relative_phrase(kind: str, ref_kind: str, f: Features) -> str:
    """Position of `kind` relative to `ref_kind` on the toroidal world.

    Returns "" unless the two biomes sit notably far apart. On a torus,
    absolute positions are meaningless; only pairwise relationships are
    stable narrative color."""
    a = f.kind_centroids.get(kind)
    b = f.kind_centroids.get(ref_kind)
    if a is None or b is None or kind == ref_kind:
        return ""
    dist = _torus_distance(a, b) / _TORUS_MAX_DIST  # 0..1
    if dist >= 0.70:
        return f"on the far side of the world from the {BIOME_LABELS.get(ref_kind, ref_kind)}"
    if dist >= 0.55:
        return f"across the world from the {BIOME_LABELS.get(ref_kind, ref_kind)}"
    return ""


def _paragraph_shape(f: Features) -> str:
    water_pct = round(f.water_fraction * 100)
    land_pct = 100 - water_pct
    world_m = f.world_meters
    chunks = f.world_w  # Dimensions.WorldWidth is in chunks

    if f.continent_count == 0:
        return (
            f"A {world_m}-meter world that reads as almost pure ocean "
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
        f"({chunks}-chunk) world, {island_clause}."
    )

    # The world is a torus — absolute "anchored in the X" claims aren't
    # meaningful. Only surface the *relative* scale of the biggest landmass.
    anchor_line = ""
    if f.continent_count > 1 and largest_frac > 0.40:
        anchor_line = " The biggest landmass dwarfs its neighbors."
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
    if first_frac >= 0.30:
        lead = f"The land is dominated by {first_label}"
    elif first_frac >= 0.20:
        lead = f"{first_label.capitalize()} leads the biome mix"
    elif first_frac >= 0.10:
        lead = f"{first_label.capitalize()} is the single biggest biome"
    else:
        lead = f"{first_label.capitalize()} narrowly edges out the others"

    # Parenthetical for the lead biome: percent + clustering character
    # (if notable). No absolute directions — the world wraps.
    first_spread = _spread_phrase(f.kind_spreads.get(first_kind, 0.0))
    lead_parts = [f"{round(first_frac * 100)}% of land"]
    if first_spread:
        lead_parts.append(first_spread)
    lead += f" ({', '.join(lead_parts)})"

    # Runners-up. Each runner gets its percentage; optionally a relative-
    # distance note (if it sits far from the dominant biome) and a
    # clustering-character note (if tight or very scattered). Middle-of-
    # the-road biomes get no qualifier so the list stays tight.
    runner_bits: list[str] = []
    for kind, frac in top[1:4]:
        label = BIOME_LABELS.get(kind, kind)
        rel = _relative_phrase(kind, first_kind, f)
        spread_note = _spread_phrase(f.kind_spreads.get(kind, 0.0),
                                     tight_only=True)
        qualifiers = [q for q in (rel, spread_note) if q]
        if qualifiers:
            runner_bits.append(f"{label} at {round(frac * 100)}% "
                               + " and ".join(qualifiers))
        else:
            runner_bits.append(f"{label} at {round(frac * 100)}%")
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


def _biome_sentence(kind: str, h: BiomeHighlight, dominant: bool) -> str:
    """One sentence of player-facing flavor for a named biome.

    Dominant biome: the full trees / fauna / minerals readout alongside
    the industry hook. Secondary biome: just the hook, which already
    summarizes the biome's gameplay role in a phrase."""
    label = BIOME_LABELS.get(kind, kind)
    if dominant:
        return (
            f"The {label} here offers {h.character} — {h.trees}, "
            f"{h.fauna}, and {h.minerals}."
        )
    return f"The {label} adds {h.character}."


def _paragraph_biome_contents(f: Features) -> str:
    """Third paragraph: what the top biomes on this map actually
    contain — the specific trees, fauna, and mineral stacks a player
    would find inside them. Draws on biomes.BIOME_HIGHLIGHTS."""
    top = _top_biomes(f, n=5)
    if not top:
        return ""

    sentences: list[str] = []

    # Dominant biome: full flavor.
    first_kind, _ = top[0]
    first_h = BIOME_HIGHLIGHTS.get(first_kind)
    if first_h is not None:
        sentences.append(_biome_sentence(first_kind, first_h, dominant=True))

    # Second biome: shorter flavor, and only if it's genuinely a
    # different biome (skip if duplicate / missing highlights).
    if len(top) >= 2:
        second_kind, _ = top[1]
        second_h = BIOME_HIGHLIGHTS.get(second_kind)
        if second_h is not None and second_h is not first_h:
            sentences.append(_biome_sentence(second_kind, second_h, dominant=False))

    return " ".join(sentences)


def _paragraph_surface_notes(f: Features) -> str:
    """Fourth (and shortest) paragraph: global, biome-agnostic surface
    observations — ore seams poking through, seafloor visible in the
    shallows, tundra dirt, visible craters. The old "Visible stone is
    mixed: granite N%..." content lived here; it's now covered by the
    biome-contents paragraph, which names each biome's mineral stack
    directly."""
    bits: list[str] = []

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
    basalt_frac = f.kind_pixels.get("basalt", 0) / f.total_pixels if f.total_pixels else 0
    ocean_floor = f.kind_pixels.get("ocean_floor", 0) / f.total_pixels if f.total_pixels else 0
    if basalt_frac > 0.01 or ocean_floor > 0.005:
        bits.append("shallow coastal water shows seafloor through it in places")

    # Tundra/dirt exposure implies frost damage; the player should
    # read it as "tough starting biome."
    dirt_frac = f.land_kind_fraction("dirt")
    if dirt_frac > 0.05:
        bits.append(
            f"bare earth occupies {round(dirt_frac * 100)}% of the land, usually a sign of tundra and high-elevation peaks"
        )

    # Crater-bearing worlds (disabled by default on Sirens).
    if f.crater_enabled:
        bits.append("impact craters scar the terrain, visible as dark circular pits")

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
    contents = _paragraph_biome_contents(features)
    if contents:
        paras.append(contents)
    surface = _paragraph_surface_notes(features)
    if surface:
        paras.append(surface)
    return "\n\n".join(paras)
