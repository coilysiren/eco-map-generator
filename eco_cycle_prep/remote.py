"""SSH helpers for kai-server. Uses the user's configured ssh client; assumes keys."""

import contextlib
import subprocess
import sys
import threading
from collections.abc import Iterator

from invoke.context import Context

HOST = "kai@kai-server"
INFRA_DIR = "~/projects/infrastructure"
ECO_SERVER_DIR = "/home/kai/Steam/steamapps/common/EcoServer"
# Non-login ssh doesn't source ~/.bashrc, so pyenv shims aren't on PATH.
# The `inv` binary lives in ~/.pyenv/shims/inv on kai-server.
REMOTE_INV = "/home/kai/.pyenv/shims/inv"


def ssh(
    ctx: Context,
    remote_cmd: str,
    *,
    echo: bool = True,
    capture: bool = False,
    check: bool = True,
) -> subprocess.CompletedProcess:
    """Run a single command on kai-server via subprocess (avoids invoke's
    cmd.exe shell-quoting issues on Windows, which mangle single quotes and
    append stray apostrophes to the last token)."""
    if echo:
        print(f"$ ssh {HOST} {remote_cmd}")
    return subprocess.run(
        ["ssh", HOST, remote_cmd],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=capture,
        check=check,
    )


def run_python(
    ctx: Context,
    script: str,
    *,
    echo: bool = True,
) -> subprocess.CompletedProcess:
    """Pipe a Python script into `python3 -` on kai-server via ssh stdin.
    Avoids the quoting pain of embedding a multi-line script in an ssh
    command line."""
    if echo:
        first = next((ln for ln in script.strip().splitlines() if ln.strip()), "")
        print(f"$ ssh {HOST} python3 -  # {first}")
    return subprocess.run(
        ["ssh", HOST, "python3", "-"],
        input=script,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )


def steamcmd_update(ctx: Context):
    """Run the Eco server pre-start script (steamcmd install/update)."""
    ssh(ctx, "bash /home/kai/projects/infrastructure/scripts/eco-server-pre.sh")


def infra_pull(ctx: Context):
    ssh(ctx, f"cd {INFRA_DIR} && git pull --ff-only")


def copy_configs(ctx: Context):
    """Run `inv eco.copy-configs --with-world-gen` on kai-server."""
    ssh(ctx, f"cd {INFRA_DIR} && {REMOTE_INV} eco.copy-configs --with-world-gen")


def reset_world_storage(ctx: Context):
    """Delete Storage/Backup, Storage/Game.db, Storage/Game.eco, Logs/."""
    paths = [
        f"{ECO_SERVER_DIR}/Storage/Backup",
        f"{ECO_SERVER_DIR}/Storage/Game.db",
        f"{ECO_SERVER_DIR}/Storage/Game.eco",
        f"{ECO_SERVER_DIR}/Logs",
    ]
    ssh(ctx, "rm -rf " + " ".join(paths))


def server_is_active(ctx: Context) -> bool:
    r = ssh(ctx, "systemctl is-active eco-server || true", echo=False, capture=True)
    return (r.stdout or "").strip() == "active"


def server_is_activating(ctx: Context) -> bool:
    r = ssh(ctx, "systemctl is-active eco-server || true", echo=False, capture=True)
    return (r.stdout or "").strip() in {"activating", "reloading"}


def restart_server(ctx: Context):
    ssh(ctx, f"cd {INFRA_DIR} && {REMOTE_INV} eco.restart")


@contextlib.contextmanager
def stream_server_logs(prefix: str = "[eco] ") -> Iterator[None]:
    """Stream `journalctl -u eco-server -f` from kai-server to stdout for the
    duration of the `with` block. Lines are prefixed so they don't blend into
    local output. On exit, the remote follower is terminated.
    """
    cmd = [
        "ssh",
        "-o",
        "ServerAliveInterval=15",
        "-o",
        "ServerAliveCountMax=4",
        HOST,
        # -n 0: don't replay history, only new lines from now on
        "journalctl -u eco-server -f -n 0 --output=cat",
    ]
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    def _pump() -> None:
        assert proc.stdout is not None
        try:
            for line in proc.stdout:
                sys.stdout.write(prefix + line)
                sys.stdout.flush()
        except Exception:  # noqa: BLE001
            pass

    t = threading.Thread(target=_pump, daemon=True)
    t.start()
    try:
        yield
    finally:
        try:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=3)
        finally:
            t.join(timeout=2)
