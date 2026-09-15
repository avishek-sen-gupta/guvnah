#!/bin/sh
# uninstall-betterleaks-guard.sh — betterleaks-backed Terminology Guard uninstaller.
# Run from the root of the git project you want to unwire.
# Leaves the grep-based terminology guard untouched.

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
  echo "Removing betterleaks terminology hooks from .pre-commit-config.yaml..."
  CONFIG="$CONFIG" python3 - <<'EOF'
import os, re

config = os.environ["CONFIG"]
content = open(config).read()

# Remove each hook entry: its '- id:' line plus the lines indented deeper than the dash.
for hook_id in ["bl-terminology-guard", "bl-terminology-commit-msg"]:
    content = re.sub(
        r"\n?([ \t]*)- id: " + re.escape(hook_id) + r"[ \t]*\n(?:\1[ \t]+[^\n]*\n)*",
        "\n",
        content,
    )

# Remove repo: local blocks whose hooks: section is now empty
content = re.sub(r"\n  - repo: local\n    hooks:\n(?:[ \t]*\n)*(?=  - repo:|\Z)", "\n", content)
content = re.sub(r"\n{3,}", "\n\n", content)

if "id:" in content:
    open(config, "w").write(content)
else:
    os.remove(config)
    print(".pre-commit-config.yaml was empty after removal — deleted.")
EOF
else
  echo "No .pre-commit-config.yaml found, skipping."
fi

# --- remove installed scripts ---
if [ -d "$SCRIPTS_DIR" ]; then
  echo "Removing betterleaks terminology guard scripts from precommit-scripts/..."
  rm -f "$SCRIPTS_DIR/lib-betterleaks.sh" "$SCRIPTS_DIR/check-terminology-bl" \
    "$SCRIPTS_DIR/check-commit-msg-bl" "$SCRIPTS_DIR/scan-history-bl" "$SCRIPTS_DIR/blocklist-to-toml"
  rmdir "$SCRIPTS_DIR" 2>/dev/null || true
fi

echo ""
echo "Done. Betterleaks terminology guard uninstalled for $PROJECT_DIR."
