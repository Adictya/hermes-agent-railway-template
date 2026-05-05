#!/bin/bash
set -euo pipefail

export HOME="${HOME:-/data}"
export HERMES_HOME="${HERMES_HOME:-/data/.hermes}"
export DASHBOARD_PORT="${DASHBOARD_PORT:-8081}"
export API_SERVER_PORT="${API_SERVER_PORT:-8642}"
export WEBHOOK_PORT="${WEBHOOK_PORT:-8644}"

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

if [ ! -f "$HOME/.taskrc" ]; then
  touch "$HOME/.taskrc"
fi

cp /opt/taskwrrior-task-manager/SKILL.md "$HERMES_HOME/skills/taskwarrior-task-manager/SKILL.md"

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
