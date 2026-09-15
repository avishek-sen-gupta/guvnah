#!/bin/sh
# uninstall-guards.sh — removes the Git and Beads terminology guards in one run.
# Run from the root of the git project you want to unwire.
# Leaves pre-commit itself installed, since other hooks may rely on it.

set -e

PLUGIN_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$PWD"

echo "== Git terminology guard"
sh "$PLUGIN_DIR/uninstall-terminology-guard.sh"

echo ""
echo "== Beads terminology guard"
# uninstall-bd-guard.sh also deletes the hook file shared by all projects, so only
# run it where the guard can actually be wired.
if [ -f "$PROJECT_DIR/.claude/settings.json" ]; then
  sh "$PLUGIN_DIR/uninstall-bd-guard.sh"
else
  echo "Skipping Beads guard: no .claude/settings.json in $PROJECT_DIR."
fi
