# eco-cycle-prep

End-to-end tooling for preparing a fresh cycle on Kai's Eco (Strange Loop
Games) server. Map generation is one phase; the rest covers source sync,
community-intel aggregation from Discord, config tuning, mod management,
and the go-live announcements.

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
- `inv roll --cycle N [--count N] [--seed S]` — roll a worldgen seed,
  sync configs to kai-server, wipe storage, wait for preview, post to
  the current cycle channel.
- `inv mods-sync` — clone eco-mods + eco-mods-public on kai-server and
  copy them into the Eco install.
- `inv mods-disable --names=A,B,C` — rm mod folders from the server
  (ephemeral; prefer deleting from the eco-mods source repo).
- `inv ad --cycle N --start-ts UNIX_TS` — emit the main Eco Discord ad
  and sync Network.eco's DetailedDescription.
- `inv eco-configs-post --cycle N` — emit the Sirens #eco-configs
  channel post (longer, mod.io links).

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
