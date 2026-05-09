# AGENTS.md — Execution Playbook

> This file is the canonical entry point for any LLM agent (Hermes Agent, Claude Code, Cursor, OpenCode, etc.) reading this repository. Follow it top-to-bottom.

## Goal

Set up 4 isolated Hermes Agent profiles on the current machine, each with its own config, memory, gateway tokens, and persona:

| Profile | Purpose | Model preset | Channels |
|---------|---------|--------------|----------|
| `coder` | Full-stack development assistant | Sonnet-class | CLI only |
| `assistant` | Personal daily assistant | Sonnet-class | Telegram |
| `research` | Deep research with web search | Opus-class | CLI only |
| `community-bot` | Korean dev community helper | Haiku-class (cheap) | Telegram + Discord |

Profiles are independent: separate API keys, separate memory, separate sessions, separate gateway processes. See `docs/concepts.md` for the isolation model.

## Hard rules (do not violate)

1. **Never write secrets to git-tracked files.** Only edit `.env` files inside `~/.hermes/profiles/<name>/`. The `.env.example` files in this repo must stay placeholder-only.
2. **Always run `hermes profile show <name>`** before assuming a profile exists. Do not guess state.
3. **Never delete the default profile (`~/.hermes`).** Only profiles created by this kit can be reset via `scripts/reset.sh`.
4. **Ask the user** before running `gateway install` (registers a systemd/launchd service) or before starting any gateway that connects to a real messaging platform.
5. **Treat `manifest.yaml` as the source of truth** for which profiles to create and what each one's role is. If you read this AGENTS.md but the manifest disagrees, the manifest wins.

## Preconditions

Run these checks first. If any fails, stop and report to the user.

```bash
# 1. Hermes is installed and on PATH
command -v hermes >/dev/null || { echo "hermes not found"; exit 1; }

# 2. Hermes can self-check
hermes doctor

# 3. ~/.local/bin is on PATH (profile aliases live there)
echo "$PATH" | tr ':' '\n' | grep -q "$HOME/.local/bin" || \
  echo "WARNING: ~/.local/bin not in PATH — aliases like 'coder chat' won't work"

# 4. Repo files are intact
test -f manifest.yaml && test -d profiles || { echo "repo incomplete"; exit 1; }
```

## Steps

### Step 1 — Read the manifest

```bash
cat manifest.yaml
```

This lists the profiles to create with their template paths. Do not hardcode profile names; iterate over `profiles[]` from the manifest.

### Step 2 — For each profile in manifest, create it

For every entry under `profiles[]`:

```bash
PROFILE_NAME="<from manifest .name>"
TEMPLATE_DIR="<from manifest .template>"   # e.g. profiles/coder

# 2a. Skip if it already exists
if hermes profile show "$PROFILE_NAME" >/dev/null 2>&1; then
  echo "Profile '$PROFILE_NAME' already exists — skipping create"
else
  hermes profile create "$PROFILE_NAME"
fi

# 2b. Resolve the profile home
PROFILE_HOME="$HOME/.hermes/profiles/$PROFILE_NAME"
test -d "$PROFILE_HOME" || { echo "create failed for $PROFILE_NAME"; exit 1; }

# 2c. Apply templates (overwrite SOUL.md and config.yaml; never overwrite .env)
cp "$TEMPLATE_DIR/SOUL.md"          "$PROFILE_HOME/SOUL.md"
cp "$TEMPLATE_DIR/config.yaml"      "$PROFILE_HOME/config.yaml"

# 2d. Seed .env only if it does not already exist (preserves user secrets)
if [ ! -f "$PROFILE_HOME/.env" ]; then
  cp "$TEMPLATE_DIR/.env.example" "$PROFILE_HOME/.env"
  chmod 600 "$PROFILE_HOME/.env"
  echo "  -> seeded .env from .env.example. User must fill in keys."
fi
```

Verify after each profile:

```bash
hermes profile show "$PROFILE_NAME"
# Expected: shows home dir, model, gateway status (off), skills count
```

### Step 3 — Tell the user which secrets to fill

For every profile created, print the path to its `.env` and list the `<FILL_IN>` placeholders that the user must replace:

```bash
for env_file in "$HOME/.hermes/profiles/"*/.env; do
  if grep -q "FILL_IN" "$env_file"; then
    echo "EDIT REQUIRED: $env_file"
    grep -n "FILL_IN" "$env_file"
  fi
done
```

Do not attempt to fill these yourself. Do not guess from context. Stop and tell the user.

### Step 4 — Verify with hermes doctor per profile

After the user has filled secrets:

```bash
for p in coder assistant research community-bot; do
  echo "=== $p ==="
  hermes -p "$p" doctor
done
```

A profile passes if `hermes doctor` exits 0 and no `MISSING` lines for the providers listed in that profile's `config.yaml`.

### Step 5 — Optional: install gateway services

Only if the user explicitly confirms. Each profile that has channel tokens in its `.env` can run as a background service:

```bash
# Per profile (only after user confirms)
<profile-name> gateway install   # creates hermes-gateway-<profile-name> service
```

Do NOT run `gateway install` automatically. Always ask.

## Profile customization rules

When the user asks to change a profile's behavior:

| Request | What to edit |
|---------|--------------|
| "Change model" | `~/.hermes/profiles/<name>/config.yaml` → `model.default` |
| "Change personality / tone" | `~/.hermes/profiles/<name>/SOUL.md` |
| "Add a Telegram bot" | `~/.hermes/profiles/<name>/.env` → set `TELEGRAM_BOT_TOKEN` |
| "Add a working directory" | `config.yaml` → `terminal.cwd: /absolute/path` |
| "Add an API key" | `.env`, never `config.yaml` |

## Common errors and fixes

| Error | Cause | Fix |
|-------|-------|-----|
| `command not found: coder` | Alias not on PATH | Add `export PATH="$HOME/.local/bin:$PATH"` to shell rc |
| `gateway: token already in use by profile X` | Same bot token in two `.env` files | Edit the conflicting `.env` |
| `model not found` after edit | Provider not configured | `hermes -p <name> model` (interactive picker) |
| `permission denied` on `.env` | Wrong mode | `chmod 600 ~/.hermes/profiles/<name>/.env` |
| Profile created but empty | `--clone` was used without an existing profile to clone from | Recreate without `--clone` |

## What this kit does NOT do

- Does not install Hermes Agent itself. Run `curl -fsSL https://raw.githubusercontent.com/nousresearch/hermes-agent/main/scripts/install.sh | bash` separately.
- Does not configure provider credentials beyond placeholder names. The user fills `.env`.
- Does not start any gateway process. The user runs `<profile> gateway start` when ready.
- Does not modify the default profile (`~/.hermes/`).
- Does not sandbox profiles. Profiles share filesystem permissions with the user. See `docs/concepts.md` §isolation-limits.

## When you are done

Print a summary in this exact format:

```
Created profiles: <comma-separated names>
Skipped (already existed): <comma-separated names>
Required user actions:
  - Fill <profile>.env keys: <list>
  - <other actions>
Next commands the user can run:
  - <profile> chat                     # start chatting
  - hermes -p <profile> doctor         # health check
  - <profile> gateway start            # launch messaging gateway (if tokens set)
```

## Reference

- Repository structure: see `manifest.yaml`
- Concepts (isolation model, what's shared vs scoped): `docs/concepts.md`
- Command cheatsheet: `docs/commands.md`
- Gateway / multi-channel patterns: `docs/gateways.md`
- Troubleshooting: `docs/troubleshooting.md`
- Hermes upstream docs: https://hermes-agent.nousresearch.com/docs/user-guide/profiles
