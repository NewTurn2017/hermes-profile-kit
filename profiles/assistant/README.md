# assistant profile

Personal daily assistant. Sonnet-class. CLI + optional Telegram.

## What this profile is good at
- Schedule management, reminders, follow-ups
- Drafting short messages (always confirms before sending)
- Daily briefings via cron

## Setting up Telegram

1. Talk to `@BotFather` on Telegram, create a new bot, get the token.
2. Add to `.env`:
   ```bash
   echo "TELEGRAM_BOT_TOKEN=1234:ABC..." >> ~/.hermes/profiles/assistant/.env
   ```
3. Start the gateway:
   ```bash
   assistant gateway start    # foreground for testing
   assistant gateway install  # background service for production
   ```
4. Search for your bot's username on Telegram, send `/start`.

## Setting up cron jobs

```bash
assistant chat
> "매일 아침 8시에 오늘 날씨랑 일정 요약해줘"
```

The agent will create a cron job in this profile only.

## Approval flows

By default, this profile requires confirmation before:
- Sending any message externally
- Scheduling events to a real calendar
- Deleting anything

To loosen these, edit `config.yaml`:

```yaml
gateway:
  approval_required:
    - delete    # only require approval for deletions
```
