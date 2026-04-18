"""`inv go-live` workflow: flip the Eco server public at launch.

Kai's rule: the git-tracked `eco-configs/Configs/Network.eco` is ALWAYS in
the private, password-protected state. Going public is a runtime edit
applied directly to the on-disk copy on kai-server. That way:

  - A careless `inv roll` or `inv mods-sync` during prep can never publish.
  - A later `inv eco.copy-configs` re-privatizes the server predictably
    (which is what you want if you need to quickly take the server down).

Sequence run by `run()`:

  1. `ssh kai-server` + `inv eco.copy-configs --with-world-gen` — pulls
     the final cycle configs from git onto the server. Network.eco at
     this step is the private version (by design).
  2. Remotely edit `Configs/Network.eco` on the server's disk to set
     PublicServer=true + Password="". Piped as a Python script over ssh
     stdin so quoting stays sane.
  3. (Optional) `inv eco.restart` so the public flip takes effect.
"""

from invoke.context import Context

from . import remote

FLIP_SCRIPT = r"""
import json, sys
from pathlib import Path
p = Path("/home/kai/Steam/steamapps/common/EcoServer/Configs/Network.eco")
d = json.loads(p.read_text(encoding="utf-8"))
before = (d.get("PublicServer"), d.get("Password"))
d["PublicServer"] = True
d["Password"] = ""
p.write_text(json.dumps(d, indent=4), encoding="utf-8")
print(f"Network.eco flipped: PublicServer {before[0]} -> True; Password {before[1]!r} -> ''")
"""


def run(ctx: Context, *, restart: bool = True) -> None:
    print("-- copying latest eco-configs onto kai-server")
    remote.copy_configs(ctx)

    print("-- flipping Network.eco on kai-server to public + empty password")
    remote.run_python(ctx, FLIP_SCRIPT)

    if restart:
        print("-- restarting eco-server so the flip takes effect")
        remote.restart_server(ctx)
    else:
        print("skipped restart (--no-restart); the flip takes effect on next restart")
