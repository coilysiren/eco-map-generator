"""Local Eco server management. Ported (copied) from
coilysiren/infrastructure/src/eco.py so the same host that preps a cycle
can also spin up the Eco server locally to test mods, configs, and world
gen without involving kai-server.

Pairs with ``remote.py`` (kai-server ops) and is intentionally Windows +
macOS first; Linux paths mirror the infrastructure version for parity
while the migration is in flight.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import sys
from pathlib import Path

from . import ssm

PUBLIC_MODS_SIBLING = Path("..") / "eco-mods-public"
PRIVATE_MODS_SIBLING = Path("..") / "eco-mods"
CONFIGS_SIBLING = Path("..") / "eco-configs"

WINDOWS_SERVER_PATH = Path(
    r"C:\Program Files (x86)\Steam\steamapps\common\Eco\Eco_Data\Server"
)
MACOS_SERVER_PATH = Path.home() / (
    "Library/Application Support/Steam/steamapps/common/Eco/Eco.app/Contents/Server"
)
LINUX_SERVER_PATH = Path.home() / "Steam/steamapps/common/EcoServer"


def server_path() -> Path:
    if sys.platform.startswith("win"):
        return WINDOWS_SERVER_PATH
    if sys.platform == "darwin":
        return MACOS_SERVER_PATH
    return LINUX_SERVER_PATH


def eco_binary() -> str:
    if sys.platform.startswith("win"):
        return "EcoServer.exe"
    return "./EcoServer"


def _get_api_key() -> str:
    return ssm.get("/eco/server-api-token").strip()


def _handle_remove_readonly(func, path, _):
    if not os.access(path, os.W_OK):
        os.chmod(path, stat.S_IWUSR)
        func(path)
    else:
        raise OSError(f"could not remove {path}")


def _rmtree(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path, onerror=_handle_remove_readonly)


def _copy_tree(origin: Path, target: Path) -> None:
    if not origin.is_dir():
        return
    if target.exists() and "BunWulfEducational" not in str(origin):
        print(f"\tRemoving {target}")
        _rmtree(target)
    print(f"\tCopying {origin} -> {target}")
    shutil.copytree(origin, target, dirs_exist_ok=True)


def copy_configs_from_sibling(sibling: Path = CONFIGS_SIBLING) -> None:
    """Copy Configs/ from the eco-configs sibling repo into the local server."""
    src = sibling / "Configs"
    if not src.is_dir():
        raise FileNotFoundError(f"{src} does not exist; is {sibling} cloned?")
    dst = server_path() / "Configs"
    dst.mkdir(parents=True, exist_ok=True)
    for config in src.iterdir():
        target = dst / config.name
        if target.exists():
            target.unlink()
        print(f"\tCopying {config} -> {target}")
        shutil.copyfile(config, target)


def copy_mods_from_sibling(sibling: Path) -> None:
    """Copy one of eco-mods or eco-mods-public into the local server's Mods/.
    Mirrors infrastructure/src/eco.py:_copy_mods."""
    mods_root = sibling / "Mods"
    if not mods_root.is_dir():
        raise FileNotFoundError(f"{mods_root} does not exist")
    for mod in mods_root.iterdir():
        if mod.name == "UserCode":
            continue
        _copy_tree(mod, server_path() / "Mods" / mod.name)
    user_code = mods_root / "UserCode"
    if user_code.is_dir():
        for mod in user_code.iterdir():
            _copy_tree(mod, server_path() / "Mods" / "UserCode" / mod.name)
    configs_dir = sibling / "Configs"
    if configs_dir.is_dir():
        print(f"Copying mod configs from {configs_dir}")
        shutil.copytree(configs_dir, server_path() / "Configs", dirs_exist_ok=True)


def deploy_mod_dll(dll_path: Path, mod_name: str | None = None) -> Path:
    """Drop a pre-built mod DLL into Server/Mods/<mod_name>/. Returns the
    deployed path. Used by eco-spec-tracker (and future prebuilt mods)."""
    dll_path = Path(dll_path).resolve()
    if not dll_path.is_file():
        raise FileNotFoundError(dll_path)
    name = mod_name or dll_path.stem
    dest_dir = server_path() / "Mods" / name
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / dll_path.name
    shutil.copyfile(dll_path, dest)
    print(f"Deployed {dll_path} -> {dest}")
    return dest


def prep_for_local(offline: bool = False) -> None:
    """Rewrite Configs/*.eco for private-local dev. Mirrors the infra `run`
    task's pre-launch config mutation, with the Difficulty-to-Network bug
    fixed."""
    configs = server_path() / "Configs"

    network_path = configs / "Network.eco"
    with network_path.open("r", encoding="utf-8") as f:
        network = json.load(f)
    network["PublicServer"] = False
    network["Name"] = "localhost"
    network["IPAddress"] = "Any"
    network["RemoteAddress"] = "localhost:3000"
    network["WebServerUrl"] = "http://localhost:3001"
    with network_path.open("w", encoding="utf-8") as f:
        json.dump(network, f, indent=4)
    print(f"Rewrote {network_path} for private-local dev")

    discord_path = configs / "DiscordLink.eco"
    if discord_path.exists():
        with discord_path.open("r", encoding="utf-8") as f:
            discord = json.load(f)
        discord["BotToken"] = ""
        with discord_path.open("w", encoding="utf-8") as f:
            json.dump(discord, f, indent=4)
        print(f"Cleared BotToken in {discord_path}")

    difficulty_path = configs / "Difficulty.eco"
    with difficulty_path.open("r", encoding="utf-8") as f:
        difficulty = json.load(f)
    difficulty["GameSettings"]["GameSpeed"] = "VeryFast"
    with difficulty_path.open("w", encoding="utf-8") as f:
        json.dump(difficulty, f, indent=4)
    print(f"Set {difficulty_path} GameSpeed=VeryFast")

    sleep_path = configs / "Sleep.eco"
    with sleep_path.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "AllowFastForward": True,
                "SleepTimePassMultiplier": 1000,
                "TimeToReachMaximumTimeRate": 5,
            },
            f,
            indent=4,
        )
    print(f"Wrote {sleep_path}")


def launch(offline: bool = False) -> None:
    """Launch the local EcoServer executable. Replaces the current process so
    Ctrl+C goes to Eco, not invoke."""
    token_arg: list[str] = []
    if not offline:
        token_arg = [f"-userToken={_get_api_key()}"]
    cwd = server_path()
    binary = cwd / eco_binary() if sys.platform.startswith("win") else eco_binary()
    print(f"Launching {binary} (cwd={cwd})")
    os.chdir(cwd)
    os.execv(str(binary), [str(binary), *token_arg])


def regen_same_world() -> None:
    """Wipe Storage + Logs; leave WorldGenerator + Difficulty as-is."""
    _rmtree(server_path() / "Storage")
    _rmtree(server_path() / "Logs")
    difficulty_path = server_path() / "Configs" / "Difficulty.eco"
    with difficulty_path.open("r", encoding="utf-8") as f:
        difficulty = json.load(f)
    difficulty["GameSettings"]["GenerateRandomWorld"] = False
    with difficulty_path.open("w", encoding="utf-8") as f:
        json.dump(difficulty, f, indent=4)


def regen_new_world(seed: int = 0) -> None:
    """Wipe Storage + Logs; force a fresh random world with the given seed."""
    _rmtree(server_path() / "Storage")
    _rmtree(server_path() / "Logs")
    worldgen_path = server_path() / "Configs" / "WorldGenerator.eco"
    with worldgen_path.open("r", encoding="utf-8") as f:
        worldgen = json.load(f)
    worldgen["HeightmapModule"]["Source"]["Config"]["Seed"] = seed
    with worldgen_path.open("w", encoding="utf-8") as f:
        json.dump(worldgen, f, indent=4)
    difficulty_path = server_path() / "Configs" / "Difficulty.eco"
    with difficulty_path.open("r", encoding="utf-8") as f:
        difficulty = json.load(f)
    difficulty["GameSettings"]["GenerateRandomWorld"] = True
    with difficulty_path.open("w", encoding="utf-8") as f:
        json.dump(difficulty, f, indent=4)
