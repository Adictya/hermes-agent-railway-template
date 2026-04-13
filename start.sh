#!/bin/bash
set -euo pipefail

export HERMES_HOME="${HERMES_HOME:-/data/.hermes}"

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

# Run the gateway as PID 1 so Hermes writes its own PID/runtime status files.
exec hermes gateway run --replace -v
