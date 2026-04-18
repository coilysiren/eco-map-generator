"""Local-machine command helpers. Uses subprocess directly so we avoid
invoke's Windows cmd.exe shell-quoting issues (e.g. --ff-only getting a
stray apostrophe appended)."""

import subprocess
from pathlib import Path


def git(
    cwd: Path,
    *args: str,
    check: bool = True,
    capture: bool = False,
    echo: bool = True,
) -> subprocess.CompletedProcess:
    cmd = ["git", *args]
    if echo:
        print(f"$ git -C {cwd} {' '.join(args)}")
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        check=check,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=capture,
    )
