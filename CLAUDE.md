# Hermes Agent Railway Template

## Architecture

Railway worker container that runs Hermes Agent's gateway directly.

- `start.sh` — Creates persistent runtime directories and `exec`s `hermes gateway run --replace -v`
- `Dockerfile` — Installs Hermes Agent and packages the direct gateway entrypoint
- Config comes from Railway environment variables and/or `/data/.hermes/.env`
- Hermes writes runtime state under `/data/.hermes`, including `gateway.pid` and `gateway_state.json`

## Key patterns

- The gateway is the main container process, so Railway starts it automatically on boot
- `hermes cron status` should see the running instance because Hermes owns the PID/runtime files
- No wrapper web server or UI layer is involved in startup anymore
