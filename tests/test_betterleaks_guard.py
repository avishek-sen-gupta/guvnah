"""Tests for the betterleaks-backed terminology guard.

Tests cover:
- blocklist-to-toml: converting blocklist.txt + blocklist-exclude.txt to a rules file
- check-terminology-bl: staged content scanning
- check-commit-msg-bl: commit message scanning
- scan-history-bl: history content + commit message scanning
- bd-guard-bl.sh: Beads PreToolUse hook
- installers/uninstallers
"""

import json
import os
import shutil
import stat
import subprocess

import pytest

pytestmark = pytest.mark.skipif(
    shutil.which("betterleaks") is None, reason="betterleaks not installed"
)

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BL_DIR = os.path.join(REPO_ROOT, "hooks", "betterleaks")
CONVERTER = os.path.join(BL_DIR, "blocklist-to-toml")
CHECK_TERMINOLOGY_BL = os.path.join(BL_DIR, "check-terminology-bl")
CHECK_COMMIT_MSG_BL = os.path.join(BL_DIR, "check-commit-msg-bl")
SCAN_HISTORY_BL = os.path.join(BL_DIR, "scan-history-bl")
BD_GUARD_BL = os.path.join(REPO_ROOT, "hooks", "bd-guard-bl.sh")
INSTALL_BL = os.path.join(REPO_ROOT, "install-betterleaks-guard.sh")
UNINSTALL_BL = os.path.join(REPO_ROOT, "uninstall-betterleaks-guard.sh")
INSTALL_BD_BL = os.path.join(REPO_ROOT, "install-bd-guard-bl.sh")
UNINSTALL_BD_BL = os.path.join(REPO_ROOT, "uninstall-bd-guard-bl.sh")


# ── helpers ──────────────────────────────────────────────────────


