#!/bin/sh
# install-guards.sh — installs the Git and Beads terminology guards in one run.
# Run from the root of the git project you want to protect.
# The Beads guard is skipped when the project has no .claude/ directory.

set -e

PLUGIN_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$PWD"
RULES="$HOME/.config/git/terminology.toml"

echo "== Git terminology guard"
sh "$PLUGIN_DIR/install-terminology-guard.sh"

echo ""
echo "== Beads terminology guard"
if [ -d "$PROJECT_DIR/.claude" ]; then
  sh "$PLUGIN_DIR/install-bd-guard.sh"
  BEADS="installed"
else
  echo "Skipping Beads guard: no .claude/ directory in $PROJECT_DIR."
  BEADS="skipped (no .claude/ directory)"
fi

if [ -f "$RULES" ]; then
  RULES_STATUS="present"
else
  RULES_STATUS="MISSING — run: $PLUGIN_DIR/hooks/terminology/blocklist-to-toml > $RULES"
fi

if command -v betterleaks > /dev/null 2>&1; then
  BETTERLEAKS_STATUS="found"
else
  BETTERLEAKS_STATUS="MISSING — run: brew install betterleaks"
fi

echo ""
echo "== Summary"
echo "  Git terminology guard   : installed"
echo "  Beads terminology guard : $BEADS"
echo "  Rules (terminology.toml): $RULES_STATUS"
echo "  betterleaks             : $BETTERLEAKS_STATUS"
