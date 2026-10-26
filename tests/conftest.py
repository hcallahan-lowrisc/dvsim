# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0

"""Fixtures shared by all the tests."""

import os

import pytest

# Variables through which git can be pointed at a repository other than the one it finds from
# the current directory.
_GIT_REPO_VARS = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_COMMON_DIR",
    "GIT_NAMESPACE",
    "GIT_PREFIX",
)


@pytest.fixture(autouse=True)
def _isolated_git(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the tests' git commands in the repositories that the tests make.

    Git hooks and `git rebase --exec` set GIT_DIR and friends, which would point the tests'
    git commands at the repository that the tests are run from. The user's and the system's
    git config (commit signing, hooks, templates) are left out too, and commits get a fixed
    author.
    """
    for var in _GIT_REPO_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for role in ("AUTHOR", "COMMITTER"):
        monkeypatch.setenv(f"GIT_{role}_NAME", "dvsim test")
        monkeypatch.setenv(f"GIT_{role}_EMAIL", "dvsim-test@example.com")
