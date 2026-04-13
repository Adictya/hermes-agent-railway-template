# Hermes Agent Railway Template

Deploy [Hermes Agent](https://github.com/nousresearch/hermes-agent) on [Railway](https://railway.app) as a direct background gateway process.

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/deploy/hermes-agent)

## What you get

- **Direct Gateway Startup** — the container runs `hermes gateway run` directly
- **Cron-Compatible Runtime** — Hermes writes its own PID/runtime status files, so `hermes cron status` sees the live gateway
- **Auto-Start on Deploy** — Railway starts Hermes immediately when the container boots
- **Bundled Taskwarrior Tooling** — `taskwarrior`, `node`, and `task-agent` are available in the container
- **Preinstalled Task Skill** — the `taskwarrior-task-manager` skill is copied into `/data/.hermes/skills` on boot
- **Persistent Storage** — config and data survive container restarts via Railway volume

## Quick Start

### Deploy to Railway

1. Click the "Deploy on Railway" button above
2. Attach a volume mounted at `/data`
3. Set your Hermes environment variables in Railway, for example:
   - `LLM_MODEL`
   - `OPENROUTER_API_KEY`
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_ALLOWED_USERS`
4. Deploy the service
5. Watch Railway logs for `Hermes Gateway Starting` and your messaging adapter connecting

### Run Locally with Docker

```bash
docker build -t hermes-agent .
docker run --rm -it --env-file .env -v hermes-data:/data hermes-agent
```

The container runs the Hermes gateway in the foreground and logs directly to stdout/stderr.

Taskwarrior data uses the default home-based path, so with `HOME=/data` the task database lives under `/data/.task`. Boot also creates `/data/.taskrc` if it does not exist.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `HERMES_HOME` | `/data/.hermes` | Persistent Hermes home directory |
| `LLM_MODEL` | *(unset)* | Default model Hermes should use |
| `OPENROUTER_API_KEY` | *(unset)* | Example provider key |
| `TELEGRAM_BOT_TOKEN` | *(unset)* | Telegram bot token |
| `TELEGRAM_ALLOWED_USERS` | *(unset)* | Telegram user allowlist |

Hermes will also read `/data/.hermes/.env` if you prefer to manage config from inside the container.

## Architecture

```
Railway Container
├── /app/start.sh
│   ├── creates persistent Hermes directories under /data/.hermes
│   ├── seeds `/data/.hermes/skills/taskwarrior-task-manager/SKILL.md`
│   ├── creates `/data/.task` for Taskwarrior data
│   ├── creates `/data/.taskrc` if missing
│   └── execs `hermes gateway run --replace -v`
├── /usr/local/bin/task-agent
│   └── wraps `node /opt/taskwrrior-task-manager/dist/task-agent.js`
└── hermes gateway — runs as the main container process
```

This template is a worker-style Railway deployment. There is no bundled admin UI or HTTP health endpoint.

## Supported Providers

OpenRouter, DeepSeek, DashScope, GLM/Z.AI, Kimi, MiniMax, Hugging Face

## Supported Channels

Telegram, Discord, Slack, WhatsApp, Email, Mattermost, Matrix
