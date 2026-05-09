# community-bot profile

Korean dev community helper bot. Haiku-class for cost efficiency. Runs on Telegram + Discord.

## What this profile is good at
- Answering common dev questions in Korean
- Pointing to canonical docs instead of long explanations
- Handling volume cheaply

## Why Haiku?
Community channels see lots of repeat questions. Haiku's speed and cost make a 10x difference at scale. Quality is fine for FAQ-level depth.

## Setting up Telegram

```bash
# Create a NEW bot at @BotFather (different from the assistant profile's bot)
echo "TELEGRAM_BOT_TOKEN=..." >> ~/.hermes/profiles/community-bot/.env
```

## Setting up Discord

1. Create a Discord application: https://discord.com/developers/applications
2. Create a Bot user, copy token.
3. **Important**: enable "Message Content Intent" in the bot settings (otherwise the bot can read mentions but not full messages).
4. Add to .env:
   ```bash
   echo "DISCORD_BOT_TOKEN=..." >> ~/.hermes/profiles/community-bot/.env
   ```
5. Generate an invite URL with `bot` and `applications.commands` scopes, invite to your server.

## Rate limiting

This profile ships with rate limits to control costs:

```yaml
rate_limit:
  per_user_per_hour: 30
  per_channel_per_hour: 200
```

Adjust in `config.yaml` if your community is bigger or smaller.

## Channel norms

The SOUL.md tells the bot to mirror channel tone. If your community uses 반말 vs 존댓말 inconsistently, override per-channel:

```bash
community-bot chat
> "디스코드의 #help 채널에서는 항상 존댓말 써. 텔레그램은 반말 OK."
```

The bot will save that to MEMORY.md and apply going forward.

## Auto-start in production

```bash
community-bot gateway install   # runs as systemd/launchd service
systemctl --user status hermes-gateway-community-bot   # Linux
```

## Token isolation

Make sure THIS bot's tokens are different from any other profile's tokens. Hermes will refuse to start the gateway if there's a conflict, but it's cleaner to design the bot identities separately from the start.
