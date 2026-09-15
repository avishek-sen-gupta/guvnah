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
# wire_hook <id> <hook block>: puts the block in the first `repo: local` entry,
# creating the entry (or the whole file) when absent. An existing entry with the
# same id is replaced, so re-running upgrades hooks wired by older installs.
wire_hook() {
  echo "Wiring $1 in .pre-commit-config.yaml..."
  HOOK_ID="$1" HOOK_BLOCK="$2" CONFIG="$CONFIG" python3 - <<'EOF'
import os, re

config = os.environ["CONFIG"]
hook_id, block = os.environ["HOOK_ID"], os.environ["HOOK_BLOCK"]
content = open(config).read() if os.path.isfile(config) else "repos:\n"

# Drop any existing entry for this id: its '- id:' line plus the lines indented deeper than the dash.
content = re.sub(
    r"\n?([ \t]*)- id: " + re.escape(hook_id) + r"[ \t]*\n(?:\1[ \t]+[^\n]*\n)*",
    "\n",
    content,
)
if not content.endswith("\n"):
    content += "\n"
lines = content.splitlines(keepends=True)

local_idx = next((i for i, l in enumerate(lines) if re.search(r"repo:\s*local", l)), None)
if local_idx is None:
    lines += ["\n", "  - repo: local\n", "    hooks:\n", block]
else:
    insert_at = next(
        (i for i in range(local_idx + 1, len(lines)) if re.match(r"\s*- repo:", lines[i])),
        len(lines),
    )
    while insert_at > local_idx + 1 and lines[insert_at - 1].strip() == "":
        insert_at -= 1
    lines.insert(insert_at, "\n" + block)

open(config, "w").write(re.sub(r"\n{3,}", "\n\n", "".join(lines)))
EOF
}

wire_hook terminology-guard "      - id: terminology-guard
        name: Terminology Guard
        entry: precommit-scripts/check-terminology
        language: script
        pass_filenames: false
        always_run: true
"

wire_hook terminology-commit-msg "      - id: terminology-commit-msg
        name: Terminology Guard (commit message)
        entry: precommit-scripts/check-commit-msg
        language: script
        stages: [commit-msg]
"

# --- activate the hooks in .git/hooks ---
if command -v pre-commit > /dev/null 2>&1 \
  && pre-commit install --hook-type pre-commit --hook-type commit-msg; then
  echo "Activated pre-commit and commit-msg hooks."
else
  echo ""
  echo "Warning: could not activate the hooks. Install pre-commit, then run in $PROJECT_DIR:"
  echo "  pre-commit install --hook-type pre-commit --hook-type commit-msg"
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
