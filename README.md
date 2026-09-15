# guvnah

[![CI](https://github.com/avishek-sen-gupta/guvnah/actions/workflows/ci.yml/badge.svg)](https://github.com/avishek-sen-gupta/guvnah/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE.md)

A collection of Claude Code hooks and tools for enforcing discipline during agentic development workflows.

**Tools:**

- **Pipefail Guard** — a PreToolUse hook that prepends `set -o pipefail;` to every Bash command, ensuring that exit codes of all Bash invocations are surfaced correctly (even when they are tailed, etc.)
- **[Python FP Lint](https://github.com/avishek-sen-gupta/python-fp-lint)** (`/lint`) — a functional-programming linter for Python that detects mutation, reassignment, and impurity patterns using ast-grep, Ruff, and beniget backends
- **Beads Terminology Guard** — a PreToolUse hook that blocks Beads issue-tracker commands containing sensitive terminology
- **Git Terminology Guard** — git pre-commit and commit-msg hooks that prevent forbidden terms from entering source history
- **History Scanner** (`scan-history`) — scans full git history (file contents + commit messages) for forbidden terms

The terminology guards use [betterleaks](https://github.com/betterleaks/betterleaks) for matching, driven by a rules file generated from your blocklist.

All tools are independent and can be installed/enabled simultaneously.

## Using the tools together

Every tool wires its own hook and can be enabled independently:

| Tool | Command | Hook events |
|---|---|---|
| Pipefail Guard | `install-pipefail-guard.sh` / `uninstall-pipefail-guard.sh` | `PreToolUse` (matcher: Bash) |
| Beads Terminology Guard | `install-bd-guard.sh` / `uninstall-bd-guard.sh` | `PreToolUse` |
| Git Terminology Guard | `install-terminology-guard.sh` / `uninstall-terminology-guard.sh` | git pre-commit + commit-msg hooks |

When several are active they don't conflict — each operates on its own hook wiring.

## Requirements

- [Claude Code](https://claude.ai/code) with a project that has a `.claude/` directory
- Python 3.10+ (used by the hook scripts — no external runtime dependencies)
- `jq` (for the automated installers)
- [betterleaks](https://github.com/betterleaks/betterleaks) (`brew install betterleaks`) for the terminology guards

## Development Setup

This project uses [uv](https://docs.astral.sh/uv/) for dependency management during development.

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install all dependencies (runtime + dev) into .venv/
uv sync --dev

# Run tests
uv run pytest tests/ -v
```

The development environment (`.venv/` managed by uv) is independent of the hook deployment. Contributors use `uv sync --dev` for local testing; end users run the `install-*.sh` scripts to deploy.

## Installation

### Terminology guards in one step

```bash
cd /path/to/your/project
/path/to/guvnah/install-guards.sh
```

Runs `install-terminology-guard.sh` (which also runs `pre-commit install` for the pre-commit and commit-msg hooks) and `install-bd-guard.sh` (skipped when the project has no `.claude/` directory), then prints whether the rules file and `betterleaks` are in place.

Uninstall both: `/path/to/guvnah/uninstall-guards.sh` (leaves pre-commit itself installed).

### Pipefail Guard

```bash
cd /path/to/your/project
/path/to/guvnah/install-pipefail-guard.sh
```

Installs:
- `pipefail-guard.sh` hook → `.claude/hooks/`
- Wires a `PreToolUse` hook (matcher: `Bash`) in `.claude/settings.json`

Uninstall: `/path/to/guvnah/uninstall-pipefail-guard.sh`

### Terminology rules

Both terminology guards read `~/.config/git/terminology.toml`, generated from your blocklist:

- **Blocklist:** `~/.config/git/blocklist.txt` — one regex pattern per line (`#` comments ignored), matched case-insensitively
- **Excludelist:** `~/.config/git/blocklist-exclude.txt` — git pathspec globs for files to skip (optional)

```bash
/path/to/guvnah/hooks/terminology/blocklist-to-toml > ~/.config/git/terminology.toml
```

The generated file holds one rule matching every term, plus a path prefilter for the exclude globs. Regenerate it after editing either list.

With no `terminology.toml` the guards allow everything; with the rules present but `betterleaks` missing, they block.

### Git Terminology Guard

```bash
cd /path/to/your/project
/path/to/guvnah/install-terminology-guard.sh
```

Installs `check-terminology`, `check-commit-msg`, `scan-history`, `blocklist-to-toml` and `lib-terminology.sh` → `precommit-scripts/`, wires `terminology-guard` (pre-commit) and `terminology-commit-msg` (commit-msg) into `.pre-commit-config.yaml`, and runs `pre-commit install --hook-type pre-commit --hook-type commit-msg`. pre-commit refuses to install while `core.hooksPath` is set: a local value pointing at the repo's own `.git/hooks` is removed automatically; any other value is left alone and the installer warns that the hooks are NOT activated. Re-running replaces existing entries in place, so it also upgrades older installs without reshuffling the config.

Editing `.pre-commit-config.yaml` needs [uv](https://docs.astral.sh/uv/) on PATH: both the installer and the uninstaller edit it through `hooks/terminology/wire-precommit-config`, a `uv run --script` helper that rewrites the file as YAML (ruamel round-trip, comments preserved) instead of splicing lines. It also repairs configs mangled by earlier line-splicing installs — terminology hooks left under another repo, and `repo: local` entries whose `hooks:` key ended up empty, which YAML reads as null and pre-commit refuses to load.

- Staged content: `betterleaks git --pre-commit --staged`
- Commit message: `betterleaks stdin < <message file>`
- History: `precommit-scripts/scan-history` runs `betterleaks git` over all commits, then pipes every commit message line (prefixed with its short SHA) through `betterleaks stdin`

Uninstall: `/path/to/guvnah/uninstall-terminology-guard.sh`

### Beads Terminology Guard

```bash
cd /path/to/your/project
/path/to/guvnah/install-bd-guard.sh
```

Installs `bd-terminology-guard.sh` → `~/.claude/plugins/guvnah/hooks/` and wires a `PreToolUse` hook in `.claude/settings.json`. It blocks `bd` write commands (`create`, `update`, `comment`, …) whose text matches the rules.

Uninstall: `/path/to/guvnah/uninstall-bd-guard.sh`

### All tools

You can install each tool independently — they use separate lock files and hooks and don't conflict.

All scripts are idempotent — safe to run multiple times.

### Manual

#### Beads Terminology Guard

**1. Copy the hook:**
```bash
mkdir -p ~/.claude/plugins/guvnah/hooks
cp hooks/bd-terminology-guard.sh ~/.claude/plugins/guvnah/hooks/
chmod +x ~/.claude/plugins/guvnah/hooks/bd-terminology-guard.sh
```

**2. Wire in `.claude/settings.json`:**
```json
"hooks": {
  "PreToolUse": [
    {"hooks": [{"type": "command", "command": "~/.claude/plugins/guvnah/hooks/bd-terminology-guard.sh"}]}
  ]
}
```

**3. Create the blocklist and generate rules:**
```bash
mkdir -p ~/.config/git
echo "sensitive-term" >> ~/.config/git/blocklist.txt
hooks/terminology/blocklist-to-toml > ~/.config/git/terminology.toml
```

## License

[MIT](LICENSE.md)
