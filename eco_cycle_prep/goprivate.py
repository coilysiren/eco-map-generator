"""`inv go-private` workflow: flip the Eco server back to private mid-cycle.

Inverse of `golive.py`. Use when you need to take the server offline from
the public master-server browser without shutting it down — e.g. an
incident on the server, a staff-only debug window, or the end of a cycle
before wipe.

Sequence:

  1. `safety.assert_network_locked_down()` — git's Network.eco must already
     carry the locked private values. If someone accidentally pushed a
     public Network.eco into git, we want to fail loudly BEFORE we sync
     anything to the server.
  2. `inv eco.copy-configs --with-world-gen` on the server — pulls git's
     (private) Network.eco onto disk. By itself this already privatizes
     the server on next restart.
  3. Re-assert the state with an explicit flip script. Belt-and-braces
     against copy-configs ever being refactored to skip Network.eco:
     we independently force PublicServer=false + Password back to the
     locked value.
  4. (Optional) SIGTERM the eco-server process so the flip takes effect.
     systemd's Restart=on-failure / RestartSec=60 policy brings the
     service back up automatically (same approach as `golive.py`).
"""

from invoke.context import Context

from . import remote, safety

FLIP_SCRIPT = f"""
import json
from pathlib import Path
p = Path("/home/kai/Steam/steamapps/common/EcoServer/Configs/Network.eco")
d = json.loads(p.read_text(encoding="utf-8"))
before = (d.get("PublicServer"), d.get("Password"))
d["PublicServer"] = {safety.LOCKED_PUBLIC_SERVER!r}
d["Password"] = {safety.LOCKED_PASSWORD!r}
p.write_text(json.dumps(d, indent=4), encoding="utf-8")
print(f"Network.eco flipped: PublicServer {{before[0]}} -> {safety.LOCKED_PUBLIC_SERVER!r}; "
      f"Password {{before[1]!r}} -> {safety.LOCKED_PASSWORD!r}")
"""


def run(ctx: Context, *, restart: bool = True) -> None:
    print("-- verifying eco-configs/Configs/Network.eco in git is locked private")
    safety.assert_network_locked_down()

    print("-- copying latest eco-configs onto kai-server (private Network.eco)")
    remote.copy_configs(ctx)

    print("-- re-asserting Network.eco on kai-server to private + locked password")
    remote.run_python(ctx, FLIP_SCRIPT)

    if restart:
        print("-- sigterm eco-server so the flip takes effect (systemd auto-restarts)")
        remote.sigterm_server(ctx)
    else:
        print("skipped restart (--no-restart); the flip takes effect on next restart")
