# Commands Reference

Quick command index. Run `hermes <command> --help` for full options.

## Profile lifecycle

```bash
# Create
hermes profile create <name>                    # blank
hermes profile create <name> --clone            # clone config only (config.yaml, .env, SOUL.md)
hermes profile create <name> --clone-all        # clone EVERYTHING (memory, sessions, skills, cron)
hermes profile create <name> --clone --clone-from <source>

# List / inspect
hermes profile list                             # all profiles, * = active
hermes profile show <name>                      # detail view

# Switch / target
hermes profile use <name>                       # change sticky default
hermes -p <name> <command>                      # one-off use without changing default
hermes --profile <name> <command>               # equivalent long form

# Rename / delete / alias
hermes profile rename <old> <new>
hermes profile alias <name> [--name X] [--remove]
hermes profile delete <name> [--yes]            # CANNOT delete default profile

# Backup / restore
hermes profile export <name> [-o path.tar.gz]
hermes profile import <archive.tar.gz> [--name X]

# Distribution (git-based)
hermes profile install <git-url> [--alias]
hermes profile update <name>                    # pull new version, preserve memory + .env
```

## Per-profile operations

After creating a profile, every Hermes command works against it:

```bash
<profile> chat                                  # alias form (recommended)
hermes -p <profile> chat                        # explicit form

<profile> setup                                 # interactive provider setup
<profile> model                                 # pick model
<profile> tools                                 # toggle tools
<profile> doctor                                # health check
<profile> config edit                           # edit config.yaml
<profile> config set <key> <value>              # set one value
<profile> skills list                           # list profile's skills
<profile> sessions list                         # list past sessions
<profile> memory status                         # check active memory provider
```

## Gateway (per profile)

```bash
<profile> gateway start                         # foreground
<profile> gateway install                       # systemd/launchd service (background, auto-start)
<profile> gateway uninstall                     # remove service
<profile> gateway status

# Restart all profile gateways at once (via systemd)
systemctl --user restart 'hermes-gateway-*'
```

## Conversation control

```bash
hermes chat -q "single message"                 # one-shot, no TUI
hermes -c                                       # resume most recent session
hermes -c "project name"                        # resume by name
hermes --resume <session-id>                    # resume specific
hermes sessions list
hermes sessions rename <id> <title>
```

## Diagnostics

```bash
hermes doctor                                   # global checks
hermes -p <profile> doctor                      # per-profile checks
hermes dump                                     # full config snapshot for issue reports
hermes logs --profile <name>                    # tail profile's logs
hermes status                                   # provider auth status
hermes --version
```

## Memory

```bash
hermes memory setup                             # pick external provider (Honcho, Mem0, etc.)
hermes memory status                            # what's active
hermes memory off                               # disable external (built-in still works)
```

## Update

```bash
hermes update                                   # pull latest Hermes
hermes update --restart-gateway                 # also restart all profile gateways
hermes update --check                           # dry run
```

## Shell completion

```bash
# bash
eval "$(hermes completion bash)"

# zsh
eval "$(hermes completion zsh)"

# fish
hermes completion fish > ~/.config/fish/completions/hermes.fish
```

Add to `~/.bashrc` or `~/.zshrc` for persistence. Completion includes profile names.

## Environment variables

```bash
HERMES_HOME=<path>     # override profile home (used internally by aliases)
HERMES_DEBUG=1         # verbose logging
```

## One-page cheat for this kit

```bash
# Initial setup
./scripts/install.sh                            # all 4 profiles
./scripts/install.sh coder research             # specific profiles only

# After filling .env files
./scripts/verify.sh                             # health check all
./scripts/verify.sh coder                       # health check one

# Daily use
coder chat
assistant gateway start
research chat -q "양자컴퓨터 최근 동향 정리"
community-bot doctor

# Cleanup
./scripts/reset.sh --backup                     # export then delete (recoverable)
./scripts/reset.sh coder                        # delete only one
```