def git(repo: str, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout


def init_git_repo(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    git(path, "init", "-b", "main")
    git(path, "config", "user.email", "t@t.com")
    git(path, "config", "user.name", "T")
    git(path, "config", "core.hooksPath", "/dev/null")
    git(path, "commit", "--allow-empty", "-m", "init")
    return path


def commit_file(repo: str, filename: str, content: str, message: str) -> None:
    full = os.path.join(repo, filename)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w") as f:
        f.write(content)
    git(repo, "add", filename)
    git(repo, "commit", "-m", message)


def stage_content(repo: str, content: str, filename: str = "file.txt") -> None:
    full = os.path.join(repo, filename)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w") as f:
        f.write(content)
    git(repo, "add", filename)


def env_for(home: str) -> dict:
    return {**os.environ, "HOME": home}


def write_blocklist(tmp_path, patterns: list[str], excludes=None) -> str:
    """Create a fake HOME with blocklist.txt (and optional blocklist-exclude.txt)."""
    home = tmp_path / "home"
    git_config = home / ".config" / "git"
    git_config.mkdir(parents=True, exist_ok=True)
    (git_config / "blocklist.txt").write_text("\n".join(patterns) + "\n")
    if excludes is not None:
        (git_config / "blocklist-exclude.txt").write_text("\n".join(excludes) + "\n")
    return str(home)


def convert(home: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["python3", CONVERTER], env=env_for(home), capture_output=True, text=True
    )


def setup_rules(tmp_path, patterns: list[str], excludes=None) -> str:
    """Fake HOME with both blocklist.txt and a generated terminology.toml."""
    home = write_blocklist(tmp_path, patterns, excludes)
    result = convert(home)
    assert result.returncode == 0, result.stderr
    rules = os.path.join(home, ".config", "git", "terminology.toml")
    with open(rules, "w") as f:
        f.write(result.stdout)
    return home


def run_script(
    script: str, args: list[str], home: str, cwd: str, stdin: str = ""
) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", script, *args],
        env=env_for(home),
        cwd=cwd,
        input=stdin,
        capture_output=True,
        text=True,
    )


def scan_stdin(rules_toml: str, text: str) -> int:
    return subprocess.run(
        ["betterleaks", "stdin", "--no-banner", "-l", "error", "-c", rules_toml],
        input=text,
        capture_output=True,
        text=True,
    ).returncode


# ── blocklist-to-toml ────────────────────────────────────────────


class TestBlocklistToToml:
    def test_generated_rules_block_each_term_case_insensitively(self, tmp_path):
        home = setup_rules(tmp_path, ["zorblax", "quibbit"])
        rules = os.path.join(home, ".config", "git", "terminology.toml")
        assert scan_stdin(rules, "the ZORBLAX node\n") == 1
        assert scan_stdin(rules, "a Quibbit replica\n") == 1

    def test_generated_rules_allow_clean_text(self, tmp_path):
        home = setup_rules(tmp_path, ["zorblax"])
        rules = os.path.join(home, ".config", "git", "terminology.toml")
        assert scan_stdin(rules, "the primary node\n") == 0

    def test_regex_terms_keep_regex_semantics(self, tmp_path):
        home = setup_rules(tmp_path, ["quux[0-9]+"])
        rules = os.path.join(home, ".config", "git", "terminology.toml")
        assert scan_stdin(rules, "see QUUX42\n") == 1
        assert scan_stdin(rules, "quux alone\n") == 0

    def test_skips_comments_and_blank_lines(self, tmp_path):
        home = setup_rules(tmp_path, ["# a comment", "", "   ", "zorblax"])
        rules = os.path.join(home, ".config", "git", "terminology.toml")
        assert scan_stdin(rules, "a comment here\n") == 0
        assert scan_stdin(rules, "zorblax\n") == 1

    def test_fails_without_blocklist(self, tmp_path):
        home = tmp_path / "home"
        home.mkdir()
        result = convert(str(home))
        assert result.returncode != 0
        assert "blocklist" in result.stderr.lower()

    def test_fails_on_empty_blocklist(self, tmp_path):
        home = write_blocklist(tmp_path, ["# only comments"])
        result = convert(home)
        assert result.returncode != 0

    def test_rejects_term_that_would_break_toml_literal(self, tmp_path):
        home = write_blocklist(tmp_path, ["bad'''term"])
        result = convert(home)
        assert result.returncode != 0


# ── check-terminology-bl ─────────────────────────────────────────


class TestCheckTerminologyBl:
    @pytest.mark.parametrize(
        "content", ["connect to zorblax\n", "connect to ZORBLAX\n", "the Zorblax db\n"]
    )
    def test_blocks_term_in_any_case(self, tmp_path, content):
        repo = init_git_repo(str(tmp_path / "repo"))
        home = setup_rules(tmp_path, ["zorblax"])
        stage_content(repo, content)
        result = run_script(CHECK_TERMINOLOGY_BL, [], home, repo)
        assert result.returncode == 1

    def test_allows_clean_content(self, tmp_path):
        repo = init_git_repo(str(tmp_path / "repo"))
        home = setup_rules(tmp_path, ["zorblax"])
        stage_content(repo, "connect to primary\n")
        result = run_script(CHECK_TERMINOLOGY_BL, [], home, repo)
        assert result.returncode == 0

    def test_ignores_unstaged_content(self, tmp_path):
        repo = init_git_repo(str(tmp_path / "repo"))
        home = setup_rules(tmp_path, ["zorblax"])
        stage_content(repo, "clean\n")
        with open(os.path.join(repo, "file.txt"), "w") as f:
            f.write("zorblax\n")
        result = run_script(CHECK_TERMINOLOGY_BL, [], home, repo)
        assert result.returncode == 0

    def test_report_names_the_offending_file(self, tmp_path):
        repo = init_git_repo(str(tmp_path / "repo"))
        home = setup_rules(tmp_path, ["zorblax"])
        stage_content(repo, "zorblax\n", filename="offender.txt")
        result = run_script(CHECK_TERMINOLOGY_BL, [], home, repo)
        assert "offender.txt" in result.stdout + result.stderr

    @pytest.mark.parametrize(
        "exclude,filename",
        [
            ("docs", "docs/guide.txt"),
            ("*.md", "notes.md"),
            ("vendor/*", "vendor/x/y.txt"),
        ],
    )
    def test_excluded_paths_are_skipped(self, tmp_path, exclude, filename):
        repo = init_git_repo(str(tmp_path / "repo"))
        home = setup_rules(tmp_path, ["zorblax"], excludes=[exclude])
        stage_content(repo, "zorblax\n", filename=filename)
        result = run_script(CHECK_TERMINOLOGY_BL, [], home, repo)
        assert result.returncode == 0

    def test_exclusions_do_not_hide_other_files(self, tmp_path):
        repo = init_git_repo(str(tmp_path / "repo"))
        home = setup_rules(tmp_path, ["zorblax"], excludes=["docs"])
        stage_content(repo, "zorblax\n", filename="docs/guide.txt")
        stage_content(repo, "zorblax\n", filename="src/app.txt")
        result = run_script(CHECK_TERMINOLOGY_BL, [], home, repo)
        assert result.returncode == 1

    def test_allows_when_rules_file_missing(self, tmp_path):
        repo = init_git_repo(str(tmp_path / "repo"))
        home = write_blocklist(tmp_path, ["zorblax"])
        stage_content(repo, "zorblax\n")
        result = run_script(CHECK_TERMINOLOGY_BL, [], home, repo)
        assert result.returncode == 0
        assert "terminology.toml" in result.stderr


# ── check-commit-msg-bl ──────────────────────────────────────────


class TestCheckCommitMsgBl:
    def test_script_is_executable(self):
        assert os.stat(CHECK_COMMIT_MSG_BL).st_mode & stat.S_IXUSR

    @pytest.mark.parametrize("msg", ["fix zorblax branch\n", "Merge ZORBLAX in\n"])
    def test_blocks_term_in_message(self, tmp_path, msg):
        repo = init_git_repo(str(tmp_path / "repo"))
        home = setup_rules(tmp_path, ["zorblax"])
        msg_file = tmp_path / "COMMIT_EDITMSG"
        msg_file.write_text(msg)
        result = run_script(CHECK_COMMIT_MSG_BL, [str(msg_file)], home, repo)
        assert result.returncode == 1

    def test_allows_clean_message(self, tmp_path):
        repo = init_git_repo(str(tmp_path / "repo"))
        home = setup_rules(tmp_path, ["zorblax"])
        msg_file = tmp_path / "COMMIT_EDITMSG"
        msg_file.write_text("fix primary branch\n")
        result = run_script(CHECK_COMMIT_MSG_BL, [str(msg_file)], home, repo)
        assert result.returncode == 0

    def test_errors_without_message_file(self, tmp_path):
        repo = init_git_repo(str(tmp_path / "repo"))
        home = setup_rules(tmp_path, ["zorblax"])
        result = run_script(CHECK_COMMIT_MSG_BL, [], home, repo)
        assert result.returncode != 0


# ── scan-history-bl ──────────────────────────────────────────────


class TestScanHistoryBl:
    def test_finds_term_in_content_removed_later(self, tmp_path):
        repo = init_git_repo(str(tmp_path / "repo"))
        home = setup_rules(tmp_path, ["zorblax"])
        commit_file(repo, "a.txt", "zorblax\n", "add a")
        commit_file(repo, "a.txt", "primary\n", "clean a")
        result = run_script(SCAN_HISTORY_BL, [], home, repo)
        assert result.returncode == 1
        assert "a.txt" in result.stdout + result.stderr

    def test_finds_term_only_in_commit_message(self, tmp_path):
        repo = init_git_repo(str(tmp_path / "repo"))
        home = setup_rules(tmp_path, ["zorblax"])
        commit_file(repo, "a.txt", "clean\n", "merge ZORBLAX work")
        sha = git(repo, "rev-parse", "--short", "HEAD").strip()
        result = run_script(SCAN_HISTORY_BL, [], home, repo)
        assert result.returncode == 1
        assert sha in result.stdout + result.stderr

    def test_finds_term_in_commit_message_body(self, tmp_path):
        repo = init_git_repo(str(tmp_path / "repo"))
        home = setup_rules(tmp_path, ["zorblax"])
        commit_file(repo, "a.txt", "clean\n", "subject\n\nbody mentions zorblax")
        result = run_script(SCAN_HISTORY_BL, [], home, repo)
        assert result.returncode == 1

    def test_clean_history_passes(self, tmp_path):
        repo = init_git_repo(str(tmp_path / "repo"))
        home = setup_rules(tmp_path, ["zorblax"])
        commit_file(repo, "a.txt", "primary\n", "add a")
        result = run_script(SCAN_HISTORY_BL, [], home, repo)
        assert result.returncode == 0


# ── bd-terminology-guard-bl.sh ───────────────────────────────────


def bd_payload(command: str) -> str:
    return json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})


