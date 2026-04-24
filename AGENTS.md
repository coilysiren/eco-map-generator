# Agent instructions

See `../AGENTS.md` for workspace-level conventions (git workflow, test/lint autonomy, readonly ops, writing voice, deploy knowledge). This file covers only what's specific to this repo.

---

## Local Eco server config mutations are expected

`server_local.prep_for_local` (invoked by `coily server-run`) intentionally rewrites `Configs/Network.eco`, `Configs/DiscordLink.eco`, `Configs/Difficulty.eco`, and creates `Configs/Sleep.eco` in the Steam-installed Eco server dir. That's the whole point of the task - it's putting the local server into private-local-dev shape. Do not flag these mutations as surprising or as cleanup candidates after running that verb. Resync from `eco-configs` only when Kai explicitly asks.

---

## Sibling Eco repos

This project depends heavily on the user's other Eco (Strange Loop Games) repos, which live as siblings under the same parent directory (`C:\projects\` on Windows, `/Users/kai/projects/coilysiren` on Mac). Read from them directly rather than asking the user for Eco domain details.

| Dir | Visibility | Purpose |
|---|---|---|
| `eco-agent` | public | Python/FastAPI service (Discord + OpenTelemetry + AWS SSM), deployed to eco.coilysiren.me. `src/{main,application,discord,model,telemetry}.py`. |
| `eco-mods` | private | Third-party mods installed on the user's private Eco server + configs. C# (.NET, `Eco.ReferenceAssemblies`). See its `AGENTS.md` for the sourcing table (mod.io / GitHub / Discord). |
| `eco-mods-public` | public | User's own C# mods (BunWulf family: Agricultural, Biochemical, Educational/Librarian, HardwareCo; plus DirectCarbonCapture, EcoNil, MinesQuarries, ShopBoat, WorldCounter). Code generation via `main.cs` + `tasks.py` + `templates/`. |
| `eco-configs` | private | Server config diffs: `Configs/*.eco` (live), `*.original.json`, `*.diff.json`. Includes `WorldGenerator.eco` - the canonical world-gen JSON shape (Voronoi modules, biomes, rivers, lakes, crater). Most relevant to this project. |
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

- **Wiki** - https://wiki.play.eco/en/ (start pages: `/en/Modding`, `/en/Mod_Development`, `/en/Ecopedia_Modding`).
- **ModKit docs (auto-generated, tracks latest Eco)** - https://docs.play.eco/. Split into:
  - Client API (Unity3D ModKit package)
  - Server API (server-side ModKit DLLs)
  - Remote API (web server, REST-style) - e.g. https://docs.play.eco/api/remote/web/ecogameapi.html
- **EcoModKit reference repo** - https://github.com/StrangeLoopGames/EcoModKit (example mods + the ModKit Unity package).
- **SLG blog on modding** - https://strangeloopgames.com/how-mods-work-in-eco/.
- **mod.io** - game ID `6`. REST API: `GET https://api.mod.io/v1/games/6/mods?api_key=$MODIO_API_KEY&_q=<search>`.

### DiscordLink

Bridges Eco server chat/state with Discord. Used by this project.

- Source: https://github.com/Eco-DiscordLink/EcoDiscordPlugin (org: https://github.com/Eco-DiscordLink)
- Releases: https://github.com/Eco-DiscordLink/EcoDiscordPlugin/releases
- mod.io: https://mod.io/g/eco/m/discordlink

## World generation reference

Two companion reference docs under `docs/`:

