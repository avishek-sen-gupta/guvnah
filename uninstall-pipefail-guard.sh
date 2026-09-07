#!/usr/bin/env bash
# uninstall-pipefail-guard.sh — Remove the pipefail guard hook from a project.
# Run from the root of the project you want to unwire.
# Requires: jq
set -euo pipefail

PROJECT_DIR="$PWD"
SETTINGS="$PROJECT_DIR/.claude/settings.json"
HOOK="$PROJECT_DIR/.claude/hooks/pipefail-guard.sh"

# --- validate ---
if ! command -v jq > /dev/null 2>&1; then
  echo "Error: jq is required but not found." >&2
  exit 1
fi

# --- remove hook from settings.json ---
if [ -f "$SETTINGS" ]; then
  echo "Removing PreToolUse pipefail guard hook..."
  jq '.hooks.PreToolUse = [(.hooks.PreToolUse // [])[] | select(.hooks[0].command | contains("pipefail-guard") | not)]
     | if (.hooks.PreToolUse | length) == 0 then del(.hooks.PreToolUse) else . end
     | if (.hooks | length) == 0 then del(.hooks) else . end' \
    "$SETTINGS" > "$SETTINGS.tmp" && mv "$SETTINGS.tmp" "$SETTINGS"
else
  echo "No .claude/settings.json found, skipping hook removal."
fi

# --- remove hook file ---
if [ -f "$HOOK" ]; then
  rm -f "$HOOK"
  echo "Removed $HOOK"
else
  echo "Nothing to remove — $HOOK does not exist."
fi

echo ""
echo "Done. Pipefail guard uninstalled for $PROJECT_DIR."
