# guvnah

[![CI](https://github.com/avishek-sen-gupta/guvnah/actions/workflows/ci.yml/badge.svg)](https://github.com/avishek-sen-gupta/guvnah/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE.md)

A collection of Claude Code hooks and tools for enforcing discipline during agentic development workflows.

**Tools:**

- **Pipefail Guard** — a PreToolUse hook that prepends `set -o pipefail;` to every Bash command, ensuring that exit codes of all Bash invocations are surfaced correctly (even when they are tailed, etc.)
- **[Python FP Lint](https://github.com/avishek-sen-gupta/python-fp-lint)** (`/lint`) — a functional-programming linter for Python that detects mutation, reassignment, and impurity patterns using ast-grep, Ruff, and beniget backends
- **Beads Terminology Guard** — a PreToolUse hook that blocks Beads issue-tracker commands containing sensitive terminology
- **Git Terminology Guard** — a git pre-commit hook that prevents forbidden terms from entering source history
- **History Scanner** (`scan-history`) — scans full git history (file contents + commit messages) for forbidden terms and prints a formatted report

All tools are independent and can be installed/enabled simultaneously.

## Using the tools together

Every tool wires its own hook and can be enabled independently:

| Tool | Command | Hook events |
|---|---|---|
| Pipefail Guard | `install-pipefail-guard.sh` / `uninstall-pipefail-guard.sh` | `PreToolUse` (matcher: Bash) |
| Beads Terminology Guard | `install-bd-guard.sh` / `uninstall-bd-guard.sh` | `PreToolUse` |
| Git Terminology Guard | `install-terminology-guard.sh` / `uninstall-terminology-guard.sh` | git pre-commit hook |

When several are active they don't conflict — each operates on its own hook wiring.

## Requirements

- [Claude Code](https://claude.ai/code) with a project that has a `.claude/` directory
- Python 3.10+ (used by the hook scripts — no external runtime dependencies)
- `jq` (for the automated installers)

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

### Pipefail Guard

```bash
cd /path/to/your/project
/path/to/guvnah/install-pipefail-guard.sh
```

Installs:
- `pipefail-guard.sh` hook → `.claude/hooks/`
- Wires a `PreToolUse` hook (matcher: `Bash`) in `.claude/settings.json`

Uninstall: `/path/to/guvnah/uninstall-pipefail-guard.sh`

### Beads Terminology Guard

```bash
cd /path/to/your/project
/path/to/guvnah/install-bd-guard.sh
```

Installs:
- `bd-terminology-guard.sh` hook → `~/.claude/plugins/guvnah/hooks/`
- Wires `PreToolUse` hook in `.claude/settings.json`

Blocklist: `~/.config/git/blocklist.txt` (one term per line)

Uninstall: `/path/to/guvnah/uninstall-bd-guard.sh`

### Git Terminology Guard

Prevents forbidden terms from entering git history via a pre-commit hook. Uses the same blocklist as the Beads guard.

```bash
cd /path/to/your/project
/path/to/guvnah/install-terminology-guard.sh
```

Installs:
- `check-terminology`, `check-commit-msg`, `scan-history`, `lib-terminology.sh` → `precommit-scripts/` in the current project
- Wires `terminology-guard` (pre-commit) and `terminology-commit-msg` (commit-msg) into `.pre-commit-config.yaml` (idempotent)

**Blocklist:** `~/.config/git/blocklist.txt` — one regex pattern per line (comments with `#` ignored)  
**Excludelist:** `~/.config/git/blocklist-exclude.txt` — glob patterns for files to skip (optional)

**Scanning history:**
```bash
precommit-scripts/scan-history
```

Scans the full git history (file contents + commit messages) for forbidden terms and prints a formatted report.

Uninstall: `/path/to/guvnah/uninstall-terminology-guard.sh`

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

**3. Create blocklist:**
```bash
mkdir -p ~/.config/git
echo "sensitive-term" >> ~/.config/git/blocklist.txt
```

## License

[MIT](LICENSE.md)
