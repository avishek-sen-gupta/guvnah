#!/bin/sh
# uninstall-terminology-guard.sh — Terminology Guard uninstaller.
# Run from the root of the git project you want to unwire.

set -e

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
  if grep -q "id: terminology-guard" "$CONFIG" 2>/dev/null; then
    echo "Removing terminology-guard from .pre-commit-config.yaml..."
    python3 -c "
import re, sys

with open('$CONFIG') as f:
    content = f.read()

# Remove terminology-guard hook block (matches from '- id: terminology-guard' to end of its entry)
content = re.sub(
    r'\n[ \t]*- id: terminology-guard\n(?:[ \t]+[^\n]*\n)*',
    '\n',
    content
)

with open('$CONFIG', 'w') as f:
    f.write(content)
"
  else
    echo "terminology-guard not found in .pre-commit-config.yaml, skipping."
  fi

  if grep -q "id: terminology-commit-msg" "$CONFIG" 2>/dev/null; then
    echo "Removing terminology-commit-msg from .pre-commit-config.yaml..."
    python3 -c "
import re, sys

with open('$CONFIG') as f:
    content = f.read()

# Remove terminology-commit-msg hook block
content = re.sub(
    r'\n[ \t]*- id: terminology-commit-msg\n(?:[ \t]+[^\n]*\n)*',
    '\n',
    content
)

with open('$CONFIG', 'w') as f:
    f.write(content)
"
  else
    echo "terminology-commit-msg not found in .pre-commit-config.yaml, skipping."
  fi

  # Clean up empty repo: local blocks left behind
  python3 -c "
import re

with open('$CONFIG') as f:
    content = f.read()

# Remove repo: local blocks whose hooks: section is empty
content = re.sub(r'\n  - repo: local\n    hooks:\n(?:\n)+(?=  - repo:|\Z)', '\n', content)

with open('$CONFIG', 'w') as f:
    f.write(content)
" 2>/dev/null || true

  # If the config has no hooks left, remove it
  if ! grep -q "id:" "$CONFIG" 2>/dev/null; then
    rm -f "$CONFIG"
    echo ".pre-commit-config.yaml was empty after removal — deleted."
  fi
else
  echo "No .pre-commit-config.yaml found, skipping."
fi

# --- remove installed scripts ---
if [ -d "$SCRIPTS_DIR" ]; then
  echo "Removing terminology guard scripts from precommit-scripts/..."
  rm -f "$SCRIPTS_DIR/check-terminology" "$SCRIPTS_DIR/check-commit-msg" "$SCRIPTS_DIR/scan-history" "$SCRIPTS_DIR/lib-terminology.sh"
  rmdir "$SCRIPTS_DIR" 2>/dev/null || true
else
  echo "No precommit-scripts/ directory found, skipping."
fi

# --- clean up legacy install location if present ---
LEGACY_DIR="$HOME/.claude/plugins/context-injector/gates/terminology"
if [ -d "$LEGACY_DIR" ]; then
  echo "Removing legacy install at $LEGACY_DIR..."
  rm -f "$LEGACY_DIR/check-terminology" "$LEGACY_DIR/scan-history" "$LEGACY_DIR/lib-terminology.sh"
  rmdir "$LEGACY_DIR" 2>/dev/null || true
  rmdir "$HOME/.claude/plugins/context-injector/gates" 2>/dev/null || true
fi

echo ""
echo "Done. Terminology guard uninstalled for $PROJECT_DIR."
