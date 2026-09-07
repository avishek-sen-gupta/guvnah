"""Tests for the pipefail-guard PreToolUse hook."""

import json
import os
import subprocess

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
HOOKS_DIR = os.path.join(REPO_ROOT, "hooks")
HOOK = os.path.join(HOOKS_DIR, "pipefail-guard.sh")
INSTALL_SCRIPT = os.path.join(REPO_ROOT, "install-pipefail-guard.sh")
UNINSTALL_SCRIPT = os.path.join(REPO_ROOT, "uninstall-pipefail-guard.sh")


def run_hook(tool_name, tool_input):
    payload = json.dumps({"tool_name": tool_name, "tool_input": tool_input})
    return subprocess.run(
        ["bash", HOOK],
        input=payload,
        capture_output=True,
        text=True,
    )


class TestPipefailGuard:
    def test_prepends_pipefail_to_bash(self):
        result = run_hook("Bash", {"command": "pytest tests/"})
        assert result.returncode == 0
        parsed = json.loads(result.stdout)
        hook_out = parsed["hookSpecificOutput"]
        assert hook_out["permissionDecision"] == "allow"
        assert hook_out["updatedInput"]["command"] == "set -o pipefail; pytest tests/"

    def test_skips_non_bash_tools(self):
        result = run_hook("Write", {"file_path": "x.py"})
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_skips_if_already_has_pipefail(self):
        result = run_hook("Bash", {"command": "set -o pipefail; pytest"})
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_hook_is_executable(self):
        assert os.access(HOOK, os.X_OK)

    def test_preserves_original_command(self):
        cmd = "git status && echo done"
        result = run_hook("Bash", {"command": cmd})
        parsed = json.loads(result.stdout)
        assert parsed["hookSpecificOutput"]["updatedInput"]["command"].endswith(cmd)

    def test_handles_quotes_in_command(self):
        cmd = 'echo "got $?"'
        result = run_hook("Bash", {"command": cmd})
        assert result.returncode == 0
        parsed = json.loads(result.stdout)  # must be valid JSON
        assert (
            parsed["hookSpecificOutput"]["updatedInput"]["command"]
            == f"set -o pipefail; {cmd}"
        )


# ── install / uninstall ──────────────────────────────────────────


def make_project(tmp_path):
    """A bare Claude Code project root: a directory containing .claude/."""
    project = tmp_path / "project"
    (project / ".claude").mkdir(parents=True)
    return str(project)


def run_script(script, cwd):
    return subprocess.run(["bash", script], cwd=cwd, capture_output=True, text=True)


def read_settings(project):
    with open(os.path.join(project, ".claude", "settings.json")) as f:
        return json.load(f)


def pipefail_entries(settings):
    return [
        e
        for e in settings.get("hooks", {}).get("PreToolUse", [])
        if any("pipefail-guard" in h.get("command", "") for h in e.get("hooks", []))
    ]


