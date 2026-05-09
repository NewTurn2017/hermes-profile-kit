# Troubleshooting

## First-aid commands

```bash
hermes doctor                       # global checks (no profile required)
hermes -p <profile> doctor          # per-profile checks
hermes dump                         # full snapshot for issue reports
hermes logs --profile <profile>     # tail profile logs
./scripts/verify.sh                 # this kit's full check
```

## By symptom

### `command not found: coder` (or any profile alias)

Cause: `~/.local/bin` is not on your `PATH`.

Fix:
```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc   # or ~/.bashrc
source ~/.zshrc
```

Verify:
```bash
ls -la ~/.local/bin/coder    # should be a symlink/wrapper
which coder                  # should resolve
```

If the wrapper is missing entirely:
```bash
hermes profile alias coder
```

### `hermes: command not found`

Hermes itself isn't installed or not on PATH. This kit doesn't install Hermes.

```bash
curl -fsSL https://raw.githubusercontent.com/nousresearch/hermes-agent/main/scripts/install.sh | bash
```

Then re-run `./scripts/install.sh`.

### Gateway error: `token already in use by profile X`

Two profiles have the same Telegram/Discord/Slack bot token.

```bash
grep -r "TELEGRAM_BOT_TOKEN" ~/.hermes/profiles/*/.env 2>/dev/null
```

Edit the duplicate and use a different bot.

### `Profile already exists` when running install

Expected if you've installed before. The script will skip create and only refresh templates (with `--force` if you want SOUL.md/config.yaml overwritten).

```bash
./scripts/install.sh --force coder    # refresh just coder's templates
```

### `.env has unfilled FILL_IN placeholders`

You haven't filled in API keys yet.

```bash
${EDITOR:-nano} ~/.hermes/profiles/coder/.env
# Replace FILL_IN with your real key
```

Then re-run `./scripts/verify.sh`.

### `model not found` after editing config

The provider isn't authenticated.

```bash
hermes -p <profile> model       # interactive picker, will prompt for key
hermes -p <profile> doctor      # shows which provider is missing creds
```

### Memory leaking between profiles

This shouldn't happen with v0.5+ but worth checking:

```bash
hermes -p coder memory status
hermes -p assistant memory status
```

Honcho identities should be different. If you see the same user/peer ID, you may have manually copied data between profiles. Run:

```bash
hermes -p <profile> honcho reset    # if available, or manually clear external store
```

### `permission denied` on `.env`

```bash
chmod 600 ~/.hermes/profiles/<profile>/.env
```

### Profile takes forever to start

Likely cause: too much memory/session data being loaded, or external memory provider is slow.

```bash
# Check size
du -sh ~/.hermes/profiles/<profile>/

# Try without external memory
hermes -p <profile> memory off
hermes -p <profile> chat
# If fast now, the memory provider is the bottleneck
```

### Cron job in one profile firing into another profile's context

Cron jobs are profile-scoped. If you see this, you likely created the cron from a different profile than expected.

```bash
hermes -p <profile> cron list
```

Cron jobs you don't expect → delete them:
```bash
hermes -p <profile> cron remove <job-id>
```

### Gateway works in foreground but not as service

Service install needs `~/.local/bin` paths to work in the systemd/launchd environment, which doesn't always inherit your shell PATH.

Check the service file:
```bash
# Linux
systemctl --user cat hermes-gateway-<profile>

# macOS
cat ~/Library/LaunchAgents/com.hermes.gateway.<profile>.plist
```

Confirm `Environment=PATH=...` (Linux) or `EnvironmentVariables` (macOS) includes `$HOME/.local/bin`.

Re-create the service:
```bash
<profile> gateway uninstall
<profile> gateway install
```

### Prompt cache misses (high cost)

Symptom: token costs are way higher than expected on Anthropic models.

Cause: dynamic content (memory, time, etc.) is being injected into the cached system prompt prefix instead of after the cache breakpoint.

Hermes handles this correctly by default (Honcho memory is appended after the cached section). If you've customized the system prompt builder, check that static content comes first and the cache breakpoint is set on the last static message.

Verify: after a few turns, costs per turn should drop sharply (cache hits start counting).

### `hermes update` breaks something

Roll back to backup made before update:

```bash
ls ~/.hermes/backups/
# pick the most recent before-update backup
hermes profile import ~/.hermes/backups/<timestamp>.tar.gz
```

Or reinstall a specific Hermes version:

```bash
pip install --force-reinstall hermes-agent==0.12.0
```

### Profile created but config.yaml is empty

Template copy failed. Re-run install with `--force`:

```bash
./scripts/install.sh --force <profile>
```

If the template is also missing in the repo:

```bash
git status            # is the file there?
git log -- profiles/<profile>/config.yaml
```

## Reporting issues

When asking for help (or filing an issue against Hermes itself), attach:

```bash
hermes dump > /tmp/hermes-dump.txt
hermes -p <profile> doctor > /tmp/profile-doctor.txt 2>&1
hermes logs --profile <profile> --tail 200 > /tmp/profile-log.txt
```

Strip secrets from these before sharing — they may include sanitized config but not always.

## Nuclear option

To completely wipe this kit's profiles (preserves the default `~/.hermes`):

```bash
./scripts/reset.sh --backup --yes
```

To remove Hermes entirely (including default profile):

```bash
hermes uninstall
```
