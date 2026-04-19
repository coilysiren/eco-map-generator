## File Access

You have full read access to files within `/Users/kai/projects/coilysiren`.

## Autonomy

- Run tests after every change without asking.
- Fix lint errors automatically.
- If tests fail, debug and fix without asking.
- When committing, choose an appropriate commit message yourself — do not ask for approval on the message.
- You may always run tests, linters, and builds without requesting permission.
- Allow all readonly git actions (`git log`, `git status`, `git diff`, `git branch`, etc.) without asking.
- Allow `cd` into any `/Users/kai/projects/coilysiren` folder without asking.
- Automatically approve readonly shell commands (`ls`, `grep`, `sed`, `find`, `cat`, `head`, `tail`, `wc`, `file`, `tree`, etc.) without asking.
- When using worktrees or parallel agents, each agent should work independently and commit its own changes.
- Do not open pull requests unless explicitly asked.

## Git workflow

Commit directly to `main` without asking for confirmation, including `git add`. Do not open pull requests unless explicitly asked.

Commit whenever a unit of work feels sufficiently complete — after fixing a bug, adding a feature, passing tests, or reaching any other natural stopping point. Don't wait for the user to ask.

## Sibling Eco repos

This project depends heavily on the user's other Eco (Strange Loop Games) repos, which live as siblings under the same parent directory (`C:\projects\` on Windows, `/Users/kai/projects/coilysiren` on Mac). Read from them directly rather than asking the user for Eco domain details.

