#!/bin/sh
# install-terminology-guard.sh — betterleaks-backed Terminology Guard installer.
# Run from the root of the git project you want to protect.
# Copies scripts to precommit-scripts/ and wires .pre-commit-config.yaml.

set -e

PLUGIN_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$PWD"
SCRIPTS_DIR="$PROJECT_DIR/precommit-scripts"
CONFIG="$PROJECT_DIR/.pre-commit-config.yaml"
RULES="$HOME/.config/git/terminology.toml"

# --- validate ---
if [ ! -d "$PROJECT_DIR/.git" ]; then
  echo "Error: not a git repository. Run from the root of a git project." >&2
  exit 1
fi

# --- install scripts ---
echo "Installing betterleaks terminology guard scripts to precommit-scripts/..."
mkdir -p "$SCRIPTS_DIR"
for f in lib-terminology.sh check-terminology check-commit-msg scan-history blocklist-to-toml; do
  cp "$PLUGIN_DIR/hooks/terminology/$f" "$SCRIPTS_DIR/"
done
chmod +x "$SCRIPTS_DIR/check-terminology" "$SCRIPTS_DIR/check-commit-msg" \
  "$SCRIPTS_DIR/scan-history" "$SCRIPTS_DIR/blocklist-to-toml"

# --- wire .pre-commit-config.yaml (idempotent) ---
if ! command -v uv > /dev/null 2>&1; then
  echo "Error: uv is required to edit .pre-commit-config.yaml (brew install uv)." >&2
  exit 1
fi

echo "Wiring terminology hooks in .pre-commit-config.yaml..."
"$PLUGIN_DIR/hooks/terminology/wire-precommit-config" add "$CONFIG"

# --- activate the hooks in .git/hooks ---
PRE_COMMIT_CMD="pre-commit install --hook-type pre-commit --hook-type commit-msg"

# pre-commit refuses to install while core.hooksPath is set. A local value that
# just points at this repo's own .git/hooks is redundant, so remove it.
LOCAL_HOOKS_PATH="$(git config --local --get core.hooksPath || true)"
if [ -n "$LOCAL_HOOKS_PATH" ]; then
  case "$LOCAL_HOOKS_PATH" in
    "~"*) RESOLVED="$HOME${LOCAL_HOOKS_PATH#\~}" ;;
    /*) RESOLVED="$LOCAL_HOOKS_PATH" ;;
    *) RESOLVED="$PROJECT_DIR/$LOCAL_HOOKS_PATH" ;;
  esac
  OWN_HOOKS="$(cd "$PROJECT_DIR/.git" && pwd -P)/hooks"
  if [ -d "$RESOLVED" ] && [ "$(cd "$RESOLVED" && pwd -P)" = "$OWN_HOOKS" ]; then
    git config --local --unset-all core.hooksPath
    echo "Removed redundant core.hooksPath ($LOCAL_HOOKS_PATH is this repo's own .git/hooks)."
  fi
fi

HOOKS_PATH="$(git config --get core.hooksPath || true)"
if [ -n "$HOOKS_PATH" ]; then
  echo ""
  echo "Warning: hooks NOT activated. core.hooksPath is set to $HOOKS_PATH, so pre-commit"
  echo "refuses to install and git won't run hooks from .git/hooks. Either remove it"
  echo "(git config --unset core.hooksPath; add --global if it is set globally) and run:"
  echo "  $PRE_COMMIT_CMD"
  echo "or make the hooks in $HOOKS_PATH call pre-commit."
elif ! command -v pre-commit > /dev/null 2>&1; then
  echo ""
  echo "Warning: hooks NOT activated. pre-commit is not installed (brew install pre-commit). Then run:"
  echo "  $PRE_COMMIT_CMD"
elif $PRE_COMMIT_CMD; then
  echo "Activated pre-commit and commit-msg hooks."
else
  echo ""
  echo "Warning: hooks NOT activated. pre-commit install failed (see above). Fix that, then run:"
  echo "  $PRE_COMMIT_CMD"
fi

# --- prerequisites reminder ---
if ! command -v betterleaks > /dev/null 2>&1; then
  echo ""
  echo "Warning: betterleaks not found on PATH. Install it with: brew install betterleaks"
fi
if [ ! -f "$RULES" ]; then
  echo ""
  echo "Note: no rules file found at $RULES"
  echo "Generate it from your blocklist with:"
  echo "  precommit-scripts/blocklist-to-toml > $RULES"
fi

echo ""
echo "Done. Betterleaks terminology guard installed for $PROJECT_DIR."
echo ""
echo "  Pre-commit gate : precommit-scripts/check-terminology (via .pre-commit-config.yaml)"
echo "  Commit-msg gate : precommit-scripts/check-commit-msg (via .pre-commit-config.yaml)"
echo "  History scanner : precommit-scripts/scan-history"
echo "  Rules           : $RULES"
