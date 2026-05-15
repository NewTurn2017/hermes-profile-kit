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

## Slack App creation (one-time)

### 1. Create the app

Go to <https://api.slack.com/apps> → **Create New App** → **From scratch**.

- App name: `seb` (or any name you like)
- Workspace: your personal workspace

### 2. Enable Socket Mode

Under **Settings → Socket Mode**, toggle **Enable Socket Mode** on. You'll be
asked to create an App-Level Token — name it anything (e.g. `seb-socket`), add
scope `connections:write`, click **Generate**. Copy the `xapp-...` token
(**SLACK_APP_TOKEN**).

### 3. Add bot scopes

Under **Features → OAuth & Permissions → Scopes → Bot Token Scopes**, add:

| Scope | Why |
|---|---|
| `app_mentions:read` | Receive @seb mentions |
| `chat:write` | Post messages + Block Kit cards |
| `files:read` | Read file content from channels |

### 4. Subscribe to events

Under **Features → Event Subscriptions**, toggle on. Under
**Subscribe to bot events**, add `app_mention`.

### 5. Install the app

Under **Features → OAuth & Permissions** → **Install to Workspace** → Allow.
Copy the **Bot User OAuth Token** (`xoxb-...`) (**SLACK_BOT_TOKEN**).

### 6. Get the Signing Secret

Under **Settings → Basic Information → App Credentials**, reveal and copy the
**Signing Secret** (32-char hex) (**SLACK_SIGNING_SECRET**).

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
