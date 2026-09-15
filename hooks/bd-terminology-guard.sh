#!/usr/bin/env bash
# bd-terminology-guard.sh — PreToolUse hook that blocks Beads issue write commands
# containing forbidden terminology, matched by betterleaks against
# ~/.config/git/terminology.toml.
#
# Receives Claude Code hook JSON on stdin:
#   {"tool_name": "Bash", "tool_input": {"command": "bd create ..."}}
#
# Outputs {"continue": false, "stopReason": "..."} to stdout and exits 2 to block;
# also writes the reason to stderr so Claude Code surfaces it directly to the LLM.
# Exits 0 silently to allow.

set -euo pipefail

RULES="$HOME/.config/git/terminology.toml"

block() {
    printf '%s' "$(jq -n --arg reason "$1" '{"continue": false, "stopReason": $reason}')"
    echo "$1" >&2
    exit 2
}

input="$(cat)"
cmd="$(printf '%s' "$input" | jq -r '.tool_input.command // ""')"

# Only intercept bd write commands
if ! printf '%s' "$cmd" | grep -qE '^\s*bd\s+(create|new|update|edit|note|comment|dep\s+relate)\b'; then
    exit 0
fi

if [ ! -f "$RULES" ]; then
    exit 0
fi

if ! command -v betterleaks > /dev/null 2>&1; then
    block "Blocked: betterleaks is not installed, so the Beads terminology guard cannot check this command."
fi

text_to_check="$(printf '%s' "$cmd" | sed 's/^\s*bd\s\+[a-z ]*\s*//')"

if report="$(printf '%s' "$text_to_check" \
    | betterleaks stdin --no-banner -l error -c "$RULES" -f json -r - 2> /dev/null)"; then
    exit 0
fi

matched="$(printf '%s' "$report" | jq -r '.[0].Match // empty' 2> /dev/null || true)"
if [ -z "$matched" ]; then
    block "Blocked: betterleaks failed to scan the Beads command. Check $RULES."
fi
block "Blocked: Beads command contains sensitive terminology matching \"$matched\". Remove it before retrying."
