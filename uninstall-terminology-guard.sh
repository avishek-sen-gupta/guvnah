#!/bin/sh
# uninstall-terminology-guard.sh — betterleaks-backed Terminology Guard uninstaller.
# Run from the root of the git project you want to unwire.

set -e

PLUGIN_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$PWD"
SCRIPTS_DIR="$PROJECT_DIR/precommit-scripts"
CONFIG="$PROJECT_DIR/.pre-commit-config.yaml"

# --- validate ---
if [ ! -d "$PROJECT_DIR/.git" ]; then
  echo "Error: not a git repository. Run from the root of a git project." >&2
  exit 1
fi

# --- remove from .pre-commit-config.yaml ---
if [ -f "$CONFIG" ]; then
  if ! command -v uv > /dev/null 2>&1; then
    echo "Error: uv is required to edit .pre-commit-config.yaml (brew install uv)." >&2
    exit 1
  fi
  echo "Removing betterleaks terminology hooks from .pre-commit-config.yaml..."
  "$PLUGIN_DIR/hooks/terminology/wire-precommit-config" remove "$CONFIG"
  if ! grep -q "id:" "$CONFIG"; then
    rm -f "$CONFIG"
    echo ".pre-commit-config.yaml was empty after removal — deleted."
  fi
else
  echo "No .pre-commit-config.yaml found, skipping."
fi

# --- remove installed scripts ---
if [ -d "$SCRIPTS_DIR" ]; then
  echo "Removing betterleaks terminology guard scripts from precommit-scripts/..."
  rm -f "$SCRIPTS_DIR/lib-terminology.sh" "$SCRIPTS_DIR/check-terminology" \
    "$SCRIPTS_DIR/check-commit-msg" "$SCRIPTS_DIR/scan-history" "$SCRIPTS_DIR/blocklist-to-toml"
  rmdir "$SCRIPTS_DIR" 2>/dev/null || true
fi

echo ""
echo "Done. Betterleaks terminology guard uninstalled for $PROJECT_DIR."
