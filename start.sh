#!/bin/bash
set -euo pipefail

export HOME="${HOME:-/data}"
export HERMES_HOME="${HERMES_HOME:-/data/.hermes}"
export DASHBOARD_PORT="${DASHBOARD_PORT:-8081}"
export API_SERVER_PORT="${API_SERVER_PORT:-8642}"
export WEBHOOK_PORT="${WEBHOOK_PORT:-8644}"
export ZENNOTES_PORT="${ZENNOTES_PORT:-7878}"
export ZENNOTES_VAULT_PATH="${ZENNOTES_VAULT_PATH:-/data/Documents/Obsidian Vault}"

if [[ -z "${PROXY_PORT:-}" ]]; then
  export PROXY_PORT="${PORT:-8080}"
fi

mkdir -p "$HERMES_HOME/sessions"
mkdir -p "$HERMES_HOME/skills"
mkdir -p "$HERMES_HOME/skills/taskwarrior-task-manager"
mkdir -p "$HERMES_HOME/workspace"
mkdir -p "$HERMES_HOME/pairing"
mkdir -p "$HERMES_HOME/logs"
mkdir -p "$HERMES_HOME/scripts"
mkdir -p "$HOME/.task"
mkdir -p "$ZENNOTES_VAULT_PATH"
mkdir -p /data/.zennotes

if [ ! -f "$HOME/.taskrc" ]; then
  touch "$HOME/.taskrc"
fi

cp /opt/taskwrrior-task-manager/SKILL.md "$HERMES_HOME/skills/taskwarrior-task-manager/SKILL.md"

# ZenNotes uses a single shared auth token: the desktop app sends it as a
# Bearer token, and the browser exchanges it for a session cookie at login.
# Persist it on the volume so it stays stable across restarts (desktop apps
# remember it); honour an explicit ZENNOTES_AUTH_TOKEN if one is provided.
if [[ -z "${ZENNOTES_AUTH_TOKEN:-}" ]]; then
  ZENNOTES_TOKEN_FILE="/data/.zennotes/auth-token"
  if [[ ! -f "$ZENNOTES_TOKEN_FILE" ]]; then
    python -c 'import secrets; print(secrets.token_urlsafe(32))' > "$ZENNOTES_TOKEN_FILE"
    chmod 600 "$ZENNOTES_TOKEN_FILE"
  fi
  ZENNOTES_AUTH_TOKEN="$(cat "$ZENNOTES_TOKEN_FILE")"
  export ZENNOTES_AUTH_TOKEN
  echo "ZenNotes auth token: $ZENNOTES_AUTH_TOKEN"
fi

cleanup() {
  trap - TERM INT EXIT
  if [[ -n "${proxy_pid:-}" ]]; then
    kill "$proxy_pid" 2>/dev/null || true
    wait "$proxy_pid" 2>/dev/null || true
  fi
  if [[ -n "${dashboard_pid:-}" ]]; then
    kill "$dashboard_pid" 2>/dev/null || true
    wait "$dashboard_pid" 2>/dev/null || true
  fi
  if [[ -n "${zennotes_pid:-}" ]]; then
    kill "$zennotes_pid" 2>/dev/null || true
    wait "$zennotes_pid" 2>/dev/null || true
  fi
}

trap cleanup TERM INT EXIT

# ZenNotes notes server. Bound to loopback and reached only through the proxy,
# which is the sole client on 127.0.0.1 — so we trust it for X-Forwarded-*
# (real client IP for login rate-limiting). Auth is ZenNotes' own token, served
# under the /notes base path so SPA assets and API calls resolve through the
# proxy. The proxy rewrites the session-cookie path to /notes/api.
ZENNOTES_BIND="127.0.0.1:${ZENNOTES_PORT}" \
ZENNOTES_VAULT_PATH="$ZENNOTES_VAULT_PATH" \
ZENNOTES_BROWSE_ROOTS="$ZENNOTES_VAULT_PATH" \
ZENNOTES_BASE_PATH="/notes" \
ZENNOTES_TRUSTED_PROXIES="127.0.0.1,::1" \
ZENNOTES_CONFIG_PATH="/data/.zennotes/server.json" \
zennotes-server &
zennotes_pid=$!

python /app/server.py &
dashboard_pid=$!

python /app/proxy.py &
proxy_pid=$!

set +e
wait -n "$dashboard_pid" "$proxy_pid"
status=$?
set -e

cleanup
exit "$status"
