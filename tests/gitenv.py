"""Subprocess environments for the fixture repos.

Git exports its own variables to every hook it runs: GIT_DIR, GIT_INDEX_FILE
(relative to the hook's working directory), GIT_WORK_TREE, GIT_AUTHOR_*,
GIT_CONFIG_PARAMETERS. They take precedence over a subprocess `cwd=`, so a test
that shells out to git while the suite itself runs inside a pre-commit hook acts on
the repo being committed rather than on its own tmp_path fixture — writing commits,
config and hooks into it. This repo's .pre-commit-config.yaml runs pytest in exactly
that position, so the fixtures scrub the environment instead of trusting cwd.

GIT_EXEC_PATH is kept: it locates git's own helper binaries and redirects nothing.
"""

import os

KEEP = {"GIT_EXEC_PATH"}


def clean_env(**overrides: str) -> dict:
    """os.environ with git's redirecting variables removed, plus any overrides."""
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("GIT_") or key in KEEP
    }
    env.update(overrides)
    return env
