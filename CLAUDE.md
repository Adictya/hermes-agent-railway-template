# Hermes Agent Railway Template

## Architecture

Railway container that exposes Hermes Agent and a configuration dashboard through one public reverse proxy.

- `start.sh` — Creates persistent runtime directories, seeds the Taskwarrior skill, starts the ZenNotes server, the internal dashboard, and the public proxy
- `proxy.py` — Public Starlette reverse proxy for `/configure`, `/api`, `/v1`, `/webhooks`, and `/notes`
- `server.py` — Authenticated configuration dashboard that manages `hermes gateway run --replace -v` as a subprocess
- `Dockerfile` — Multi-stage: builds the ZenNotes Go server (web bundle embedded) and installs Hermes Agent, proxy/dashboard dependencies, GitHub CLI, ffmpeg, Taskwarrior, Node, and `task-agent`
- Config comes from Railway environment variables and/or `/data/.hermes/.env`
- Hermes writes runtime state under `/data/.hermes`, including `gateway.pid` and `gateway_state.json`

## Key patterns

- Railway exposes the proxy on `$PORT`; `start.sh` maps that to `PROXY_PORT` when needed
- The dashboard is internal-only on `$DASHBOARD_PORT`, default `8081`
- Hermes API and webhook endpoints stay internal and are surfaced through `/v1/*` and `/webhooks/*`
- ZenNotes runs internal-only on `127.0.0.1:$ZENNOTES_PORT` (default `7878`), served under base path `/notes`, with its vault at `$ZENNOTES_VAULT_PATH` (default `/data/Documents/Obsidian Vault`)
- ZenNotes uses its own `ZENNOTES_AUTH_TOKEN` (Bearer for the desktop app, session cookie for the browser). `start.sh` persists a generated token at `/data/.zennotes/auth-token` unless one is provided; it is printed to stdout on boot
- ZenNotes' session cookie is hardcoded to `Path=/api`, so `proxy.py` rewrites the `Set-Cookie` path to `/notes/api` so the browser sends it back under the base path. The desktop app uses Bearer and is unaffected
- `start.sh` sets `ZENNOTES_TRUSTED_PROXIES=127.0.0.1,::1` so ZenNotes trusts the loopback proxy's `X-Forwarded-*` (real client IP for login rate-limiting)
- The proxy uses `httpx`, which does not proxy WebSockets, so ZenNotes' live file-watch (`/notes/api/watch`) does not work through the public port; notes still load/save over HTTP
- `server.py` starts Hermes with `--replace -v` so Hermes owns its PID/runtime status files
- `hermes cron status` should see the running instance because Hermes writes its own runtime files
