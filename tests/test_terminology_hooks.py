"""Tests for terminology guard hook scripts.

Tests cover:
- check-terminology: case-insensitive matching on staged diffs
- check-commit-msg: blocking forbidden terms in commit messages
- install/uninstall scripts: handling of the check-commit-msg hook
"""

import os
import stat
import subprocess

import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
HOOKS_DIR = os.path.join(REPO_ROOT, "hooks", "terminology")
CHECK_TERMINOLOGY = os.path.join(HOOKS_DIR, "check-terminology")
CHECK_COMMIT_MSG = os.path.join(HOOKS_DIR, "check-commit-msg")
INSTALL_SCRIPT = os.path.join(REPO_ROOT, "install-terminology-guard.sh")
UNINSTALL_SCRIPT = os.path.join(REPO_ROOT, "uninstall-terminology-guard.sh")


def setup_home(tmp_path, pattern: str) -> str:
    """Create a fake HOME with a blocklist containing the given pattern."""
    home = tmp_path / "home"
    git_config = home / ".config" / "git"
    git_config.mkdir(parents=True)
    (git_config / "blocklist.txt").write_text(pattern + "\n")
    return str(home)


def init_git_repo(path: str) -> None:
    """Initialise a git repo with an initial empty commit."""
    subprocess.run(["git", "init", "-b", "main", path], check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "t@t.com"],
        cwd=path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "T"], cwd=path, check=True, capture_output=True
    )
    # Initial commit so staged diff has a base
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "init"],
        cwd=path,
        check=True,
        capture_output=True,
    )


def stage_content(repo: str, content: str, filename: str = "file.txt") -> None:
    """Write content to a file and stage it."""
    filepath = os.path.join(repo, filename)
    with open(filepath, "w") as f:
        f.write(content)
    subprocess.run(["git", "add", filename], cwd=repo, check=True, capture_output=True)


def run_hook(
    script: str, args: list[str], home: str, cwd: str
) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", script] + args,
        env={**os.environ, "HOME": home},
        cwd=cwd,
        capture_output=True,
        text=True,
    )


# ── check-terminology ────────────────────────────────────────────


class TestCheckTerminologyCase:
    """check-terminology must match forbidden terms regardless of case."""

    def test_blocks_lowercase_match(self, tmp_path):
        repo = str(tmp_path / "repo")
        os.makedirs(repo)
        init_git_repo(repo)
        home = setup_home(tmp_path, "master")
        stage_content(repo, "connect to master branch\n")
        result = run_hook(CHECK_TERMINOLOGY, [], home, repo)
        assert result.returncode == 1, "should block lowercase forbidden term"

    def test_blocks_uppercase_match(self, tmp_path):
        repo = str(tmp_path / "repo")
        os.makedirs(repo)
        init_git_repo(repo)
        home = setup_home(tmp_path, "master")
        stage_content(repo, "connect to MASTER branch\n")
        result = run_hook(CHECK_TERMINOLOGY, [], home, repo)
        assert (
            result.returncode == 1
        ), "should block uppercase variant of forbidden term"

    def test_blocks_mixed_case_match(self, tmp_path):
        repo = str(tmp_path / "repo")
        os.makedirs(repo)
        init_git_repo(repo)
        home = setup_home(tmp_path, "master")
        stage_content(repo, "the Master database\n")
        result = run_hook(CHECK_TERMINOLOGY, [], home, repo)
        assert (
            result.returncode == 1
        ), "should block mixed-case variant of forbidden term"

    def test_allows_clean_content(self, tmp_path):
        repo = str(tmp_path / "repo")
        os.makedirs(repo)
        init_git_repo(repo)
        home = setup_home(tmp_path, "master")
        stage_content(repo, "connect to primary branch\n")
        result = run_hook(CHECK_TERMINOLOGY, [], home, repo)
        assert result.returncode == 0, "should allow content with no forbidden terms"


# ── check-commit-msg ─────────────────────────────────────────────


