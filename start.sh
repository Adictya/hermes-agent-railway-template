#!/bin/bash
set -euo pipefail

mkdir -p /data/.hermes/sessions
mkdir -p /data/.hermes/skills
mkdir -p /data/.hermes/workspace
mkdir -p /data/.hermes/pairing

PUBLIC_PORT="${PORT:-8080}"
export DASHBOARD_PORT="${DASHBOARD_PORT:-8081}"
export API_SERVER_PORT="${API_SERVER_PORT:-8642}"
export WEBHOOK_PORT="${WEBHOOK_PORT:-8645}"

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
}

trap cleanup TERM INT EXIT

env PORT="$DASHBOARD_PORT" python /app/server.py &
dashboard_pid=$!

env PORT="$PUBLIC_PORT" python /app/proxy.py &
proxy_pid=$!

set +e
wait -n "$dashboard_pid" "$proxy_pid"
status=$?
set -e

cleanup
exit "$status"