class TestInstallScript:
    """install-pipefail-guard.sh must copy the hook and wire it as a Bash PreToolUse hook."""

    def test_copies_hook_into_project(self, tmp_path):
        project = make_project(tmp_path)
        result = run_script(INSTALL_SCRIPT, project)
        assert result.returncode == 0, f"install failed: {result.stderr}"
        installed = os.path.join(project, ".claude", "hooks", "pipefail-guard.sh")
        assert os.path.isfile(installed), "hook must be copied to .claude/hooks/"
        assert os.access(installed, os.X_OK), "installed hook must be executable"

    def test_wires_pretooluse_hook_with_bash_matcher(self, tmp_path):
        project = make_project(tmp_path)
        run_script(INSTALL_SCRIPT, project)
        entries = pipefail_entries(read_settings(project))
        assert len(entries) == 1, "pipefail guard must be wired exactly once"
        assert (
            entries[0]["matcher"] == "Bash"
        ), "pipefail guard must only match the Bash tool"

    def test_installed_hook_rewrites_commands(self, tmp_path):
        project = make_project(tmp_path)
        run_script(INSTALL_SCRIPT, project)
        installed = os.path.join(project, ".claude", "hooks", "pipefail-guard.sh")
        result = subprocess.run(
            ["bash", installed],
            input=json.dumps({"tool_name": "Bash", "tool_input": {"command": "ls"}}),
            capture_output=True,
            text=True,
        )
        parsed = json.loads(result.stdout)
        assert (
            parsed["hookSpecificOutput"]["updatedInput"]["command"]
            == "set -o pipefail; ls"
        )

    def test_install_is_idempotent(self, tmp_path):
        project = make_project(tmp_path)
        run_script(INSTALL_SCRIPT, project)
        result = run_script(INSTALL_SCRIPT, project)
        assert result.returncode == 0, "second install must not fail"
        entries = pipefail_entries(read_settings(project))
        assert len(entries) == 1, "re-installing must not duplicate the hook entry"

    def test_preserves_unrelated_settings(self, tmp_path):
        project = make_project(tmp_path)
        settings_path = os.path.join(project, ".claude", "settings.json")
        with open(settings_path, "w") as f:
            json.dump(
                {
                    "model": "opus",
                    "hooks": {
                        "PreToolUse": [
                            {
                                "matcher": "Write",
                                "hooks": [{"type": "command", "command": "other.sh"}],
                            }
                        ]
                    },
                },
                f,
            )
        run_script(INSTALL_SCRIPT, project)
        settings = read_settings(project)
        assert settings["model"] == "opus", "unrelated settings keys must survive"
        commands = [
            h["command"] for e in settings["hooks"]["PreToolUse"] for h in e["hooks"]
        ]
        assert "other.sh" in commands, "pre-existing PreToolUse hooks must survive"

    def test_fails_without_claude_directory(self, tmp_path):
        project = str(tmp_path / "not-a-project")
        os.makedirs(project)
        result = run_script(INSTALL_SCRIPT, project)
        assert (
            result.returncode != 0
        ), "install must refuse a directory with no .claude/"


class TestUninstallScript:
    """uninstall-pipefail-guard.sh must remove the hook file and its settings entry."""

    def test_removes_hook_file(self, tmp_path):
        project = make_project(tmp_path)
        run_script(INSTALL_SCRIPT, project)
        result = run_script(UNINSTALL_SCRIPT, project)
        assert result.returncode == 0, f"uninstall failed: {result.stderr}"
        assert not os.path.exists(
            os.path.join(project, ".claude", "hooks", "pipefail-guard.sh")
        ), "hook file must be deleted"

    def test_removes_settings_entry(self, tmp_path):
        project = make_project(tmp_path)
        run_script(INSTALL_SCRIPT, project)
        run_script(UNINSTALL_SCRIPT, project)
        assert (
            pipefail_entries(read_settings(project)) == []
        ), "pipefail guard entry must be gone from settings.json"

    def test_leaves_unrelated_hooks_wired(self, tmp_path):
        project = make_project(tmp_path)
        settings_path = os.path.join(project, ".claude", "settings.json")
        with open(settings_path, "w") as f:
            json.dump(
                {
                    "hooks": {
                        "PreToolUse": [
                            {
                                "matcher": "Write",
                                "hooks": [{"type": "command", "command": "other.sh"}],
                            }
                        ]
                    }
                },
                f,
            )
        run_script(INSTALL_SCRIPT, project)
        run_script(UNINSTALL_SCRIPT, project)
        settings = read_settings(project)
        commands = [
            h["command"] for e in settings["hooks"]["PreToolUse"] for h in e["hooks"]
        ]
        assert commands == ["other.sh"], "only the pipefail entry must be removed"

    def test_uninstall_is_idempotent(self, tmp_path):
        project = make_project(tmp_path)
        run_script(INSTALL_SCRIPT, project)
        run_script(UNINSTALL_SCRIPT, project)
        result = run_script(UNINSTALL_SCRIPT, project)
        assert result.returncode == 0, "uninstalling twice must not fail"
