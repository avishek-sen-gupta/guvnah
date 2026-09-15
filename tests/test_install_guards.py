"""Tests for the combined guard installers.

Tests cover:
- install-terminology-guard.sh: activating pre-commit and commit-msg hooks via `pre-commit install`
- install-guards.sh: terminology guard + Beads guard in one run
- uninstall-guards.sh: removing both guards without uninstalling pre-commit

A stub `pre-commit` on PATH records its invocations, so tests don't depend on the
real pre-commit or touch real git hooks.
"""

import json
import os
import subprocess

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
INSTALL_TERMINOLOGY = os.path.join(REPO_ROOT, "install-terminology-guard.sh")
INSTALL_GUARDS = os.path.join(REPO_ROOT, "install-guards.sh")
UNINSTALL_GUARDS = os.path.join(REPO_ROOT, "uninstall-guards.sh")
BD_COMMAND = "~/.claude/plugins/guvnah/hooks/bd-terminology-guard.sh"
PRE_COMMIT_ARGS = "install --hook-type pre-commit --hook-type commit-msg"


def git(repo: str, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def make_project(tmp_path, with_claude: bool = True) -> str:
    project = tmp_path / "project"
    project.mkdir()
    git(str(project), "init", "-b", "main")
    if with_claude:
        (project / ".claude").mkdir()
    return str(project)


def make_stub(tmp_path, exit_code: int = 0) -> tuple[str, str]:
    """Create a stub pre-commit that logs '<cwd>\\t<args>' and exits with exit_code."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "pre-commit.log"
    stub = bin_dir / "pre-commit"
    stub.write_text(
        f'#!/bin/sh\nprintf \'%s\\t%s\\n\' "$PWD" "$*" >> "{log}"\nexit {exit_code}\n'
    )
    stub.chmod(0o755)
    return str(bin_dir), str(log)


def run(
    script: str, project: str, tmp_path, bin_dir: str
) -> subprocess.CompletedProcess:
    env = {
        **os.environ,
        "HOME": str(tmp_path / "home"),
        "PATH": bin_dir + os.pathsep + os.environ["PATH"],
    }
    return subprocess.run(
        ["sh", script], cwd=project, env=env, capture_output=True, text=True
    )


def read_calls(log: str) -> list[tuple[str, str]]:
    """Return (cwd, args) for each stub invocation.

    Kept separate because pytest's tmp_path names contain the test name, which
    would otherwise leak words like 'uninstall' into argument checks.
    """
    if not os.path.isfile(log):
        return []
    with open(log) as f:
        pairs = (line.split("\t", 1) for line in f.read().splitlines())
        return [(cwd, args) for cwd, args in pairs]


def read_config(project: str) -> str:
    path = os.path.join(project, ".pre-commit-config.yaml")
    if not os.path.isfile(path):
        return ""
    with open(path) as f:
        return f.read()


def settings_commands(project: str) -> list[str]:
    path = os.path.join(project, ".claude", "settings.json")
    if not os.path.isfile(path):
        return []
    with open(path) as f:
        settings = json.load(f)
    return [
        h["command"]
        for entry in settings.get("hooks", {}).get("PreToolUse", [])
        for h in entry["hooks"]
    ]


# ── install-terminology-guard.sh: pre-commit activation ──────────


class TestTerminologyInstallerActivatesHooks:
    def test_runs_pre_commit_install_for_both_hook_types(self, tmp_path):
        project = make_project(tmp_path, with_claude=False)
        bin_dir, log = make_stub(tmp_path)
        result = run(INSTALL_TERMINOLOGY, project, tmp_path, bin_dir)
        assert result.returncode == 0, result.stderr
        calls = [cwd for cwd, args in read_calls(log) if args == PRE_COMMIT_ARGS]
        assert len(calls) == 1
        assert os.path.realpath(calls[0]) == os.path.realpath(project)

    def test_warns_but_succeeds_when_pre_commit_install_fails(self, tmp_path):
        project = make_project(tmp_path, with_claude=False)
        bin_dir, _ = make_stub(tmp_path, exit_code=1)
        result = run(INSTALL_TERMINOLOGY, project, tmp_path, bin_dir)
        assert result.returncode == 0, result.stderr
        assert "id: terminology-guard\n" in read_config(project)
        assert "pre-commit install --hook-type pre-commit" in result.stdout


# ── install-guards.sh ────────────────────────────────────────────


class TestInstallGuards:
    def test_installs_both_guards(self, tmp_path):
        project = make_project(tmp_path)
        bin_dir, log = make_stub(tmp_path)
        result = run(INSTALL_GUARDS, project, tmp_path, bin_dir)
        assert result.returncode == 0, result.stderr
        config = read_config(project)
        assert config.count("id: terminology-guard\n") == 1
        assert config.count("id: terminology-commit-msg\n") == 1
        assert settings_commands(project) == [BD_COMMAND]
        assert any(args == PRE_COMMIT_ARGS for _, args in read_calls(log))

    def test_skips_beads_guard_without_claude_dir(self, tmp_path):
        project = make_project(tmp_path, with_claude=False)
        bin_dir, _ = make_stub(tmp_path)
        result = run(INSTALL_GUARDS, project, tmp_path, bin_dir)
        assert result.returncode == 0, result.stderr
        assert "id: terminology-guard\n" in read_config(project)
        assert not os.path.exists(os.path.join(project, ".claude"))
        assert "Beads" in result.stdout and "skip" in result.stdout.lower()

    def test_is_idempotent(self, tmp_path):
        project = make_project(tmp_path)
        bin_dir, _ = make_stub(tmp_path)
        run(INSTALL_GUARDS, project, tmp_path, bin_dir)
        result = run(INSTALL_GUARDS, project, tmp_path, bin_dir)
        assert result.returncode == 0, result.stderr
        config = read_config(project)
        assert config.count("id: terminology-guard\n") == 1
        assert config.count("id: terminology-commit-msg\n") == 1
        assert settings_commands(project) == [BD_COMMAND]

    def test_reports_missing_rules_file(self, tmp_path):
        project = make_project(tmp_path)
        bin_dir, _ = make_stub(tmp_path)
        result = run(INSTALL_GUARDS, project, tmp_path, bin_dir)
        summary = result.stdout.split("Summary")[-1]
        assert "terminology.toml" in summary
        assert "missing" in summary.lower()

    def test_fails_outside_git_repo(self, tmp_path):
        project = tmp_path / "not-a-repo"
        project.mkdir()
        bin_dir, _ = make_stub(tmp_path)
        result = run(INSTALL_GUARDS, str(project), tmp_path, bin_dir)
        assert result.returncode != 0
        assert "not a git repository" in result.stderr


# ── uninstall-guards.sh ──────────────────────────────────────────


class TestUninstallGuards:
    def test_removes_both_guards(self, tmp_path):
        project = make_project(tmp_path)
        bin_dir, _ = make_stub(tmp_path)
        run(INSTALL_GUARDS, project, tmp_path, bin_dir)
        result = run(UNINSTALL_GUARDS, project, tmp_path, bin_dir)
        assert result.returncode == 0, result.stderr
        assert "terminology" not in read_config(project)
        assert settings_commands(project) == []
        hook = tmp_path / "home" / ".claude" / "plugins" / "guvnah" / "hooks"
        assert not (hook / "bd-terminology-guard.sh").exists()

    def test_does_not_uninstall_pre_commit(self, tmp_path):
        project = make_project(tmp_path)
        bin_dir, log = make_stub(tmp_path)
        run(INSTALL_GUARDS, project, tmp_path, bin_dir)
        assert any(args == PRE_COMMIT_ARGS for _, args in read_calls(log))
        result = run(UNINSTALL_GUARDS, project, tmp_path, bin_dir)
        assert result.returncode == 0, result.stderr
        assert not any(args.split()[:1] == ["uninstall"] for _, args in read_calls(log))

    def test_works_without_claude_dir(self, tmp_path):
        project = make_project(tmp_path, with_claude=False)
        bin_dir, _ = make_stub(tmp_path)
        run(INSTALL_GUARDS, project, tmp_path, bin_dir)
        result = run(UNINSTALL_GUARDS, project, tmp_path, bin_dir)
        assert result.returncode == 0, result.stderr
        assert "terminology" not in read_config(project)
