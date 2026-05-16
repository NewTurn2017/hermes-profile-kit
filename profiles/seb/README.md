# seb — Second Brain profile

Slack bot that controls your Obsidian vault and NotebookLM. Powered by gpt-5.5
via the local Codex CLI proxy.

## Prerequisites

1. **Hermes** ≥ 0.12.0 installed (`hermes --version`)
2. **codex CLI** logged in (`codex auth status`) — see the proxy README for install
3. **Codex proxy running** on `localhost:8765` (`curl http://localhost:8765/v1/models`)
4. **notebooklm CLI** set up (run `notebooklm setup` if not already done)
5. **Obsidian vault** at `/Users/genie/Obsidian/second-brain/second-brain/`

## Setup

```bash
hpk setup seb
```

The wizard will ask for three Slack tokens. Follow the steps below to get them.

## Slack App creation (one-time, ~2 min via manifest)

### 1. Create the app from the bundled manifest

Go to <https://api.slack.com/apps> → **Create New App** → **From an app
manifest** → pick your workspace → paste the contents of
[`slack-app-manifest.json`](slack-app-manifest.json) → **Next** → **Create**.

This single step provisions bot user, scopes (`app_mentions:read`,
`chat:write`, `files:read`), `app_mention` event subscription, Socket Mode,
and interactivity — everything except the three secrets you still need to
copy out.

### 2. Install + grab `SLACK_BOT_TOKEN`

Left sidebar → **Install App** → **Install to Workspace** → Allow → copy the
**Bot User OAuth Token** (`xoxb-...`). This is **`SLACK_BOT_TOKEN`**.

### 3. Generate `SLACK_APP_TOKEN` (app-level, for Socket Mode)

Slack does not let manifests create app-level tokens. Do it once by hand:
**Basic Information → App-Level Tokens → Generate Token and Scopes** →
any name (e.g. `seb-socket`) → add scope `connections:write` → **Generate**
→ copy the `xapp-...` token. This is **`SLACK_APP_TOKEN`**.

### 4. Reveal `SLACK_SIGNING_SECRET`

**Basic Information → App Credentials → Signing Secret → Show** → copy the
32-char hex string. This is **`SLACK_SIGNING_SECRET`**.

## Start the bot

```bash
seb gateway start
```

In your Slack workspace, invite the bot to a channel: `/invite @seb`

Test: `@seb 안녕`

## Vault zones

| Zone | Paths | Policy |
|---|---|---|
| AUTO_WRITE | `raw/**` | Bot writes freely |
| APPROVE | `wiki/**`, root `*.md` | Bot proposes, you click Approve |
| LOCKED | `90.*/**`, `_private/**`, `.obsidian/**` | Access denied |

## NotebookLM artifacts are saved to

```
<vault>/raw/imported/notebooklm/<YYYY-MM-DD>-<slug>/
```

## Proxy auto-start

See `scripts/codex-openai-proxy/README.md` for the macOS launchd setup. The
proxy must be running before `seb gateway start`.
