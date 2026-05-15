# hermes-profile-kit

Interactive multi-profile setup utility for [Hermes Agent](https://github.com/NousResearch/hermes-agent).

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![CI](https://github.com/NewTurn2017/hermes-profile-kit/actions/workflows/ci.yml/badge.svg)](https://github.com/NewTurn2017/hermes-profile-kit/actions/workflows/ci.yml)

## Quick start

```bash
pipx install hermes-profile-kit
hpk setup
```

The wizard walks you through 4 profiles (`coder` / `assistant` / `research` / `community-bot`), prompts for the right tokens per channel (Anthropic, Telegram, Slack, Discord, Brave, Exa), and optionally enables recommended plugins (Honcho memory, Brave search tool).

## What hpk does (and doesn't)

- ✅ Creates and configures four isolated Hermes profiles.
- ✅ Walks you through BotFather, Slack app, Discord devportal flows.
- ✅ Atomic, idempotent `.env` writes (chmod 600). Re-running is safe.
- ✅ Daily upstream-sync via GitHub Actions — kit stays current with Hermes changes.
- ❌ Does not install Hermes itself (see [Hermes installation](https://github.com/NousResearch/hermes-agent#installation)).
- ❌ Does not start gateway services automatically.
- ❌ Does not invoke any hermes command that isn't verified in upstream.

## How it stays correct

`hpk` never embeds a hermes command that hasn't been observed in the upstream argparse tree. CI AST-parses `hermes_cli/main.py` daily, regenerates `docs/commands.md` and `build/cmd_index.json`, and opens a PR when drift is detected.

## Profiles

| Profile | Role | Model tier | Channels |
|---|---|---|---|
| `coder` | Full-stack dev assistant | Sonnet | CLI |
| `assistant` | Personal daily assistant | Sonnet | CLI + Telegram |
| `research` | Web-search-backed research | Opus | CLI |
| `community-bot` | Korean dev community helper | Haiku | Telegram + Discord |

## Customization

| Goal | Edit |
|---|---|
| Change model | `~/.hermes/profiles/<name>/config.yaml` |
| Change persona | `~/.hermes/profiles/<name>/SOUL.md` |
| Add new profile | `profiles/<name>/{SOUL.md,config.yaml,.env.example}` + add to `manifest.yaml` → `hpk setup` |
| Enable a plugin | Add to `manifest.yaml` `plugins:` + reference from `recommended_plugins` |

API keys go in `~/.hermes/profiles/<name>/.env`. They're plain text with `chmod 600` — the kit deliberately does not pretend to encrypt them.

## Commands

```bash
hpk setup [profile...]    # interactive wizard
hpk verify                # doctor + FILL_IN scan
hpk doctor                # hpk's own health
hpk reset [profile...]    # remove kit-created profiles
hpk plugin list           # show recommended_plugins
hpk sync --dry-run        # local drift check
```

## License

MIT. See `LICENSE`.
