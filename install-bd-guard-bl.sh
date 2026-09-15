#!/bin/sh
# install-bd-guard-bl.sh — betterleaks-backed Beads terminology guard installer.
# Run from the root of the project you want to wire (it must have a .claude/ directory).
# Coexists with install-bd-guard.sh.
# Requires: jq, betterleaks

set -e

PLUGIN_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$PWD"
SETTINGS="$PROJECT_DIR/.claude/settings.json"
RULES="$HOME/.config/git/terminology.toml"

# --- validate ---
if ! command -v jq > /dev/null 2>&1; then
  echo "Error: jq is required but not found." >&2
  exit 1
fi

if [ ! -d "$PROJECT_DIR/.claude" ]; then
  echo "Error: no .claude/ directory found in $PROJECT_DIR. Run from a Claude Code project root." >&2
  exit 1
fi

# --- install hook ---
echo "Installing bd-guard-bl hook..."
mkdir -p ~/.claude/plugins/guvnah/hooks
cp "$PLUGIN_DIR/hooks/bd-guard-bl.sh" ~/.claude/plugins/guvnah/hooks/
chmod +x ~/.claude/plugins/guvnah/hooks/bd-guard-bl.sh

# --- create settings.json if missing ---
if [ ! -f "$SETTINGS" ]; then
  echo '{}' > "$SETTINGS"
fi

# --- wire PreToolUse hook (idempotent) ---
HAS_HOOK=$(jq '[.hooks.PreToolUse[]?.hooks[]?.command // ""] | any(contains("bd-guard-bl"))' "$SETTINGS")
if [ "$HAS_HOOK" = "false" ]; then
  echo "Wiring bd-guard-bl PreToolUse hook..."
  HOOK_ENTRY='{"hooks": [{"type": "command", "command": "~/.claude/plugins/guvnah/hooks/bd-guard-bl.sh"}]}'
  jq --argjson entry "$HOOK_ENTRY" \
    '.hooks.PreToolUse = ((.hooks.PreToolUse // []) + [$entry])' \
    "$SETTINGS" > "$SETTINGS.tmp" && mv "$SETTINGS.tmp" "$SETTINGS"
else
  echo "bd-guard-bl hook already wired, skipping."
fi

if ! command -v betterleaks > /dev/null 2>&1; then
  echo ""
  echo "Warning: betterleaks not found on PATH. Install it with: brew install betterleaks"
fi

echo ""
echo "Done. Betterleaks Beads terminology guard installed for $PROJECT_DIR."
echo "Rules: $RULES"