class TestCheckCommitMsg:
    """check-commit-msg must exist and block forbidden terms in commit messages."""

    def test_script_exists(self):
        assert os.path.isfile(CHECK_COMMIT_MSG), "check-commit-msg script must exist"

    def test_script_is_executable(self):
        s = os.stat(CHECK_COMMIT_MSG)
        assert s.st_mode & stat.S_IXUSR, "check-commit-msg must be executable"

    def test_blocks_forbidden_term_in_message(self, tmp_path):
        repo = str(tmp_path / "repo")
        os.makedirs(repo)
        init_git_repo(repo)
        home = setup_home(tmp_path, "master")
        msg_file = tmp_path / "COMMIT_EDITMSG"
        msg_file.write_text("fix bug in master branch\n")
        result = run_hook(CHECK_COMMIT_MSG, [str(msg_file)], home, repo)
        assert (
            result.returncode == 1
        ), "should block commit message containing forbidden term"

    def test_blocks_uppercase_term_in_message(self, tmp_path):
        repo = str(tmp_path / "repo")
        os.makedirs(repo)
        init_git_repo(repo)
        home = setup_home(tmp_path, "master")
        msg_file = tmp_path / "COMMIT_EDITMSG"
        msg_file.write_text("Merge MASTER into main\n")
        result = run_hook(CHECK_COMMIT_MSG, [str(msg_file)], home, repo)
        assert (
            result.returncode == 1
        ), "should block uppercase forbidden term in commit message"

    def test_allows_clean_commit_message(self, tmp_path):
        repo = str(tmp_path / "repo")
        os.makedirs(repo)
        init_git_repo(repo)
        home = setup_home(tmp_path, "master")
        msg_file = tmp_path / "COMMIT_EDITMSG"
        msg_file.write_text("fix bug in primary branch\n")
        result = run_hook(CHECK_COMMIT_MSG, [str(msg_file)], home, repo)
        assert result.returncode == 0, "should allow clean commit message"

    def test_exits_with_error_if_no_message_file(self, tmp_path):
        repo = str(tmp_path / "repo")
        os.makedirs(repo)
        init_git_repo(repo)
        home = setup_home(tmp_path, "master")
        result = run_hook(CHECK_COMMIT_MSG, [], home, repo)
        assert (
            result.returncode != 0
        ), "should exit with error when no message file given"


# ── install / uninstall ──────────────────────────────────────────


class TestInstallScript:
    """install-terminology-guard.sh must install check-commit-msg and wire the pre-commit hook."""

    def test_installs_check_commit_msg_script(self, tmp_path):
        repo = str(tmp_path / "repo")
        os.makedirs(repo)
        init_git_repo(repo)
        result = subprocess.run(
            ["bash", INSTALL_SCRIPT],
            cwd=repo,
            env={**os.environ, "HOME": str(tmp_path / "home")},
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"install script failed: {result.stderr}"
        assert os.path.isfile(
            os.path.join(repo, "precommit-scripts", "check-commit-msg")
        ), "check-commit-msg must be installed to precommit-scripts/"

    def test_wires_terminology_commit_msg_hook(self, tmp_path):
        repo = str(tmp_path / "repo")
        os.makedirs(repo)
        init_git_repo(repo)
        subprocess.run(
            ["bash", INSTALL_SCRIPT],
            cwd=repo,
            env={**os.environ, "HOME": str(tmp_path / "home")},
            capture_output=True,
            check=True,
        )
        config_path = os.path.join(repo, ".pre-commit-config.yaml")
        with open(config_path) as f:
            config = f.read()
        assert (
            "terminology-commit-msg" in config
        ), ".pre-commit-config.yaml must contain terminology-commit-msg hook"

    def test_install_is_idempotent_for_commit_msg_hook(self, tmp_path):
        repo = str(tmp_path / "repo")
        os.makedirs(repo)
        init_git_repo(repo)
        env = {**os.environ, "HOME": str(tmp_path / "home")}
        subprocess.run(
            ["bash", INSTALL_SCRIPT], cwd=repo, env=env, capture_output=True, check=True
        )
        result = subprocess.run(
            ["bash", INSTALL_SCRIPT], cwd=repo, env=env, capture_output=True, text=True
        )
        assert result.returncode == 0, "second install must not fail"
        config_path = os.path.join(repo, ".pre-commit-config.yaml")
        with open(config_path) as f:
            config = f.read()
        assert (
            config.count("terminology-commit-msg") == 1
        ), "terminology-commit-msg must appear exactly once after idempotent install"


class TestUninstallScript:
    """uninstall-terminology-guard.sh must remove check-commit-msg and its hook entry."""

    def test_removes_check_commit_msg_script(self, tmp_path):
        repo = str(tmp_path / "repo")
        os.makedirs(repo)
        init_git_repo(repo)
        env = {**os.environ, "HOME": str(tmp_path / "home")}
        subprocess.run(
            ["bash", INSTALL_SCRIPT], cwd=repo, env=env, capture_output=True, check=True
        )
        subprocess.run(
            ["bash", UNINSTALL_SCRIPT],
            cwd=repo,
            env=env,
            capture_output=True,
            check=True,
        )
        assert not os.path.isfile(
            os.path.join(repo, "precommit-scripts", "check-commit-msg")
        ), "check-commit-msg must be removed on uninstall"

    def test_removes_terminology_commit_msg_hook_entry(self, tmp_path):
        repo = str(tmp_path / "repo")
        os.makedirs(repo)
        init_git_repo(repo)
        env = {**os.environ, "HOME": str(tmp_path / "home")}
        subprocess.run(
            ["bash", INSTALL_SCRIPT], cwd=repo, env=env, capture_output=True, check=True
        )
        subprocess.run(
            ["bash", UNINSTALL_SCRIPT],
            cwd=repo,
            env=env,
            capture_output=True,
            check=True,
        )
        config_path = os.path.join(repo, ".pre-commit-config.yaml")
        if os.path.isfile(config_path):
            with open(config_path) as f:
                config = f.read()
            assert (
                "terminology-commit-msg" not in config
            ), "terminology-commit-msg must be removed from .pre-commit-config.yaml on uninstall"
