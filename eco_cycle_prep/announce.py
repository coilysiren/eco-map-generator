"""Compose the two cycle-prep messages that go to Discord:

1. The server ad pasted into Strange Loop Games' main Eco Discord each
   cycle (terse format, cross-server audience).
2. The "Mods / Configs at Cycle N start:" post in Sirens' own
   #eco-configs channel (longer, links to mod.io sources).

Structure lives in templates/ (checked into git, generic). Server-specific
strings (summary, objective, location, code-mod descriptions) live in
rolls/_prep/server-identity.json (gitignored — it's semi-private branding
that shouldn't ship publicly with the tool). Per-cycle config bullets live
in rolls/_prep/ad-configs-cycle-<N>.txt (also gitignored)."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from string import Template

from . import mods as mods_mod
from . import ssm, worldgen

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
PREP_DIR = REPO_ROOT / "rolls" / "_prep"

IDENTITY_PATH = PREP_DIR / "server-identity.json"

# Folder names in eco-mods/Mods/UserCode/ that aren't player-facing "mods"
# (overrides, tooling scaffolding) and should be hidden from either message.
# Enabling/disabling whole mods is done by editing the eco-mods source repo,
# not by listing them here.
CONTENT_MODS_HIDE = {
    "AutoGen",
    "Objects",
    "Tools",
    "SkillsRequirements",  # support lib, shown via "Skill Trees" in Code Mods
    "NutritionMod",  # support lib for Nid/NutriView
    "CavRnMods",  # internal helper package
    # Listed under "Custom Content Mods" instead (it's a BunWulf mod)
    "BunWulfEducational",
}

# Mods that live in eco-mods-public but Kai advertises as Content Mods
# (popular enough to be first-class public mods in the ad, even though the
# source sits in her private-authored repo).
CONTENT_MODS_FROM_PUBLIC: dict[str, str] = {
    "BunWulfBiochemical": "Biochemist",
}

CONTENT_DISPLAY = {
    "AlpacacornItemPack": "Alpacacorn Item Pack",
    "AnimalHusbandry": "Animal Husbandry",
    "Beekeeping": "Beekeeping",
    "BunWulfBiochemical": "Biochemist",
    "DFEasierShopCart": "Easier Shop Cart",
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

COLLAB_SHORT = {
    "LowCollaboration": "Low Collab",
    "MediumCollaboration": "Medium Collab",
    "HighCollaboration": "High Collab",
}
COLLAB_LONG = {
    "LowCollaboration": "Low Collaboration",
    "MediumCollaboration": "Medium Collaboration",
    "HighCollaboration": "High Collaboration",
}

NETWORK_CONFIG = worldgen.ECO_CONFIGS / "Configs" / "Network.eco"
DIFFICULTY_CONFIG = worldgen.ECO_CONFIGS / "Configs" / "Difficulty.eco"
WORLDGEN_CONFIG = worldgen.ECO_CONFIGS / "Configs" / "WorldGenerator.eco"


# ---------------------------------------------------------------------------
# Identity + templates
# ---------------------------------------------------------------------------


class IdentityMissing(FileNotFoundError):
    pass


def load_identity() -> dict:
    if not IDENTITY_PATH.exists():
        raise IdentityMissing(
            f"server-identity.json not found at {IDENTITY_PATH}.\n"
            "This file holds server-specific branding (summary, objective, "
            "location, code-mod descriptions) and is gitignored. See "
            "templates/server-ad.md.tmpl for expected keys."
        )
    return json.loads(IDENTITY_PATH.read_text(encoding="utf-8"))


def _load_template(name: str) -> Template:
    return Template((TEMPLATE_DIR / name).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Data-source helpers (configs + mod dirs)
# ---------------------------------------------------------------------------


def _camel_space(name: str) -> str:
    # "FooBarBaz" -> "Foo Bar Baz"
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
    public_dirs = set(_visible_dirs(mods_mod.ECO_MODS_PUBLIC / "Mods" / "UserCode"))
    for folder, display in CONTENT_MODS_FROM_PUBLIC.items():
        if folder in public_dirs:
            out.append(display)
    return sorted(out)


def list_custom_mods() -> list[str]:
    names = _visible_dirs(mods_mod.ECO_MODS_PUBLIC / "Mods" / "UserCode")
    skip = set(CONTENT_MODS_FROM_PUBLIC)
    return [_custom_display(n) for n in names if n not in skip]


# Parse `[Display](https://mod.io/...)` bullets from eco-mods/README.md
# so the eco-configs channel post can carry mod.io links directly.
MOD_LINK_RE = re.compile(r"^\s*-\s*\[([^\]]+)\]\((https://mod\.io/[^\)]+)\)")


def list_public_mods_with_links() -> list[str]:
    readme = mods_mod.MODS_README.read_text(encoding="utf-8")
    out: list[str] = []
    for line in readme.splitlines():
        m = MOD_LINK_RE.match(line)
        if m:
            out.append(f"- [{m.group(1)}]({m.group(2)})")
    return out


def _read_collab_raw() -> str:
    data = json.loads(DIFFICULTY_CONFIG.read_text(encoding="utf-8"))
    return data["GameSettings"].get("CollaborationLevel", "")


def _read_meteor_days() -> int:
    data = json.loads(DIFFICULTY_CONFIG.read_text(encoding="utf-8"))
    return int(
        data["GameSettings"].get("AdvancedGameSettings", {}).get(
            "MeteorImpactInDays", 60
        )
    )


def _read_world_size() -> str:
    data = json.loads(WORLDGEN_CONFIG.read_text(encoding="utf-8"))

    # An explicit Dimensions block overrides MapSizePreset — it's the actual
    # world size the server will generate. The block is nested, so walk for it.
    def _find_dims(obj):
        if isinstance(obj, dict):
            if "WorldLength" in obj and "WorldWidth" in obj:
                return obj["WorldLength"], obj["WorldWidth"]
            for v in obj.values():
                r = _find_dims(v)
                if r is not None:
                    return r
        elif isinstance(obj, list):
            for v in obj:
                r = _find_dims(v)
                if r is not None:
                    return r
        return None

    dims = _find_dims(data)
    if dims:
        return f"{dims[0]} x {dims[1]}"
    preset = data.get("MapSizePreset", "Small")
    # Eco presets (current as of 2026): Small 100x100, Medium 160x160, Large 240x240
    table = {"Small": "100 x 100", "Medium": "160 x 160", "Large": "240 x 240"}
    return table.get(preset, preset)


def _read_exhaustion_note() -> str:
    data = json.loads(DIFFICULTY_CONFIG.read_text(encoding="utf-8"))
    enabled = data["GameSettings"].get("ExhaustionEnabled", True)
    return "Enabled" if enabled else "Disabled"


SETTLEMENTS_CONFIG = worldgen.ECO_CONFIGS / "Configs" / "Settlements.eco"
BALANCE_CONFIG = worldgen.ECO_CONFIGS / "Configs" / "Balance.eco"


def _read_dinner_party_max() -> int:
    data = json.loads(SETTLEMENTS_CONFIG.read_text(encoding="utf-8"))
    return int(data["DinnerPartyConfig"].get("MaxDinnerPartiesPerDayCountedForBonus", 1))


def _read_freshness_minutes() -> int:
    data = json.loads(SETTLEMENTS_CONFIG.read_text(encoding="utf-8"))
    return int(data["DinnerPartyConfig"].get("FreshnessTimeMinutesPreparedFood", 60))


def _read_claim_papers() -> float:
    data = json.loads(DIFFICULTY_CONFIG.read_text(encoding="utf-8"))
    return float(
        data["GameSettings"].get("AdvancedGameSettings", {}).get(
            "ClaimPapersGrantedUponSkillscrollConsumed", 0
        )
    )


def _read_claim_stakes() -> float:
    data = json.loads(DIFFICULTY_CONFIG.read_text(encoding="utf-8"))
    return float(
        data["GameSettings"].get("AdvancedGameSettings", {}).get(
            "ClaimStakesGrantedUponSkillscrollConsumed", 0
        )
    )


def _read_tool_repair_penalty() -> float:
    data = json.loads(BALANCE_CONFIG.read_text(encoding="utf-8"))
    return float(data.get("ToolRepairPenalty", 0.2))


def _read_max_height() -> int:
    data = json.loads(WORLDGEN_CONFIG.read_text(encoding="utf-8"))
    return int(data.get("MaxGenerationHeight", 120))


def _ad_config_bullets(cycle: int) -> list[str]:
    """Per-cycle ad-configs override at rolls/_prep/ad-configs-cycle-<N>.txt.
    Lines starting with `#` are comments; blank lines are skipped."""
    override = PREP_DIR / f"ad-configs-cycle-{cycle}.txt"
    if not override.exists():
        raise FileNotFoundError(
            f"Config bullets for cycle {cycle} not found at {override}.\n"
            "Create the file (one bullet per line, `#` for comments)."
        )
    bullets: list[str] = []
    for raw in override.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        bullets.append(line)
    if not bullets:
        raise ValueError(f"{override} exists but contains no bullets.")
    return bullets


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------


def render_server_ad(cycle: int, start_ts: int) -> str:
    identity = load_identity()
    server_id = ssm.get("/eco/server-id")
    invite = ssm.get("/discord/server-ad-invite")
    collab_short = COLLAB_SHORT.get(_read_collab_raw(), _read_collab_raw())

    config_lines = "\n".join(f"- {b}" for b in _ad_config_bullets(cycle))
    content_lines = "\n".join(f"- {m}" for m in list_content_mods())
    custom_lines = "\n".join(f"- {m}" for m in list_custom_mods())
    code_lines = "\n".join(f"- {c.format(invite=invite)}" for c in identity["code_mods"])

    return _load_template("eco-server-ad.md.tmpl").substitute(
        summary=identity["summary"],
        objective=identity["objective"],
        server_id=server_id,
        cycle=cycle,
        start_ts=start_ts,
        meteor_days=_read_meteor_days(),
        location=identity["location"],
        languages=identity["languages"],
        whitelist=identity["whitelist"],
        difficulty=collab_short,
        world_size=_read_world_size(),
        invite=invite,
        config_bullets=config_lines,
        content_mods=content_lines,
        custom_mods=custom_lines,
        code_mods=code_lines,
    )


def render_sirens_configs_channel(cycle: int, start_ts: int) -> str:
    """Verbose Discord-style announcement for Sirens' own #eco-configs channel.
    Budgeted to Discord's 2000-char message limit (caller should check).

    TODO: multi-message split. We currently clip mod.io links, per-mod
    blurbs, per-config rationale, and worldgen theme notes to hit the
    2000-char cap. Future iteration should render a list of messages
    (header + configs / content-mods / code-mods / gameplay-and-world)
    and post them in sequence. Template comments mark what to add."""
    identity = load_identity()
    invite = ssm.get("/discord/server-ad-invite")
    collab_long = COLLAB_LONG.get(_read_collab_raw(), _read_collab_raw())

    config_lines = "\n".join(f"- {b}" for b in _ad_config_bullets(cycle))
    content_lines = "\n".join(f"- {m}" for m in list_content_mods())
    custom_lines = "\n".join(f"- {m}" for m in list_custom_mods())
    code_lines = "\n".join(f"- {c.format(invite=invite)}" for c in identity["code_mods"])

    return _load_template("sirens-configs-channel.md.tmpl").substitute(
        cycle=cycle,
        start_ts=start_ts,
        difficulty_long=collab_long,
        meteor_days=_read_meteor_days(),
        world_size=_read_world_size(),
        invite=invite,
        config_bullets=config_lines,
        content_mods=content_lines,
        custom_mods=custom_lines,
        code_mods=code_lines,
        max_dinner_parties=_read_dinner_party_max(),
        freshness_minutes=_read_freshness_minutes(),
        claim_papers=_fmt_num(_read_claim_papers()),
        claim_stakes=_fmt_num(_read_claim_stakes()),
        tool_repair_penalty=_fmt_num(_read_tool_repair_penalty()),
        max_height=_read_max_height(),
    )


def _fmt_num(x: float) -> str:
    # 2.0 -> "2", 0.1 -> "0.1"
    return str(int(x)) if float(x).is_integer() else str(x)


def render_ingame_name(cycle: int) -> str:
    collab_short = COLLAB_SHORT.get(_read_collab_raw(), _read_collab_raw())
    return _load_template("ingame-name.md.tmpl").substitute(
        cycle=cycle,
        difficulty_short=collab_short,
        world_size=_read_world_size(),
    ).rstrip("\n")


def render_ingame_description(cycle: int) -> str:
    """500-char budget (hard cap in Eco's master-server registration).
    Tagline strings below are sized to fit within that cap."""
    invite = ssm.get("/discord/server-ad-invite")
    collab_long = COLLAB_LONG.get(_read_collab_raw(), _read_collab_raw())

    content = list_content_mods()
    custom = list_custom_mods()
    total_mods = len(content) + len(custom)
    # Pick a handful of name-recognition hits: one or two Content mods
    # people already know, plus the Sirens-only customs that read as
    # "wait, that's cool" to a server-browser skimmer.
    highlights: list[str] = []
    for m in ["Biochemist", "Animal Husbandry", "Greenhouses"]:
        if m in content:
            highlights.append(m)
    highlights.extend(custom[:3])
    mods_tagline = f"{total_mods}+ including {', '.join(highlights)}"

    # Pick 5-6 highest-signal configs
    config_tagline = (
        f"2x plant growth / fuel / connection, 50% item weight, "
        f"{_read_dinner_party_max()}/day dinner parties, softer tool wear, "
        "paid items allowed, no exhaustion"
    )

    return _load_template("ingame-description.md.tmpl").substitute(
        cycle=cycle,
        meteor_days=_read_meteor_days(),
        difficulty_long=collab_long,
        world_size=_read_world_size(),
        config_tagline=config_tagline,
        mods_tagline=mods_tagline,
        invite=invite,
    ).rstrip("\n")


# ---------------------------------------------------------------------------
# Entrypoints used by tasks.py
# ---------------------------------------------------------------------------


def run(cycle: int, start_ts: int, save: bool = True) -> str:
    md = render_server_ad(cycle=cycle, start_ts=start_ts)
    if save:
        PREP_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out = PREP_DIR / f"server-ad-cycle-{cycle}-{stamp}.md"
        out.write_text(md, encoding="utf-8")
        print(f"# saved to {out}\n", flush=True)
    print(md, end="", flush=True)
    return md


def run_sirens_configs(cycle: int, start_ts: int, save: bool = True) -> str:
    md = render_sirens_configs_channel(cycle=cycle, start_ts=start_ts)
    if save:
        PREP_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out = PREP_DIR / f"sirens-configs-channel-cycle-{cycle}-{stamp}.md"
        out.write_text(md, encoding="utf-8")
        print(f"# saved to {out}  ({len(md)} chars, discord limit 2000)\n", flush=True)
    print(md, end="", flush=True)
    return md


def run_ingame(cycle: int, save: bool = True) -> dict[str, str]:
    """Render the in-game Name + DetailedDescription strings. Does NOT write
    to Network.eco — call `sync_ingame_to_network(cycle)` explicitly once
    you're happy with the output."""
    name = render_ingame_name(cycle=cycle)
    desc = render_ingame_description(cycle=cycle)
    if save:
        PREP_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        (PREP_DIR / f"ingame-name-cycle-{cycle}-{stamp}.txt").write_text(
            name + "\n", encoding="utf-8"
        )
        (PREP_DIR / f"ingame-description-cycle-{cycle}-{stamp}.txt").write_text(
            desc + "\n", encoding="utf-8"
        )
    print(f"\n=== ingame-name ({len(name)} chars, eco limit 250) ===\n{name}\n")
    print(f"=== ingame-description ({len(desc)} chars, eco limit 500) ===\n{desc}\n")
    return {"name": name, "description": desc}


# ---------------------------------------------------------------------------
# Sync the ad's DetailedDescription back into eco-configs/Configs/Network.eco
# so the in-game server info panel matches the public ad.
# ---------------------------------------------------------------------------


NAME_CAP = 250
DESCRIPTION_CAP = 500


def sync_ingame_to_network(cycle: int) -> None:
    """Write render_ingame_name() and render_ingame_description() into the
    git-tracked Network.eco's Name + DetailedDescription fields. Enforces
    the Eco master-server caps (250 / 500) and raises if exceeded."""
    name = render_ingame_name(cycle=cycle)
    desc = render_ingame_description(cycle=cycle)
    if len(name) > NAME_CAP:
        raise ValueError(f"ingame-name is {len(name)} chars, exceeds cap {NAME_CAP}")
    if len(desc) > DESCRIPTION_CAP:
        raise ValueError(
            f"ingame-description is {len(desc)} chars, exceeds cap {DESCRIPTION_CAP}"
        )

    data = json.loads(NETWORK_CONFIG.read_text(encoding="utf-8"))
    old_name = data.get("Name", "")
    old_desc = data.get("DetailedDescription", "")
    changed = []
    if old_name != name:
        data["Name"] = name
        changed.append(f"Name ({len(old_name)} -> {len(name)} chars)")
    if old_desc != desc:
        data["DetailedDescription"] = desc
        changed.append(f"DetailedDescription ({len(old_desc)} -> {len(desc)} chars)")
    if not changed:
        print("Network.eco Name + DetailedDescription unchanged")
        return
    NETWORK_CONFIG.write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print("updated Network.eco: " + ", ".join(changed))
    print(
        "commit + push eco-configs, then `inv eco.copy-configs --with-world-gen` "
        "on kai-server."
    )
