# Hermes Agent Railway Template

Deploy [Hermes Agent](https://github.com/nousresearch/hermes-agent) on [Railway](https://railway.app) with a single public HTTP port for the Hermes API, webhooks, and a configuration web UI.

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/deploy/hermes-agent)

## What you get

- **Single-Port Proxy** — one public listener exposes `/configure`, `/api`, `/v1`, `/webhooks`, and `/notes`
- **ZenNotes Notes Server** — a [ZenNotes](https://github.com/ZenNotes/zennotes) Markdown/Obsidian-vault editor at `/notes`, gated by admin Basic auth
- **Web Config UI** — configure LLM providers, messaging channels, tool API keys, model settings, and user pairing from your browser
- **Gateway Management** — start, stop, restart, and view gateway logs from the UI
- **Bundled Taskwarrior Tooling** — `taskwarrior`, `node`, and `task-agent` are available in the container
- **Preinstalled Task Skill** — the `taskwarrior-task-manager` skill is copied into `/data/.hermes/skills` on boot
- **Persistent Storage** — config and data survive container restarts via Railway volume

## Quick Start

### Deploy to Railway

1. Click the "Deploy on Railway" button above
2. Attach a volume mounted at `/data`
3. Set `ADMIN_PASSWORD` in Railway, or read the generated password from deploy logs
4. Open your app URL at `/configure` and log in with `admin` or `ADMIN_USERNAME`
5. Configure at least one LLM provider API key and your messaging channels, then save and restart the gateway

### Run Locally with Docker

```bash
docker build -t hermes-agent .
docker run --rm -it -p 8080:8080 --env-file .env -e ADMIN_PASSWORD=changeme -v hermes-data:/data hermes-agent
```

Open `http://localhost:8080/configure` and log in with `admin` / `changeme`.

Taskwarrior data uses the default home-based path, so with `HOME=/data` the task database lives under `/data/.task`. Boot also creates `/data/.taskrc` if it does not exist.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `8080` | Public Railway port. Used as `PROXY_PORT` when `PROXY_PORT` is unset |
| `PROXY_PORT` | `8080` | Public reverse proxy port |
| `DASHBOARD_PORT` | `8081` | Internal config UI server port |
| `API_SERVER_PORT` | `8642` | Internal Hermes API server port used for `/v1/*` |
| `WEBHOOK_PORT` | `8644` | Internal Hermes webhook port used for `/webhooks/*` |
| `ZENNOTES_PORT` | `7878` | Internal ZenNotes server port surfaced through `/notes/*` |
| `ZENNOTES_VAULT_PATH` | `/data/Documents/Obsidian Vault` | Markdown/Obsidian vault root ZenNotes serves and edits |
| `ZENNOTES_AUTH_TOKEN` | *(generated)* | ZenNotes auth token. If unset, one is generated, persisted at `/data/.zennotes/auth-token`, and printed to stdout |
| `HERMES_HOME` | `/data/.hermes` | Persistent Hermes home directory |
| `ADMIN_USERNAME` | `admin` | Basic auth username |
| `ADMIN_PASSWORD` | *(generated)* | Basic auth password. If unset, a random password is generated and printed to stdout |
| `LINEAR_WEBHOOK_SECRET` | *(unset)* | Shared secret used to verify incoming `Linear-Signature` HMACs |
| `LINEAR_WEBHOOK_MAX_AGE_SECONDS` | `60` | Replay window for Linear `webhookTimestamp`; set `0` to disable |
| `LLM_MODEL` | *(unset)* | Default model Hermes should use |
| `TELEGRAM_BOT_TOKEN` | *(unset)* | Telegram bot token |
| `TELEGRAM_ALLOWED_USERS` | *(unset)* | Telegram user allowlist |

Hermes will also read `/data/.hermes/.env`; the web UI writes saved config there.

## GitHub CLI

`gh` is installed in the container.

Recommended auth setup:

1. Set `GITHUB_TOKEN` in the web UI or as a service environment variable.
2. Hermes passes `GITHUB_TOKEN` into the gateway process, and `gh` can use that token non-interactively.

For manual shell usage inside the container, either export `GH_TOKEN` or log in explicitly:

```bash
export GH_TOKEN="$GITHUB_TOKEN"
gh auth status
```

Or:

```bash
printf '%s' "$GITHUB_TOKEN" | gh auth login --hostname github.com --with-token
```

Use a token with the scopes your workflows need, typically `repo`, `read:org`, and `workflow` for repository and PR automation.

## Architecture

```
Railway Container
├── /app/start.sh
│   ├── creates persistent Hermes directories under /data/.hermes
│   ├── seeds /data/.hermes/skills/taskwarrior-task-manager/SKILL.md
│   ├── creates /data/.task and /data/.taskrc for Taskwarrior
│   ├── creates the ZenNotes vault dir and /data/.zennotes
│   ├── starts ZenNotes (zennotes-server) on 127.0.0.1:$ZENNOTES_PORT
│   ├── starts Internal Dashboard (server.py) on $DASHBOARD_PORT
│   └── starts Public Proxy (proxy.py) on $PROXY_PORT
├── Public Proxy (Starlette + uvicorn)
│   ├── /configure -> internal dashboard
│   ├── /api/* -> internal dashboard API
│   ├── /v1/* -> Hermes API server
│   ├── /webhooks/* -> Hermes webhook server
│   └── /notes/* -> ZenNotes server (admin Basic auth)
├── Internal Dashboard (server.py)
│   ├── / — Config editor + status dashboard
│   ├── /health — Dashboard health check
│   └── /api/* — Config, status, logs, gateway control
├── ZenNotes (zennotes-server)
│   └── serves $ZENNOTES_VAULT_PATH under base path /notes
├── /usr/local/bin/task-agent
│   └── wraps node /opt/taskwrrior-task-manager/dist/task-agent.js
└── hermes gateway — managed as async subprocess by server.py
```

The public listener forwards `/configure` to the dashboard while keeping Hermes HTTP endpoints available on the same external port. `server.py` manages the Hermes gateway as a child process and captures stdout/stderr into a ring buffer viewable in the dashboard.

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/` | No | Proxy info |
| `GET` | `/configure` | Yes | Web UI |
| `GET` | `/health` | No | Forwarded dashboard health check |
| `GET` | `/api/config` | Yes | Get config, with secrets masked |
| `PUT` | `/api/config` | Yes | Save config |
| `GET` | `/api/status` | Yes | Gateway, provider, and channel status |
| `GET` | `/api/logs` | Yes | Recent gateway log lines |
| `POST` | `/api/gateway/start` | Yes | Start gateway |
| `POST` | `/api/gateway/stop` | Yes | Stop gateway |
| `POST` | `/api/gateway/restart` | Yes | Restart gateway |
| `*` | `/v1/*` | Depends on Hermes config | Forwarded to Hermes API server |
| `*` | `/webhooks/*` | Depends on Hermes config | Forwarded to Hermes webhook server |
| `*` | `/notes/*` | Yes (ZenNotes token) | Forwarded to the ZenNotes server |

## ZenNotes

A self-hosted [ZenNotes](https://github.com/ZenNotes/zennotes) server is built into the image and serves your Markdown/Obsidian vault at `/notes`.

- The vault lives at `ZENNOTES_VAULT_PATH` (default `/data/Documents/Obsidian Vault`) on the persistent volume and is created on boot.
- ZenNotes binds to `127.0.0.1:$ZENNOTES_PORT` and is protected by its own auth token. Set `ZENNOTES_AUTH_TOKEN`, or let boot generate one — it is persisted at `/data/.zennotes/auth-token` and printed to the deploy logs.

**Browser:** open `https://<your-app>/notes` and enter the token when prompted; ZenNotes exchanges it for a session cookie. The proxy rewrites the cookie's path to `/notes/api` so it works under the base path.

**Desktop / mobile app:** the ZenNotes app can connect to this server as a remote workspace. Use:

- **Server URL:** `https://<your-app>/notes`
- **Auth token:** the same `ZENNOTES_AUTH_TOKEN`

The desktop app authenticates with a Bearer token (no cookies), so it works through the same endpoint.

> **WebSocket limitation:** the public proxy uses `httpx`, which does not forward WebSockets, so ZenNotes' live file-watch (`/notes/api/watch`) does not work through the public port. Notes still load, save, and search over HTTP in both the browser and the app; only live updates from external vault changes are unavailable.

## Linear Webhooks

Routes under `/webhooks/linear-*` are treated as Linear webhook endpoints by the public proxy.

- The proxy reads the exact raw request bytes before parsing JSON.
- It verifies `Linear-Signature` with `LINEAR_WEBHOOK_SECRET` using HMAC-SHA256.
- It optionally rejects stale payloads when `webhookTimestamp` is older than `LINEAR_WEBHOOK_MAX_AGE_SECONDS`.
- It forwards the original raw body unchanged to Hermes and adds `X-Webhook-Signature`, `X-Webhook-Provider`, `X-Webhook-Event`, and `X-Original-Linear-Signature`.

## Supported Providers

OpenRouter, DeepSeek, DashScope, GLM/Z.AI, Kimi, MiniMax, Hugging Face

## Supported Channels

Telegram, Discord, Slack, WhatsApp, Email, Mattermost, Matrix
