# Gateways and Multi-Channel Setup

## Concept

Each profile runs an **independent gateway process** that listens on whatever messaging channels its `.env` configures. A profile can listen on:

- One channel (just Telegram)
- Multiple channels at once (Telegram + Discord + Slack from one process)
- Zero channels (CLI-only profile)

Channels supported in v0.13:
- **Messengers**: Telegram, Discord, Slack, WhatsApp, Signal, Matrix, Mattermost, Microsoft Teams
- **CN-region**: WeChat, DingTalk, Feishu/Lark, WeCom, QQBot
- **Other**: Email (IMAP/SMTP), SMS (Twilio), BlueBubbles (iMessage), Home Assistant, Webhook

## How channels are detected

When you run `<profile> gateway start`, Hermes scans the profile's `.env` for known token keys. Whichever ones are populated determine which adapters spin up.

```
TELEGRAM_BOT_TOKEN → Telegram adapter
DISCORD_BOT_TOKEN  → Discord adapter
SLACK_BOT_TOKEN    → Slack adapter
... etc
```

No separate "enable channel X" config — populating the token IS the enable signal.

## Same channel, different profiles

You can have multiple profiles each running their own bot on the same platform, as long as the **bot tokens are different**:

```
~/.hermes/profiles/withgenie/.env
  TELEGRAM_BOT_TOKEN=xxx-AAA  # @withgenie_bot

~/.hermes/profiles/community-bot/.env
  TELEGRAM_BOT_TOKEN=xxx-BBB  # @vibecoding_helper_bot
```

Both can run simultaneously. Each is a separate Telegram identity with its own conversations.

## Token conflict protection

If you accidentally put the same token in two profiles' `.env` and start both gateways, the second one will fail with an explicit error:

```
Error: Telegram bot token already in use by profile 'withgenie'.
Refusing to start.
```

Per-profile token locks make this structurally impossible. No silent message dropping or mixed routing.

## Cross-platform conversation continuity

Within a single profile, sessions are unified by user identity, not by channel. If a user on Telegram also messages the same bot on Discord (recognized via gateway-level user mapping), the conversation history threads together. This works **inside one profile**. Across profiles, conversations stay separate.

## Background services (recommended for production)

Foreground gateways are fine for testing, but for actual deployment use service install:

```bash
withgenie gateway install      # creates hermes-gateway-withgenie
community-bot gateway install  # creates hermes-gateway-community-bot
```

This:
- Registers a systemd unit (Linux) or launchd plist (macOS).
- Auto-starts on boot.
- Restarts on crash (configurable).
- Logs to standard journal/log location.

Manage them with normal service tools:

```bash
# Linux
systemctl --user start hermes-gateway-community-bot
systemctl --user status hermes-gateway-community-bot
journalctl --user -u hermes-gateway-community-bot -f

# macOS
launchctl start com.hermes.gateway.community-bot
launchctl list | grep hermes
```

## Pattern: 1 profile, multi-channel (one persona, many surfaces)

Use this when one bot identity should be reachable from multiple platforms.

```bash
# .env in this profile
TELEGRAM_BOT_TOKEN=xxx
DISCORD_BOT_TOKEN=yyy
EMAIL_IMAP_HOST=imap.gmail.com
EMAIL_USERNAME=bot@example.com
EMAIL_PASSWORD=app-password
```

One process, three adapters, unified memory. Good for personal assistants you want to reach from any device.

## Pattern: N profiles, 1 channel (multiple bots on one platform)

Use this for distinct bot identities on the same platform — for example, a client-facing Slack bot and an internal Slack bot in the same Slack workspace.

```bash
client-bot/.env:    SLACK_BOT_TOKEN=client-token
internal-bot/.env:  SLACK_BOT_TOKEN=internal-token
```

Each runs as its own service. Different `SOUL.md`, different memory, different model budget.

## Pattern: N profiles, N channels (full segmentation)

Use this when work, personal, and community contexts must not mix.

| Profile | Channels | Identity |
|---------|----------|----------|
| `work` | Slack (work workspace) | @work-assistant |
| `personal` | Telegram | @genie_personal |
| `community` | Discord, Telegram (community) | @vibecoding_helper |
| `coder` | CLI only | n/a |

Total: 4 service units, fully isolated. Fail one, others keep running.

## Approval flows for channels

For profiles that take consequential actions (sending messages, scheduling events), set approval rules in `config.yaml`:

```yaml
gateway:
  approval_required:
    - send_message      # bot drafts, user confirms with /approve
    - delete
    - schedule_event
```

This kit's `assistant` and `community-bot` profiles ship with sensible defaults.

## Common operational commands

```bash
# See which gateways are running across all profiles
systemctl --user list-units 'hermes-gateway-*'

# Restart everything after pulling new Hermes version
hermes update --restart-gateway

# Tail logs from one profile's gateway
journalctl --user -u hermes-gateway-coder -f
```

## Troubleshooting channels

| Symptom | Cause | Fix |
|---------|-------|-----|
| Gateway starts but bot doesn't respond | Token typo, or bot not added to chat | Verify token at `@BotFather`; add bot to the channel |
| `403 Forbidden` from Telegram | Bot blocked or kicked | Re-add the bot to the chat |
| Discord bot online but silent | Missing intent permissions in Discord developer portal | Enable Message Content intent |
| Slack `channel_not_found` | Bot not invited to channel | `/invite @your-bot` in the channel |
| Email gateway hangs | IMAP creds wrong or Gmail blocking less-secure apps | Use app-specific password |
| Two gateways using same token | Token reuse across profiles | Edit one `.env`, restart that gateway |
