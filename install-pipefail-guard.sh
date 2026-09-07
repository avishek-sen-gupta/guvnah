#!/usr/bin/env bash
# install-pipefail-guard.sh — Wire the pipefail guard hook into a project.
# Run from the root of the project you want to wire (it must have a .claude/ directory).
# Requires: jq
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$PWD"
SETTINGS="$PROJECT_DIR/.claude/settings.json"
DEST="$PROJECT_DIR/.claude/hooks"

# --- validate ---
if ! command -v jq > /dev/null 2>&1; then
  echo "Error: jq is required but not found." >&2
  exit 1
fi

if [ ! -d "$PROJECT_DIR/.claude" ]; then
  echo "Error: no .claude/ directory found in $PROJECT_DIR. Run from a Claude Code project root." >&2
  exit 1
fi

echo "Installing pipefail guard to $DEST ..."

mkdir -p "$DEST"
cp "$REPO_ROOT/hooks/pipefail-guard.sh" "$DEST/pipefail-guard.sh"
chmod +x "$DEST/pipefail-guard.sh"

# --- create settings.json if missing ---
if [ ! -f "$SETTINGS" ]; then
  echo '{}' > "$SETTINGS"
fi

# --- wire pipefail guard (PreToolUse with Bash matcher, idempotent) ---
PIPEFAIL_CMD=".claude/hooks/pipefail-guard.sh"
ALREADY=$(jq --arg cmd "$PIPEFAIL_CMD" \
  '[.hooks.PreToolUse[]?.hooks[]?.command // ""] | any(contains($cmd))' "$SETTINGS")
if [ "$ALREADY" = "false" ]; then
  echo "Wiring pipefail guard..."
  ENTRY='{"matcher": "Bash", "hooks": [{"type": "command", "command": "'"$PIPEFAIL_CMD"'"}]}'
  jq --argjson entry "$ENTRY" \
    '.hooks.PreToolUse = ((.hooks.PreToolUse // []) + [$entry])' \
    "$SETTINGS" > "$SETTINGS.tmp" && mv "$SETTINGS.tmp" "$SETTINGS"
else
  echo "Pipefail guard already wired, skipping."
fi

echo ""
echo "Done. Pipefail guard installed for $PROJECT_DIR."
