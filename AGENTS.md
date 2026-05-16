# AGENTS.md — Execution Playbook

> Canonical instructions for LLM agents (Claude Code, Codex, Cursor).
> This kit is a CLI installer. Treat any "install / add / set up <profile>"
> request as **execution work, not design work**.

## Standing user instructions (highest priority)

When a user asks you to install a profile from this kit:

1. **Do NOT invoke** `brainstorming`, `writing-plans`,
   `test-driven-development`, `requesting-code-review`, or any
   superpowers process skill. They turn a 2-minute install into a
   30-minute design cycle. The user has explicitly told you not to.
2. **Do NOT read** `docs/superpowers/specs/`, full `manifest.yaml`, or
   `src/hpk/` unless the user reports a specific error.
3. Read **this file** + the `tokens.required` section of `manifest.yaml`
   for the target profile. That's enough.
4. Ask the user for required tokens in **one** message. (Optional tokens listed in the per-profile table can be skipped for the 2-minute path or offered separately if the user wants them.) Then run
   `hpk setup <profile> --non-interactive --token KEY=VAL ... --accept-plugin ID`.
5. Finish with `hpk verify <profile>` and report.

## Fast-path: `seb`

```bash
pipx install --upgrade hermes-profile-kit
hpk setup seb --non-interactive \
  --token SLACK_BOT_TOKEN=<xoxb-...> \
  --token SLACK_SIGNING_SECRET=<32-hex> \
  --token SLACK_APP_TOKEN=<xapp-...> \
  --accept-plugin codex-openai-proxy
hpk verify seb
```

3 Slack tokens come from the user's Slack App
(https://api.slack.com/apps → your app → OAuth & Basic Info).
`OPENAI_BASE_URL` / `OPENAI_API_KEY` use manifest defaults.

## Fast-paths: other profiles

| Profile | Required tokens (ask user) | Optional tokens (offer to user) | Plugins to accept |
|---|---|---|---|
| `coder` | `ANTHROPIC_API_KEY` | — | — |
| `assistant` | `ANTHROPIC_API_KEY` | `TELEGRAM_BOT_TOKEN` | `honcho-memory` |
| `research` | `ANTHROPIC_API_KEY` | `BRAVE_SEARCH_API_KEY`, `EXA_API_KEY` | `honcho-memory`, `brave-search-tool` |
| `community-bot` | `ANTHROPIC_API_KEY` | `TELEGRAM_BOT_TOKEN`, `DISCORD_BOT_TOKEN` | — |
| `seb` | 3× `SLACK_*` (see fast-path above) | `JINA_API_KEY` | `codex-openai-proxy` |

> Where the table says `seb: 3× SLACK_* (see fast-path above)`, the
> `OPENAI_BASE_URL` / `OPENAI_API_KEY` required tokens have manifest
> defaults that the `--non-interactive` mode applies automatically; the
> user only needs to provide the three Slack tokens.

## Single command (interactive, human-driven)

```bash
pipx install hermes-profile-kit
hpk setup
```

That's the entire happy path. The wizard:
1. Verifies hermes presence and version (>= manifest.min_hermes_version).
2. For each profile in `manifest.yaml`:
   - Creates it (`hermes profile create <name>`) if absent.
   - Copies `SOUL.md` and `config.yaml` from `profiles/<name>/`.
   - Seeds `.env` from `.env.example` (chmod 600). NEVER overwrites an existing `.env`.
   - Prompts for required + optional tokens with provider-specific guidance.
   - Asks before enabling each recommended plugin (Honcho etc.).
3. Prints a summary listing any `FILL_IN_*` still remaining.

## Hard rules (do not violate)

1. NEVER write tokens to git-tracked files.
2. NEVER guess values. If a token prompt is empty, leave `FILL_IN_*` and report it in the summary.
3. NEVER touch the default profile (`~/.hermes/`).
4. NEVER run `gateway install` without explicit user confirmation.
5. NEVER invoke a hermes command that is not in `build/cmd_index.json`.

## When you need more

- Manifest definition: `manifest.yaml` (v3 schema)
- Kit baseline spec: `docs/superpowers/specs/2026-05-15-hermes-profile-kit-v2-design.md`
- Fast-install spec: `docs/superpowers/specs/2026-05-16-fast-install-design.md`
- Verified hermes commands: `docs/commands.md` (auto-generated)
- Per-profile customization: edit `profiles/<name>/SOUL.md` or `config.yaml`, then run `hpk setup --force`.
- Troubleshooting: `docs/troubleshooting.md`