| Dir | Visibility | Purpose |
|---|---|---|
| `eco-agent` | public | Python/FastAPI service (Discord + OpenTelemetry + AWS SSM), deployed to eco.coilysiren.me. `src/{main,application,discord,model,telemetry}.py`. |
| `eco-mods` | private | Third-party mods installed on the user's private Eco server + configs. C# (.NET, `Eco.ReferenceAssemblies`). See its `AGENTS.md` for the sourcing table (mod.io / GitHub / Discord). |
| `eco-mods-public` | public | User's own C# mods (BunWulf family: Agricultural, Biochemical, Educational/Librarian, HardwareCo; plus DirectCarbonCapture, EcoNil, MinesQuarries, ShopBoat, WorldCounter). Code generation via `main.cs` + `tasks.py` + `templates/`. |
| `eco-configs` | private | Server config diffs: `Configs/*.eco` (live), `*.original.json`, `*.diff.json`. Includes `WorldGenerator.eco` — the canonical world-gen JSON shape (Voronoi modules, biomes, rivers, lakes, crater). Most relevant to this project. |
| `eco-mods-assets` | private | Unity project (AssetBundles, Assets, Builds, Packages, ProjectSettings). Produces asset bundles consumed by mods. |
| `eco-mods-assets-embeded` | private | Embedded Unity assets (Icons, Prefabs, Scenes). |
| `eco-GlobalPlanetaryDefense` | public | Standalone mod (Deepflame's GPD) overhauling laser/computer-lab endgame. |

Eco server install paths referenced across these repos:
- Windows: `C:\Program Files (x86)\Steam\steamapps\common\Eco\Eco_Data\Server\`
- Linux: `/home/kai/Steam/steamapps/common/EcoServer/` (also `.local/share/Steam/...`)
- Mac: `/Users/kai/Library/Application Support/Steam/steamapps/common/Eco/Eco.app/Contents/Server/`

Mod sourcing for `eco-mods`: `MODIO_API_KEY` env var; mod.io game ID is 6.

## Eco official docs and API

Reach for these before guessing at Eco types, config shapes, or modding conventions.

- **Wiki** — https://wiki.play.eco/en/ (start pages: `/en/Modding`, `/en/Mod_Development`, `/en/Ecopedia_Modding`).
- **ModKit docs (auto-generated, tracks latest Eco)** — https://docs.play.eco/. Split into:
  - Client API (Unity3D ModKit package)
  - Server API (server-side ModKit DLLs)
  - Remote API (web server, REST-style) — e.g. https://docs.play.eco/api/remote/web/ecogameapi.html
- **EcoModKit reference repo** — https://github.com/StrangeLoopGames/EcoModKit (example mods + the ModKit Unity package).
- **SLG blog on modding** — https://strangeloopgames.com/how-mods-work-in-eco/.
- **mod.io** — game ID `6`. REST API: `GET https://api.mod.io/v1/games/6/mods?api_key=$MODIO_API_KEY&_q=<search>`.

### DiscordLink

Bridges Eco server chat/state with Discord. Used by this project.

- Source: https://github.com/Eco-DiscordLink/EcoDiscordPlugin (org: https://github.com/Eco-DiscordLink)
- Releases: https://github.com/Eco-DiscordLink/EcoDiscordPlugin/releases
- mod.io: https://mod.io/g/eco/m/discordlink

## World generation reference

Two companion reference docs under `docs/`:

- [`docs/worldgen.md`](docs/worldgen.md) — the map-generation
  reference: `WorldGenerator.eco` config schema, the biome catalog
  with colors and block palettes, `WorldPreview.gif` format
  (single-frame 8-bit indexed; pixel size is `WorldWidth × 10`, so
  720×720 at Sirens' current 72-chunk sizing), sibling `/Layers/`
  GIFs, and what's inferable from config-only vs config+GIF.
- [`docs/biomes.md`](docs/biomes.md) — per-biome plants, animals,
  and minerals. Feeds `inv narrate` with the flavor color that lets
  a map description say "oak and elk on granite" instead of just
  "warm forest." Scope is vanilla Eco plus the Sirens mod stack.

Consult both before writing anything that reads world config, parses
the preview image, or attempts to narrate a map in prose.

## Third-party source code reference

The `../Eco/` sibling directory contains vendor-provided game source. Use it as read-only background for type signatures, API shapes, and reproducing vanilla formulas, but do not paste, quote, or link snippets of it in anything that leaves this repo: commit messages, PR descriptions, public READMEs, issues, Discord posts, or other published docs. Describe game behavior in your own words and use fresh examples rather than lifting source prose. The same rule applies to any voice guide or Discord draft: describe patterns and use fabricated examples, do not quote.

## Server communications (canonical)

This repo owns all manual Discord messaging to the Sirens Eco server. Sibling repos (eco-mods, eco-mods-public, eco-configs) point here rather than reimplementing locally. The Python helpers live in [`eco_cycle_prep/discord_post.py`](eco_cycle_prep/discord_post.py); the user-facing entry points are invoke tasks.

### Invoke tasks

```
inv discord-post --channel=<alias> --from-file=<path>     # send a plain-content message
inv discord-post --channel=<alias> --body="<inline body>"
inv restart-notice [--reason="<short reason>"]            # pre-restart heads-up embed to #eco-status
```

Known channel aliases live in `discord_post.CHANNEL_ALIASES`. Currently: `general-public`, `eco-status`. Add new aliases there, not at call sites.

Both tasks post through the `sirens-echo` bot (SSM `/sirens-echo/discord-bot-token`). The `eco-sirens` bot (`/eco/discord-bot-token`) belongs to DiscordLink and auto-posts `Server Started` / `Server Stopped` embeds plus the in-game chat bridge; it is intentionally never used for manual messaging, so that a message's bot author unambiguously signals whether it was automated or authored here.

### When to post to #general-public

Triggers specific to eco-cycle-prep:

- `inv go-live` / `inv go-private` (Network.eco flip, public/private + password state).
- `inv roll` / `inv post-roll` (new world seed, preview GIF, server restart).
- `inv mods-sync` (copies eco-mods and eco-mods-public onto the Eco install).
- `inv mods-disable --names=...` (removes mods from the server's UserCode).
- `inv ingame --sync` (writes in-game Name / DetailedDescription into Network.eco).
- Any direct ssh edit on kai-server to `/home/kai/Steam/steamapps/common/EcoServer/`.

A plain commit to `main` in this repo is not a deploy trigger by itself (tasks, helpers, and wording tweaks that never run against prod don't need a post). Post when the invoked task actually reaches the server, in the same turn as the deploy. Do not describe the post as a backfill, delayed notice, or after-the-fact summary. Write as if the change just landed.

### Voice and tone

Before drafting a patch-note body, read the private reference in [`../eco-voice/VOICE.md`](../eco-voice/VOICE.md). That repo stays private and is the working guide for how Sirens-facing messages should read. Treat its patterns as load-bearing: the voice is what keeps posts feeling like they belong on the server rather than like build-system output.

Quick-reference rules (full detail in the voice guide):

- Mechanical and specific. Numbers over adjectives. Name skills, tiers, recipes, and systems directly; assume the reader knows them.
- No marketing hype. No condescension. No exclamation points in body copy. No em-dashes (use periods, commas, parens, or " - " for mid-sentence sidebars).
- Describe the before / after on a fix. Describe the new capability on a feature.
- Under ~1500 characters so it fits in a single Discord message.
- Sign off with the repo + task or config touched in brackets, e.g. `[eco-cycle-prep / inv roll]`.

### Link back to the commit (public repos only)

When a patch note describes a change whose source is in a **public** sibling repo (currently only [`eco-mods-public`](https://github.com/coilysiren/eco-mods-public)), include a link to the relevant commit or compare view in the message body, above the sign-off. Format:

```
https://github.com/coilysiren/eco-mods-public/commit/<short-sha>
https://github.com/coilysiren/eco-mods-public/compare/<a>...<b>
```

Use the full URL so Discord renders a preview. If the change spans more than one public repo, include a link per repo. Private-repo changes (eco-mods, eco-configs, eco-cycle-prep itself) do not get a link.

### Server restart notice (#eco-status)

Before restarting the Eco server on kai-server, post a heads-up via `inv restart-notice`. The embed matches DiscordLink's existing `Server Started` / `Server Stopped` format (title-only, color `7506394`, two-space emoji spacing), so it slots visually into the auto-feed. Pass `--reason="<one-liner>"` when the restart has a specific cause worth surfacing; otherwise leave it title-only.

Post immediately before the restart command, not after. The feed order should read: our manual "restarting" embed, then DiscordLink's auto `Server Stopped`, then `Server Started`.