class TestBdGuardBl:
    def test_blocks_bd_create_with_term(self, tmp_path):
        home = setup_rules(tmp_path, ["zorblax"])
        result = run_script(
            BD_GUARD_BL, [], home, str(tmp_path), bd_payload('bd create "fix ZORBLAX"')
        )
        assert result.returncode == 2
        out = json.loads(result.stdout)
        assert out["continue"] is False
        assert "ZORBLAX" in out["stopReason"]

    @pytest.mark.parametrize(
        "command",
        [
            'bd update x --notes "zorblax"',
            'bd comment x "zorblax"',
            'bd dep relate a "zorblax"',
        ],
    )
    def test_blocks_other_write_subcommands(self, tmp_path, command):
        home = setup_rules(tmp_path, ["zorblax"])
        result = run_script(BD_GUARD_BL, [], home, str(tmp_path), bd_payload(command))
        assert result.returncode == 2

    def test_allows_clean_bd_create(self, tmp_path):
        home = setup_rules(tmp_path, ["zorblax"])
        result = run_script(
            BD_GUARD_BL, [], home, str(tmp_path), bd_payload('bd create "fix primary"')
        )
        assert result.returncode == 0
        assert result.stdout == ""

    def test_ignores_bd_read_commands(self, tmp_path):
        home = setup_rules(tmp_path, ["zorblax"])
        result = run_script(
            BD_GUARD_BL, [], home, str(tmp_path), bd_payload("bd list | grep zorblax")
        )
        assert result.returncode == 0

    def test_ignores_non_bd_commands(self, tmp_path):
        home = setup_rules(tmp_path, ["zorblax"])
        result = run_script(
            BD_GUARD_BL, [], home, str(tmp_path), bd_payload("git checkout zorblax")
        )
        assert result.returncode == 0

    def test_allows_when_rules_file_missing(self, tmp_path):
        home = write_blocklist(tmp_path, ["zorblax"])
        result = run_script(
            BD_GUARD_BL, [], home, str(tmp_path), bd_payload('bd create "zorblax"')
        )
        assert result.returncode == 0


