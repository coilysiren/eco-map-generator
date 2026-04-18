"""Compose the server ad that gets pasted into Strange Loop Games' main
Eco Discord each cycle. Pulls stable fields from SSM + the live Network
/ Difficulty / WorldGenerator configs, and lists mods based on what's
actually in eco-mods + eco-mods-public.

The Configs bullet list is a curated human description — there's no clean
mapping from JSON knobs to player-facing phrasing — so it lives as a
constant here and you edit it per cycle.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from . import mods as mods_mod
from . import ssm, worldgen

# ---------------------------------------------------------------------------
# Curated per-cycle content. Edit these lists when the knobs drift.

AD_SUMMARY = (
    "High collab server with an in-house modder and highly experimental "
    "settings and configuration!"
)
AD_OBJECTIVE = (
    "Build highly collaborative towns and have fun with all the cool content "
    "this game gives us."
)
AD_LOCATION = "US West"
AD_LANGUAGES = "English"
AD_WHITELIST = "No"

# Configs bullets — copied from cycle 11's ad. Tune per cycle by editing here.
DEFAULT_CONFIG_BULLETS: list[str] = [
    "60 day meteor",
    "High collab",
    "No exhaustion",
    "Slower tool integrity loss",
    "Extra experience for late joiners",
    "Claim papers and claim stakes on learning skills",
    "lower integrity loss",
    "less animal attacks",
    "3x stack size",
    "2x pollution",
    "2x plant growth rate",
    "2x inventory connection range",
    "2x food shelf life",
    "2x higher fuel efficiency",
    "50% lower item weight",
    "10 item crafting queues",
    "Paid items enabled",
    "Deep ocean building off",
    "Expensive endgame crafts (laser + computer lab)",
]

# Folder names in eco-mods/Mods/UserCode/ that aren't player-facing "mods"
# (overrides, tooling scaffolding) and should be hidden from the ad.
CONTENT_MODS_HIDE = {
    "AutoGen",
    "Objects",
    "Tools",
    "SkillsRequirements",  # support lib, included via Skill Trees in Code Mods
    "NutritionMod",  # support lib for Nid/NutriView
    "CavRnMods",  # internal helper package
    # Deepflame — per 2026-04-16 ask, disabled for cycle 13
    "DFBargeIndustries",
    "DFEasierShopCart",
    "DFEngineering",
    "DFGlobalPlanetaryDefense",
    # Listed under Custom Content Mods instead (it's a BunWulf mod)
    "BunWulfEducational",
}

# Mods that live in eco-mods-public but Kai advertises as Content Mods
# (they're popular enough to be treated as first-class public mods in
# the ad even though the source sits in her private-authored repo).
CONTENT_MODS_FROM_PUBLIC: dict[str, str] = {
    "BunWulfBiochemical": "Biochemist",
}

# Pretty display names — use when the folder name doesn't format cleanly.
CONTENT_DISPLAY = {
    "AlpacacornItemPack": "Alpacacorn Item Pack",
    "AnimalHusbandry": "Animal Husbandry",
    "Beekeeping": "Beekeeping",
    "BunWulfBiochemical": "Biochemist",
    "BunWulfEducational": "Librarian",
    "DirtDecomposition": "Dirt Decomposition",
    "ElixrModsUNC": "Elixir Mods Trucking",
    "FishingReloaded": "Fishing",
    "Greenhouses": "Greenhouses",
    "Mixology": "Mixology",
    "PanDrippingsMod": "Pan Drippings",
    "StorageMore": "Storage More",
}

CUSTOM_DISPLAY = {
    "BunWulfAgricultural": "BunWulf Agricultural",
    "BunWulfEducational": "Librarian",
    "BunWulfHardwareCo": "BunWulf HardwareCo",
    "DirectCarbonCapture": "Direct Carbon Capture",
    "EcoNil": "EcoNil",
    "MinesQuarries": "Mines & Quarries & Pits",
    "ShopBoat": "Shop Boat",
    "WorldCounter": "World Counter",
}

# Code (DLL) mods — small stable set; beautified captions include the bits
# of marketing copy from the cycle-11 ad.
CODE_MODS: list[str] = [
    "Discord Link, discord invite: {invite}",
    "Nutri View: shows ideal nutrient information when hovering your food stats",
    "Skill Trees: specializing in higher level skills requires specializing in their "
    "pre-requisites, and you can only take 1 of certainly highly advanced skills",
    "Easy Mining",
    "Easy Logging",
    "Easy Digging",
]


# ---------------------------------------------------------------------------

COLLAB_LABEL = {
    "LowCollaboration": "Low Collab",
    "MediumCollaboration": "Medium Collab",
    "HighCollaboration": "High Collab",
}

NETWORK_CONFIG = worldgen.ECO_CONFIGS / "Configs" / "Network.eco"
DIFFICULTY_CONFIG = worldgen.ECO_CONFIGS / "Configs" / "Difficulty.eco"


def _camel_space(name: str) -> str:
    # "FooBarBaz" → "Foo Bar Baz"
    return re.sub(r"(?<!^)(?=[A-Z])", " ", name)


def _content_display(name: str) -> str:
    return CONTENT_DISPLAY.get(name, _camel_space(name))


def _custom_display(name: str) -> str:
    return CUSTOM_DISPLAY.get(name, _camel_space(name))


def _visible_dirs(root: Path) -> list[str]:
    if not root.is_dir():
        return []
    return sorted(p.name for p in root.iterdir() if p.is_dir() and not p.name.startswith("."))


def list_content_mods() -> list[str]:
    names = _visible_dirs(mods_mod.ECO_MODS / "Mods" / "UserCode")
    out: list[str] = [
        _content_display(n) for n in names if n not in CONTENT_MODS_HIDE
    ]
    # Pull in the content-class mods that live in eco-mods-public.
    public_dirs = set(_visible_dirs(mods_mod.ECO_MODS_PUBLIC / "Mods" / "UserCode"))
    for folder, display in CONTENT_MODS_FROM_PUBLIC.items():
        if folder in public_dirs:
            out.append(display)
    return sorted(out)


def list_custom_mods() -> list[str]:
    names = _visible_dirs(mods_mod.ECO_MODS_PUBLIC / "Mods" / "UserCode")
    # Folders that land in Content Mods (see CONTENT_MODS_FROM_PUBLIC) are
    # not duplicated here.
    skip = set(CONTENT_MODS_FROM_PUBLIC)
    return [_custom_display(n) for n in names if n not in skip]


def _read_collab() -> str:
    data = json.loads(DIFFICULTY_CONFIG.read_text(encoding="utf-8"))
    raw = data["GameSettings"].get("CollaborationLevel", "")
    return COLLAB_LABEL.get(raw, raw)


def _read_meteor_days() -> int:
    data = json.loads(DIFFICULTY_CONFIG.read_text(encoding="utf-8"))
    return int(
        data["GameSettings"].get("AdvancedGameSettings", {}).get(
            "MeteorImpactInDays", 60
        )
    )


def _read_world_size() -> str:
    data = json.loads(
        (worldgen.ECO_CONFIGS / "Configs" / "WorldGenerator.eco").read_text(
            encoding="utf-8"
        )
    )
    preset = data.get("MapSizePreset", "Small")
    # Eco presets (current as of 2026): Small 100x100, Medium 160x160, Large 240x240
    table = {"Small": "100 x 100", "Medium": "160 x 160", "Large": "240 x 240"}
    return table.get(preset, preset)


def _ad_config_bullets() -> list[str]:
    # Currently pass-through; leaving a seam here so future iterations can
    # pull some bullets programmatically from Difficulty/EcoSim/Balance.eco
    # and reconcile with the curated list.
    return DEFAULT_CONFIG_BULLETS


def render(cycle: int, start_ts: int) -> str:
    server_id = ssm.get("/eco/server-id")
    invite = ssm.get("/discord/server-ad-invite")
    collab = _read_collab()
    meteor = _read_meteor_days()
    size = _read_world_size()

    lines: list[str] = []
    lines.append(f"**Summary:** {AD_SUMMARY} ")
    lines.append(f"**World Objective:** {AD_OBJECTIVE}")
    lines.append(f"**Server ID:** `{server_id}`")
    lines.append(f"**Cycle:** {cycle}")
    lines.append(f"**Start Time:** <t:{start_ts}:F>")
    lines.append(f"**Meteor:** {meteor} days")
    lines.append(f"**Location:** {AD_LOCATION}")
    lines.append(f"**Languages:** {AD_LANGUAGES}")
    lines.append(f"**Whitelist:** {AD_WHITELIST}")
    lines.append(f"**Difficulty:** {collab}")
    lines.append(f"**World Size:** {size}")
    lines.append(f"**Discord:** {invite}")
    lines.append("")
    lines.append("### Configs:")
    lines.append("")
    for b in _ad_config_bullets():
        lines.append(f"- {b}")
    lines.append("")
    lines.append("### Content Mods:")
    lines.append("")
    for m in list_content_mods():
        lines.append(f"- {m}")
    lines.append("")
    lines.append("### Custom Content Mods (this server only):")
    lines.append("")
    for m in list_custom_mods():
        lines.append(f"- {m}")
    lines.append("")
    lines.append("### Code Mods:")
    lines.append("")
    for c in CODE_MODS:
        lines.append(f"- {c.format(invite=invite)}")
    return "\n".join(lines) + "\n"


PREP_DIR = Path(__file__).resolve().parent.parent / "rolls" / "_prep"


def run(cycle: int, start_ts: int, save: bool = True) -> str:
    md = render(cycle=cycle, start_ts=start_ts)
    if save:
        PREP_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out = PREP_DIR / f"server-ad-cycle-{cycle}-{stamp}.md"
        out.write_text(md, encoding="utf-8")
        print(f"# saved to {out}\n", flush=True)
    print(md, end="", flush=True)
    return md


# ---------------------------------------------------------------------------
# Sync the ad's DetailedDescription back into eco-configs/Configs/Network.eco
# so the in-game server info panel matches the public ad.


def _detailed_description(cycle: int) -> str:
    # Plain-ASCII on purpose: Eco's in-game description panel does its own
    # markup; no need for typographic dashes. (Also matches Kai's "no em-dash
    # in drafted prose" style rule.)
    configs = _ad_config_bullets()
    content = list_content_mods() + list_custom_mods()
    parts = [
        f"Cycle {cycle} - all time zones welcome!",
        "",
        "Configs: " + "; ".join(configs) + ".",
        "",
        "Mods: " + ", ".join(content) + ".",
    ]
    return "\n".join(parts)


def sync_network_description(cycle: int) -> None:
    data = json.loads(NETWORK_CONFIG.read_text(encoding="utf-8"))
    old = data.get("DetailedDescription", "")
    new = _detailed_description(cycle)
    if old == new:
        print(f"Network.eco DetailedDescription unchanged")
        return
    data["DetailedDescription"] = new
    NETWORK_CONFIG.write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        f"updated Network.eco DetailedDescription ({len(old)} → {len(new)} chars).\n"
        "commit + push eco-configs, then `inv eco.copy-configs --with-world-gen` on kai-server."
    )
