# Hermes Agent Railway Template

## Architecture

Railway container that exposes Hermes Agent and a configuration dashboard through one public reverse proxy.

- `start.sh` — Creates persistent runtime directories, seeds the Taskwarrior skill, starts the internal dashboard, and starts the public proxy
- `proxy.py` — Public Starlette reverse proxy for `/configure`, `/api`, `/v1`, and `/webhooks`
- `server.py` — Authenticated configuration dashboard that manages `hermes gateway run --replace -v` as a subprocess
- `Dockerfile` — Installs Hermes Agent, proxy/dashboard dependencies, GitHub CLI, ffmpeg, Taskwarrior, Node, and `task-agent`
- Config comes from Railway environment variables and/or `/data/.hermes/.env`
- Hermes writes runtime state under `/data/.hermes`, including `gateway.pid` and `gateway_state.json`

## Key patterns

- Railway exposes the proxy on `$PORT`; `start.sh` maps that to `PROXY_PORT` when needed
- The dashboard is internal-only on `$DASHBOARD_PORT`, default `8081`
- Hermes API and webhook endpoints stay internal and are surfaced through `/v1/*` and `/webhooks/*`
- `server.py` starts Hermes with `--replace -v` so Hermes owns its PID/runtime status files
- `hermes cron status` should see the running instance because Hermes writes its own runtime files