# ── install / uninstall: git hooks ───────────────────────────────


def read_config(repo: str) -> str:
    path = os.path.join(repo, ".pre-commit-config.yaml")
    if not os.path.isfile(path):
        return ""
    with open(path) as f:
        return f.read()


def run_installer(script: str, repo: str, home: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", script], cwd=repo, env=env_for(home), capture_output=True, text=True
    )


class TestInstallBetterleaksGuard:
    def test_installs_scripts(self, tmp_path):
        repo = init_git_repo(str(tmp_path / "repo"))
        home = str(tmp_path / "home")
        result = run_installer(INSTALL_BL, repo, home)
        assert result.returncode == 0, result.stderr
        for name in ["check-terminology-bl", "check-commit-msg-bl", "scan-history-bl"]:
            path = os.path.join(repo, "precommit-scripts", name)
            assert os.path.isfile(path), name
            assert os.stat(path).st_mode & stat.S_IXUSR, name

    def test_wires_both_hooks_once_when_run_twice(self, tmp_path):
        repo = init_git_repo(str(tmp_path / "repo"))
        home = str(tmp_path / "home")
        run_installer(INSTALL_BL, repo, home)
        result = run_installer(INSTALL_BL, repo, home)
        assert result.returncode == 0
        config = read_config(repo)
        assert config.count("id: bl-terminology-guard\n") == 1
        assert config.count("id: bl-terminology-commit-msg\n") == 1

    def test_commit_msg_hook_runs_at_commit_msg_stage(self, tmp_path):
        repo = init_git_repo(str(tmp_path / "repo"))
        run_installer(INSTALL_BL, repo, str(tmp_path / "home"))
        config = read_config(repo)
        block = config.split("id: bl-terminology-commit-msg")[1].split("- id:")[0]
        assert "stages: [commit-msg]" in block

    def test_warns_when_rules_file_missing(self, tmp_path):
        repo = init_git_repo(str(tmp_path / "repo"))
        result = run_installer(INSTALL_BL, repo, str(tmp_path / "home"))
        assert "terminology.toml" in result.stdout

    def test_refuses_outside_git_repo(self, tmp_path):
        result = run_installer(INSTALL_BL, str(tmp_path), str(tmp_path / "home"))
        assert result.returncode != 0


