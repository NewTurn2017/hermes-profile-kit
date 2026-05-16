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
  --token SLACK_APP_TOKEN=<xapp-...>
hpk verify seb
```

Only 3 Slack tokens are required. Fastest path to get them: tell the
user to create the app from `profiles/seb/slack-app-manifest.json` at
<https://api.slack.com/apps> → Create New App → From an app manifest →
paste the JSON. That provisions all bot scopes, `app_mention` event,
Socket Mode, and interactivity in one step; the user then copies
`SLACK_BOT_TOKEN` (Install App), `SLACK_APP_TOKEN` (Basic Information →
App-Level Tokens → Generate with `connections:write`), and
`SLACK_SIGNING_SECRET` (Basic Information → App Credentials).

The model uses Hermes's native `openai-codex` provider — no proxy plugin,
no OpenAI API key. Prerequisite: the user has `codex auth login` done.
The `codex-openai-proxy` plugin is now opt-in (default `false`); do NOT
pass `--accept-plugin codex-openai-proxy` unless the user explicitly asks
for the local HTTP bridge.

## Fast-paths: other profiles

| Profile | Required tokens (ask user) | Optional tokens (offer to user) | Plugins to accept |
|---|---|---|---|
| `coder` | `ANTHROPIC_API_KEY` | — | — |
| `assistant` | `ANTHROPIC_API_KEY` | `TELEGRAM_BOT_TOKEN` | `honcho-memory` |
| `research` | `ANTHROPIC_API_KEY` | `BRAVE_SEARCH_API_KEY`, `EXA_API_KEY` | `honcho-memory`, `brave-search-tool` |
| `community-bot` | `ANTHROPIC_API_KEY` | `TELEGRAM_BOT_TOKEN`, `DISCORD_BOT_TOKEN` | — |
| `seb` | 3× `SLACK_*` (see fast-path above) | `OPENAI_BASE_URL`, `OPENAI_API_KEY`, `JINA_API_KEY` | — |

> `seb` no longer requires plugins by default — Hermes's built-in
> `openai-codex` provider handles gpt-5.5 directly via the local Codex
> CLI OAuth session. The `codex-openai-proxy` plugin is still in the
> manifest as opt-in (`default: false`); accept it only if the user
> explicitly wants a local HTTP bridge instead of the native path.

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
