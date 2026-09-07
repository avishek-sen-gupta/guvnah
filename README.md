# context-injector

[![CI](https://github.com/avishek-sen-gupta/context-injector/actions/workflows/ci.yml/badge.svg)](https://github.com/avishek-sen-gupta/context-injector/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE.md)

A collection of Claude Code hooks and tools for enforcing discipline during agentic development workflows.

**Tools:**

- **Pipefail Guard** — a PreToolUse hook that prepends `set -o pipefail;` to every Bash command, ensuring that exit codes of all Bash invocations are surfaced correctly (even when they are tailed, etc.)
- **Context Injection** (`/ctx`) — keyword-based context injection that adds relevant guidance files to every prompt based on what you're working on
- **[Python FP Lint](https://github.com/avishek-sen-gupta/python-fp-lint)** (`/lint`) — a functional-programming linter for Python that detects mutation, reassignment, and impurity patterns using ast-grep, Ruff, and beniget backends
- **Beads Terminology Guard** — a PreToolUse hook that blocks Beads issue-tracker commands containing sensitive terminology
- **Git Terminology Guard** — a git pre-commit hook that prevents forbidden terms from entering source history
- **History Scanner** (`scan-history`) — scans full git history (file contents + commit messages) for forbidden terms and prints a formatted report

All tools are independent and can be installed/enabled simultaneously.

## Context Injection

Keyword-matched injection of your own guidance files into every prompt.

### Commands

- **`/ctx`** — toggle on/off (state stored in `/tmp/ctx-locks/<hash>`)

### How it works

When on, every prompt receives:
1. All files from `.claude/core/` (always)
2. Matching files from `.claude/conditional/` based on keyword classification

### Keyword classification

| Keywords in prompt | Files injected from `.claude/conditional/` |
|---|---|
| implement, add, build, create, fix, feature, bug, write, emit, lower, migrate, introduce, wire, hook, support, handle, extend, port, close | design-principles, testing-patterns, refactoring, tools-skills |
| test, tdd, assert, coverage, xfail, failing, passes, red-green, fixture, integration test, unit test | testing-patterns |
| refactor, rename, extract, move, split, merge, simplify, clean, reorganize, restructure, consolidate, decompose, inline, deduplicate | design-principles, refactoring, tools-skills |
| review, pr, diff, check, feedback, critique, approve | code-review |
| verify, audit, scan, lint, sweep, validate, ensure, confirm, gate, black, lint-imports | testing-patterns, tools-skills |

### Project convention

Each project provides its own context files:

```
.claude/
  core/                    ← always injected when ctx is on
    project-context.md
    workflow.md
    ...
  conditional/             ← injected based on keyword classification
    design-principles.md
    testing-patterns.md
    code-review.md
    refactoring.md
    tools-skills.md
```

## Using the tools together

Every tool uses **separate lock files / hooks** and can be enabled independently:

| Tool | Command | Hook events |
|---|---|---|
| Context Injection | `/ctx on\|off` | `UserPromptSubmit` |
| Pipefail Guard | `install-pipefail-guard.sh` / `uninstall-pipefail-guard.sh` | `PreToolUse` (matcher: Bash) |
| Beads Terminology Guard | `install-bd-guard.sh` / `uninstall-bd-guard.sh` | `PreToolUse` |
| Git Terminology Guard | `install-terminology-guard.sh` / `uninstall-terminology-guard.sh` | git pre-commit hook |

When multiple modes are active they don't conflict — each operates on its own hook events and lock files.

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
/path/to/context-injector/install-pipefail-guard.sh
```

Installs:
- `pipefail-guard.sh` hook → `.claude/hooks/`
- Wires a `PreToolUse` hook (matcher: `Bash`) in `.claude/settings.json`

Uninstall: `/path/to/context-injector/uninstall-pipefail-guard.sh`

### Context Injection

```bash
cd /path/to/your/project
/path/to/context-injector/install-ctx.sh
```

Installs:
- `user-prompt-submit.sh` hook → `~/.claude/plugins/context-injector/hooks/`
- `/ctx` command → `~/.claude/commands/`
- Wires `UserPromptSubmit` hook in `.claude/settings.json`
- Adds `/tmp/ctx-locks` Bash permissions

Uninstall: `/path/to/context-injector/uninstall-ctx.sh`

### Beads Terminology Guard

```bash
cd /path/to/your/project
/path/to/context-injector/install-bd-guard.sh
```

Installs:
- `bd-terminology-guard.sh` hook → `~/.claude/plugins/context-injector/hooks/`
- Wires `PreToolUse` hook in `.claude/settings.json`

Blocklist: `~/.config/git/blocklist.txt` (one term per line)

Uninstall: `/path/to/context-injector/uninstall-bd-guard.sh`

### Git Terminology Guard

Prevents forbidden terms from entering git history via a pre-commit hook. Uses the same blocklist as the Beads guard.

```bash
cd /path/to/your/project
/path/to/context-injector/install-terminology-guard.sh
```

Installs:
- `check-terminology`, `scan-history`, `lib-terminology.sh` → `~/.claude/plugins/context-injector/gates/terminology/`
- Wires `check-terminology` into `.git/hooks/pre-commit` of the current project (idempotent)

**Blocklist:** `~/.config/git/blocklist.txt` — one regex pattern per line (comments with `#` ignored)  
**Excludelist:** `~/.config/git/blocklist-exclude.txt` — glob patterns for files to skip (optional)

**Scanning history:**
```bash
~/.claude/plugins/context-injector/gates/terminology/scan-history
```

Scans the full git history (file contents + commit messages) for forbidden terms and prints a formatted report.

Uninstall: `/path/to/context-injector/uninstall-terminology-guard.sh`

### All tools

You can install each tool independently — they use separate lock files and hooks and don't conflict.

All scripts are idempotent — safe to run multiple times.

### Manual

#### Context Injection

**1. Copy the hook:**
```bash
mkdir -p ~/.claude/plugins/context-injector/hooks/lib
cp hooks/lib/hash.sh ~/.claude/plugins/context-injector/hooks/lib/
cp hooks/user-prompt-submit.sh ~/.claude/plugins/context-injector/hooks/
chmod +x ~/.claude/plugins/context-injector/hooks/user-prompt-submit.sh
```

**2. Copy command:**
```bash
cp commands/ctx.md ~/.claude/commands/ctx.md
```

**3. Wire in `.claude/settings.json`:**
```json
"hooks": {
  "UserPromptSubmit": [
    {"hooks": [{"type": "command", "command": "~/.claude/plugins/context-injector/hooks/user-prompt-submit.sh"}]}
  ]
}
```

**4. Add permissions:**
```json
"Bash(mkdir:/tmp/ctx-locks)",
"Bash(touch:/tmp/ctx-locks/*)",
"Bash(rm:/tmp/ctx-locks/*)"
```

#### Beads Terminology Guard

**1. Copy the hook:**
```bash
mkdir -p ~/.claude/plugins/context-injector/hooks
cp hooks/bd-terminology-guard.sh ~/.claude/plugins/context-injector/hooks/
chmod +x ~/.claude/plugins/context-injector/hooks/bd-terminology-guard.sh
```

**2. Wire in `.claude/settings.json`:**
```json
"hooks": {
  "PreToolUse": [
    {"hooks": [{"type": "command", "command": "~/.claude/plugins/context-injector/hooks/bd-terminology-guard.sh"}]}
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