class TestUninstallBetterleaksGuard:
    def test_removes_scripts_and_hooks(self, tmp_path):
        repo = init_git_repo(str(tmp_path / "repo"))
        home = str(tmp_path / "home")
        run_installer(INSTALL_BL, repo, home)
        result = run_installer(UNINSTALL_BL, repo, home)
        assert result.returncode == 0, result.stderr
        assert not os.path.exists(os.path.join(repo, "precommit-scripts"))
        assert "bl-terminology" not in read_config(repo)

    def test_preserves_unrelated_hooks(self, tmp_path):
        repo = init_git_repo(str(tmp_path / "repo"))
        home = str(tmp_path / "home")
        with open(os.path.join(repo, ".pre-commit-config.yaml"), "w") as f:
            f.write(
                "repos:\n  - repo: local\n    hooks:\n"
                "      - id: pytest\n        name: pytest\n"
                "        entry: pytest\n        language: system\n"
            )
        run_installer(INSTALL_BL, repo, home)
        run_installer(UNINSTALL_BL, repo, home)
        config = read_config(repo)
        assert "id: pytest\n" in config
        assert "bl-terminology" not in config


# ── install / uninstall: bd guard ────────────────────────────────


def claude_project(tmp_path) -> str:
    project = tmp_path / "project"
    (project / ".claude").mkdir(parents=True)
    return str(project)


def settings_commands(project: str) -> list[str]:
    with open(os.path.join(project, ".claude", "settings.json")) as f:
        settings = json.load(f)
    return [
        h["command"]
        for entry in settings.get("hooks", {}).get("PreToolUse", [])
        for h in entry["hooks"]
    ]


class TestInstallBdGuardBl:
    def test_installs_hook_and_wires_once(self, tmp_path):
        project = claude_project(tmp_path)
        home = str(tmp_path / "home")
        run_installer(INSTALL_BD_BL, project, home)
        result = run_installer(INSTALL_BD_BL, project, home)
        assert result.returncode == 0, result.stderr
        hook = os.path.join(
            home, ".claude", "plugins", "guvnah", "hooks", "bd-guard-bl.sh"
        )
        assert os.stat(hook).st_mode & stat.S_IXUSR
        commands = settings_commands(project)
        assert sum("bd-guard-bl" in c for c in commands) == 1

    def test_uninstall_removes_hook_and_keeps_unrelated_hooks(self, tmp_path):
        project = claude_project(tmp_path)
        home = str(tmp_path / "home")
        with open(os.path.join(project, ".claude", "settings.json"), "w") as f:
            json.dump(
                {
                    "hooks": {
                        "PreToolUse": [
                            {"hooks": [{"type": "command", "command": "other.sh"}]}
                        ]
                    }
                },
                f,
            )
        run_installer(INSTALL_BD_BL, project, home)
        result = run_installer(UNINSTALL_BD_BL, project, home)
        assert result.returncode == 0, result.stderr
        assert settings_commands(project) == ["other.sh"]
        hook_dir = os.path.join(home, ".claude", "plugins", "guvnah", "hooks")
        assert not os.path.exists(os.path.join(hook_dir, "bd-guard-bl.sh"))