- [`docs/worldgen.md`](docs/worldgen.md) - the map-generation
  reference: `WorldGenerator.eco` config schema, the biome catalog
  with colors and block palettes, `WorldPreview.gif` format
  (single-frame 8-bit indexed; pixel size is `WorldWidth × 10`, so
  720×720 at Sirens' current 72-chunk sizing), sibling `/Layers/`
  GIFs, and what's inferable from config-only vs config+GIF.
- [`docs/biomes.md`](docs/biomes.md) - per-biome plants, animals,
  and minerals. Feeds `coily narrate` with the flavor color that lets
  a map description say "oak and elk on granite" instead of just
  "warm forest." Scope is vanilla Eco plus the Sirens mod stack.

Consult both before writing anything that reads world config, parses
the preview image, or attempts to narrate a map in prose.

## Third-party source code reference

The `../Eco/` sibling directory contains vendor-provided game source. Use it as read-only background for type signatures, API shapes, and reproducing vanilla formulas, but do not paste, quote, or link snippets of it in anything that leaves this repo: commit messages, PR descriptions, public READMEs, issues, Discord posts, or other published docs. Describe game behavior in your own words and use fresh examples rather than lifting source prose. The same rule applies to any voice guide or Discord draft: describe patterns and use fabricated examples, do not quote.

## Dev entry point: coily

`coily` (sibling repo, `../coily`) is the canonical entry point for every dev verb in this repo. The invoke tasks in `tasks.py` are the implementation; operators (human or agent) type `coily <verb>`, not `inv <task>`. The mapping is 1:1 and declared in [`.coily/coily.yaml`](.coily/coily.yaml).

Running `coily --list` from anywhere inside this checkout shows all available verbs with descriptions. Flags forward verbatim, e.g. `coily prep --cycle=13`. Shell metacharacters are rejected at the coily boundary before they reach invoke.

The pyinvoke tasks still exist and still work (`uv run inv <task>`), but prose in this repo and in drafted messages references the coily form. The only reason to invoke `inv` directly is when coily itself is unavailable (e.g. on a host where it isn't installed).

## Server communications (canonical)

This repo owns all manual Discord messaging to the Sirens Eco server. Sibling repos (eco-mods, eco-mods-public, eco-configs) point here rather than reimplementing locally. The Python helpers live in [`eco_cycle_prep/discord_post.py`](eco_cycle_prep/discord_post.py); the user-facing entry points are coily verbs.

### Commands

```
coily discord-post --channel=<alias> --from-file=<path>     # send a plain-content message
coily discord-post --channel=<alias> --body="<inline body>"
coily restart-notice [--reason="<short reason>"]            # pre-restart heads-up embed to #eco-status
```

Known channel aliases live in `discord_post.CHANNEL_ALIASES`. Currently: `general-public`, `eco-status`. Add new aliases there, not at call sites.

Both verbs post through the `sirens-echo` bot (SSM `/sirens-echo/discord-bot-token`). The `eco-sirens` bot (`/eco/discord-bot-token`) belongs to DiscordLink and auto-posts `Server Started` / `Server Stopped` embeds plus the in-game chat bridge; it is intentionally never used for manual messaging, so that a message's bot author unambiguously signals whether it was automated or authored here.

### When to post to #general-public

Triggers specific to eco-cycle-prep:

- `coily go-live` / `coily go-private` (Network.eco flip, public/private + password state).
- `coily roll` / `coily post-roll` (new world seed, preview GIF, server restart).
- `coily mods-sync` (copies eco-mods and eco-mods-public onto the Eco install).
- `coily mods-disable --names=...` (removes mods from the server's UserCode).
- `coily ingame --sync` (writes in-game Name / DetailedDescription into Network.eco).
- Any direct ssh edit on kai-server to `/home/kai/Steam/steamapps/common/EcoServer/`.

A plain commit to `main` in this repo is not a deploy trigger by itself (tasks, helpers, and wording tweaks that never run against prod don't need a post). Post when the invoked task actually reaches the server, in the same turn as the deploy. Do not describe the post as a backfill, delayed notice, or after-the-fact summary. Write as if the change just landed.

### Voice and tone

Before drafting a patch-note body, read the private reference in [`../eco-voice/VOICE.md`](../eco-voice/VOICE.md). That repo stays private and is the working guide for how Sirens-facing messages should read. Treat its patterns as load-bearing: the voice is what keeps posts feeling like they belong on the server rather than like build-system output.

Quick-reference rules (full detail in the voice guide):

- Mechanical and specific. Numbers over adjectives. Name skills, tiers, recipes, and systems directly; assume the reader knows them.
- No marketing hype. No condescension. No exclamation points in body copy. No em-dashes (use periods, commas, parens, or " - " for mid-sentence sidebars).
- Describe the before / after on a fix. Describe the new capability on a feature.
- Under ~1500 characters so it fits in a single Discord message.
- Sign off with the repo + verb or config touched in brackets, e.g. `[eco-cycle-prep / coily roll]`.

### Restart-schedule footer (changes that need a restart)

The Sirens server restarts automatically at 08:00 America/Los_Angeles. Any patch note describing a change that needs a restart to take effect (nearly all mod-code and most config changes) ends with a footer line naming that restart time in Discord's native timestamp syntax, so every reader sees it rendered in their own locale. Use the helper:

```py
from eco_cycle_prep.discord_post import restart_schedule_footer
print(restart_schedule_footer())
# "These changes will go live at 8am PT (<t:TS:F>, <t:TS:R>) unless players request an earlier restart."
```

`restart_schedule_footer()` defaults to the next 08:00 PT and handles DST via `zoneinfo`. Pass an explicit `unix_ts` if the restart is scheduled outside the default cadence. The footer is a single paragraph, placed above the `[repo / component]` sign-off.

Changes that take effect immediately without a restart (invoke-only tooling, docs, config that's hot-reloaded) do not get the footer; the footer exists to set expectations for "why can I still see the old behavior?"

### Link back to the commit (public repos only)

When a patch note describes a change whose source is in a **public** sibling repo (currently only [`eco-mods-public`](https://github.com/coilysiren/eco-mods-public)), include a link to the relevant commit or compare view in the message body, above the sign-off. Format:

```
https://github.com/coilysiren/eco-mods-public/commit/<short-sha>
https://github.com/coilysiren/eco-mods-public/compare/<a>...<b>
```

Use the full URL so Discord renders a preview. If the change spans more than one public repo, include a link per repo. Private-repo changes (eco-mods, eco-configs, eco-cycle-prep itself) do not get a link.

### Server restart notice (#eco-status)

Before restarting the Eco server on kai-server, post a heads-up via `coily restart-notice`. The embed matches DiscordLink's existing `Server Started` / `Server Stopped` format (title-only, color `7506394`, two-space emoji spacing), so it slots visually into the auto-feed. Pass `--reason="<one-liner>"` when the restart has a specific cause worth surfacing; otherwise leave it title-only.

Post immediately before the restart command, not after. The feed order should read: our manual "restarting" embed, then DiscordLink's auto `Server Stopped`, then `Server Started`.

### Ops-command trace (#eco-status)

Any invoke task in this repo that modifies real server state (mutates `/home/kai/Steam/steamapps/common/EcoServer/`, edits `Network.eco` on disk, issues an Eco restart, pushes new mod or config bits to kai-server, or similar) must post the literal text of the invoke command to `#eco-status` **before** running its side-effects. This is the audit trail: the channel log should show "here's what was about to run" in chronological order alongside DiscordLink's auto Server Started / Stopped embeds, so after-the-fact debugging has a single timeline to follow.

**How to post it.** Call `eco_cycle_prep.discord_post.ops_notice(command_text)` as the first line of the task's body (or via the `coily ops-notice --command="..."` verb for manual use). The helper builds a title-only embed that mirrors the DiscordLink format exactly:

- Title is the command text with two spaces before a trailing emoji shortcode (`:arrow_forward:`).
- Color is `7506394` (same as the Start / Stop embeds), so ops posts sit visually in the same family.
- No description, no fields. The command is the whole message.

**Format the command text naturally.** Include the subcommand, any flags worth seeing, and any values that give useful context ("`--cycle=13`", "`--mod=SkillsRequirements`"). Drop flags whose value is irrelevant for reading ("`--restart=True`" is noise if it's the default).

**Redact sensitive data at the call site.** The helper posts the string verbatim. If a task's invocation includes a secret (a password, an SSM value pulled into the command line, a token), the caller replaces it with `***` in the string passed to `ops_notice`. Examples:

- `coily go-live --restart=true` — fine as-is.
- `coily mods-sync` — fine as-is.
- `coily some-future-verb --token=***` — not `--token=<actual secret>`.

**Rule for newly added ops commands.** Any task added to `tasks.py` that changes real server state ships with an `ops_notice(...)` call as its first concrete step, and gets a matching entry in `.coily/coily.yaml` so it's reachable as a `coily <verb>`. Both are hard requirements, not conventions: a new ops task without an `ops_notice` or without a coily passthrough is a bug to fix before merging. Reading the channel back should show every ops action that hit the server.

**Existing commands.** Not retroactively required. Backfill as you touch them; don't block other work to sweep the whole file.
