# Hermes Agent Railway Template

One-click deploy [Hermes Agent](https://github.com/nousresearch/hermes-agent) on [Railway](https://railway.app) with a web-based config UI and status dashboard.

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/deploy/hermes-agent)

## What you get

- **Web Config UI** — configure LLM providers, messaging channels, tool API keys, and model settings from your browser
- **Status Dashboard** — monitor gateway state, uptime, provider/channel status, and live logs
- **Gateway Management** — start, stop, and restart the Hermes gateway from the UI
- **Basic Auth** — password-protected admin panel
- **Persistent Storage** — config and data survive container restarts via Railway volume

## Quick Start

### Deploy to Railway

1. Click the "Deploy on Railway" button above
2. Set the `ADMIN_PASSWORD` environment variable (or a random one will be generated and printed to logs)
3. Attach a volume mounted at `/data`
4. Open your app URL at `/configure` — you'll be prompted for credentials (default username: `admin`)
5. Configure at least one LLM provider API key and your messaging channels, then hit Save
6. Once setup is complete, remove the public endpoint from your Railway service — the web UI is only needed for initial configuration and Hermes operates entirely through its configured channels (Telegram, Discord, Slack, etc.)

### Run Locally with Docker

```bash
docker build -t hermes-agent .
docker run --rm -it -p 8080:8080 -e PORT=8080 -e DASHBOARD_PORT=8081 -e ADMIN_PASSWORD=changeme -v hermes-data:/data hermes-agent
```

Open `http://localhost:8080/configure` and log in with `admin` / `changeme`.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `8080` | Public reverse proxy port |
| `DASHBOARD_PORT` | `8081` | Internal `server.py` port |
| `API_SERVER_PORT` | `8642` | Internal Hermes API server port used for `/v1/*` |
| `WEBHOOK_PORT` | `8645` | Internal Hermes webhook port used for `/webhooks/*` |
| `ADMIN_USERNAME` | `admin` | Basic auth username |
| `ADMIN_PASSWORD` | *(generated)* | Basic auth password. If unset, a random password is generated and printed to stdout |

All Hermes configuration (LLM providers, messaging channels, tool API keys) is managed through the web UI.

## Architecture

```
Railway Container
├── Public Proxy (Starlette + uvicorn) on `$PORT`
│   ├── /configure -> internal dashboard
│   ├── /api/* -> internal dashboard API
│   ├── /v1/* -> Hermes API server
│   └── /webhooks/* -> Hermes webhook server
├── Internal Dashboard (`server.py`) on `$DASHBOARD_PORT`
│   ├── / — Config editor + status dashboard
│   ├── /health — Dashboard health check
│   └── /api/* — Config, status, logs, gateway control
└── hermes gateway — managed as async subprocess by `server.py`
```

The public listener runs on `$PORT` and forwards `/configure` to the existing dashboard while keeping Hermes HTTP endpoints available on the same external port. `server.py` still manages the Hermes gateway as a child process, and gateway stdout/stderr is captured into a ring buffer viewable in the dashboard.

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/` | No | Proxy info |
| `GET` | `/configure` | Yes | Web UI |
| `GET` | `/health` | No | Forwarded dashboard/gateway health check |
| `GET` | `/api/config` | Yes | Get config (secrets masked) |
| `PUT` | `/api/config` | Yes | Save config |
| `GET` | `/api/status` | Yes | Gateway, provider, channel status |
| `GET` | `/api/logs` | Yes | Recent gateway log lines |
| `POST` | `/api/gateway/start` | Yes | Start gateway |
| `POST` | `/api/gateway/stop` | Yes | Stop gateway |
| `POST` | `/api/gateway/restart` | Yes | Restart gateway |
| `*` | `/v1/*` | Depends on Hermes config | Forwarded to Hermes API server |
| `*` | `/webhooks/*` | Depends on Hermes config | Forwarded to Hermes webhook server |

## Supported Providers

OpenRouter, DeepSeek, DashScope, GLM/Z.AI, Kimi, MiniMax, Hugging Face

## Supported Channels

Telegram, Discord, Slack, WhatsApp, Email, Mattermost, Matrix
