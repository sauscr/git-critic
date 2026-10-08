"""Общие фикстуры: временные git-репозитории."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

GIT_ENV = {
    "GIT_AUTHOR_NAME": "Tester",
    "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "Tester",
    "GIT_COMMITTER_EMAIL": "t@example.com",
}


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
        env={**__import__("os").environ, **GIT_ENV},
    ).stdout


def commit_file(repo: Path, name: str, content: str, message: str) -> None:
    (repo / name).write_text(content, encoding="utf-8")
    git(repo, "add", name)
    git(repo, "commit", "-q", "-m", message)


@pytest.fixture
def empty_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "empty"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    return repo


@pytest.fixture
def repo(empty_repo: Path) -> Path:
    commit_file(empty_repo, "app.py", "print('hi')\n", "feat: первый коммит")
    commit_file(empty_repo, "lib.py", "x = 1\n", "feat: библиотека")
    return empty_repo
