# eco-cycle-prep

End-to-end tooling for preparing a fresh cycle on my [Eco](https://play.eco/)
(Strange Loop Games) server, "Eco via Sirens". Map generation is one phase;
the rest covers source sync, community-intel aggregation from Discord,
config tuning, mod management, and the go-live announcements. Written as a
set of [Invoke](https://pyinvoke.org/) tasks in Python, with
`string.Template` markdown stubs for the two recurring announcement formats
(the cross-server ad on the main Eco Discord, and the longer post on the
Sirens `#eco-configs` channel).

The cycle workflow pulls the latest from sibling repos, regenerates a
Discord digest of recent community input, rolls candidate worldgen seeds
against [eco-configs](https://github.com/coilysiren/eco-configs)'
`WorldGenerator.eco`, syncs
[eco-mods](https://github.com/coilysiren/eco-mods) plus
[eco-mods-public](https://github.com/coilysiren/eco-mods-public) onto the
game server, waits for the preview render, and posts announcements.
Discord-side plumbing runs through
[eco-agent](https://github.com/coilysiren/eco-agent); channel IDs and
tokens are resolved from AWS SSM at runtime.

This repo is part of a small family of public tooling around
[Eco](https://play.eco/), a multiplayer survival and simulation game by
[Strange Loop Games](https://strangeloopgames.com/). The official modkit
lives at
[StrangeLoopGames/EcoModKit](https://github.com/StrangeLoopGames/EcoModKit),
modding docs are at [docs.play.eco](https://docs.play.eco/) and
[wiki.play.eco/en/Modding](https://wiki.play.eco/en/Modding), and
[Eco-DiscordLink/EcoDiscordPlugin](https://github.com/Eco-DiscordLink/EcoDiscordPlugin)
is the canonical in-game to Discord chat relay.

## About Eco

Eco is a multiplayer survival/simulation game by Strange Loop Games.
Players collaborate to build a civilization on a shared procedurally
generated planet and stop an incoming meteor, while an ecological
simulation tracks the damage their extraction, pollution, and land use do
to the biosphere. Kai's server, "Eco via Sirens", runs ~2-month cycles.

## Tasks

- `inv prep --cycle N` — weekly prep: steamcmd update, git pulls on
  eco-configs + infrastructure, Discord digest of recent community input.
- `inv brief --cycle N --days D` — cycle-13-style brief: full cycle-N
  channel history + last D days of suggestions + suggestions-forum.
- `inv forum-dump --days D` — standalone dump of the suggestions forum.
- `inv roll --cycle N [--seed S]` — roll a single worldgen seed end-to-end:
  set + push to eco-configs, sync configs + reset storage on kai-server,
  wait for the preview to stabilize (streams `journalctl -u eco-server`
  while it boots), post the preview GIF to the current cycle channel.
  One roll per invocation; invoke again to roll the next seed.
- `inv mods-sync` — clone eco-mods + eco-mods-public on kai-server and
  copy them into the Eco install. Lockdown-gated (Network.eco in git
  must carry the private/password-protected values).
- `inv mods-disable --names=A,B,C` — rm mod folders from the server
  (ephemeral; prefer deleting from the eco-mods source repo).
- `inv ad --cycle N --start-ts UNIX_TS` — emit the main Eco Discord ad
  and sync Network.eco's DetailedDescription.
- `inv eco-configs-post --cycle N` — emit the Sirens #eco-configs
  channel post (longer, mod.io links).
- `inv go-live` — cycle launch: `copy-configs` to kai-server, then edit
  `Network.eco` ON THE SERVER to set PublicServer=true + Password="",
  then restart. The git-tracked Network.eco always stays in its locked
  private state; going public is a runtime-only flip.

Templates for the two announcement formats live under
`eco_cycle_prep/templates/`. Server-specific branding (summary,
objective, location, code-mod descriptions) and per-cycle config
bullets live under `rolls/_prep/` (gitignored).

## Setup

```
uv sync
```

SSM parameters required (see `coilyco-ai/AGENTS.md` for the full
inventory): `/eco/server-id`, `/eco/discord-bot-token`,
`/discord/server-id`, `/discord/server-ad-invite`,
`/discord/channel/{cycle-current,eco-configs,suggestions,suggestions-forum}`,
`/modio/api-key`.
