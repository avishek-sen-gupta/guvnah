#!/bin/sh
# install-betterleaks-guard.sh — betterleaks-backed Terminology Guard installer.
# Run from the root of the git project you want to protect.
# Copies scripts to precommit-scripts/ and wires .pre-commit-config.yaml.
# Coexists with install-terminology-guard.sh (distinct script names and hook ids).

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
for f in lib-betterleaks.sh check-terminology-bl check-commit-msg-bl scan-history-bl blocklist-to-toml; do
  cp "$PLUGIN_DIR/hooks/betterleaks/$f" "$SCRIPTS_DIR/"
done
chmod +x "$SCRIPTS_DIR/check-terminology-bl" "$SCRIPTS_DIR/check-commit-msg-bl" \
  "$SCRIPTS_DIR/scan-history-bl" "$SCRIPTS_DIR/blocklist-to-toml"

# --- wire .pre-commit-config.yaml (idempotent) ---
# wire_hook <id> <hook block>: adds the block to the first `repo: local` entry,
# creating the entry (or the whole file) when absent.
wire_hook() {
  if [ -f "$CONFIG" ] && grep -qE "id: $1[[:space:]]*$" "$CONFIG"; then
    echo "$1 already in .pre-commit-config.yaml, skipping."
    return
  fi
  echo "Adding $1 to .pre-commit-config.yaml..."
  HOOK_BLOCK="$2" CONFIG="$CONFIG" python3 - <<'EOF'
import os, re

config, block = os.environ["CONFIG"], os.environ["HOOK_BLOCK"]
lines = open(config).readlines() if os.path.isfile(config) else ["repos:\n"]

local_idx = next((i for i, l in enumerate(lines) if re.search(r"repo:\s*local", l)), None)
if local_idx is None:
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    lines += ["\n", "  - repo: local\n", "    hooks:\n", block]
else:
    insert_at = len(lines)
    for i in range(local_idx + 1, len(lines)):
        if re.match(r"\s*- repo:", lines[i]):
            insert_at = i
            while insert_at > local_idx and lines[insert_at - 1].strip() == "":
                insert_at -= 1
            break
    if insert_at > 0 and not lines[insert_at - 1].endswith("\n"):
        lines[insert_at - 1] += "\n"
    lines.insert(insert_at, "\n" + block)

open(config, "w").writelines(lines)
EOF
}

wire_hook bl-terminology-guard "      - id: bl-terminology-guard
        name: Terminology Guard (betterleaks)
        entry: precommit-scripts/check-terminology-bl
        language: script
        pass_filenames: false
        always_run: true
"

wire_hook bl-terminology-commit-msg "      - id: bl-terminology-commit-msg
        name: Terminology Guard (betterleaks, commit message)
        entry: precommit-scripts/check-commit-msg-bl
        language: script
        stages: [commit-msg]
"

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
echo "  Pre-commit gate : precommit-scripts/check-terminology-bl (via .pre-commit-config.yaml)"
echo "  Commit-msg gate : precommit-scripts/check-commit-msg-bl (needs: pre-commit install --hook-type commit-msg)"
echo "  History scanner : precommit-scripts/scan-history-bl"
echo "  Rules           : $RULES"
