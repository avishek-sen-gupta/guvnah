#!/bin/bash
# Shared helpers for the betterleaks-backed terminology guard.
# Source this file; do not execute directly.

RULES="$HOME/.config/git/terminology.toml"

# Returns 1 (with a note) when no rules file exists — callers allow in that case,
# matching the grep-based guard's behaviour with no blocklist.
bl_require_rules() {
  [ -f "$RULES" ] && return 0
  echo "[terminology-guard-bl] No rules file at $RULES — skipping." >&2
  echo "[terminology-guard-bl] Generate it with: blocklist-to-toml > $RULES" >&2
  return 1
}

bl_require_binary() {
  command -v betterleaks > /dev/null 2>&1 && return 0
  echo "[terminology-guard-bl] betterleaks not found on PATH (brew install betterleaks)." >&2
  return 1
}

bl_blocked() {
  echo "" >&2
  echo "[terminology-guard-bl] Forbidden terms found. Rules: $RULES" >&2
  echo "[terminology-guard-bl] Fix the content or update the rules to proceed." >&2
}
