"""GitCli — реализация GitService поверх консольного git."""

from __future__ import annotations

import subprocess
from datetime import date
from pathlib import Path

from gcritic_core.errors import CriticError
from gcritic_core.types import Branch, Commit, FileChange

from gcritic_git import logic

GIT_URL = "https://git-scm.com/downloads"


def _run(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", "-C", str(repo), "-c", "core.quotepath=false", *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except FileNotFoundError as exc:
        raise CriticError(f"Git не найден в PATH. Установи его: {GIT_URL}") from exc


def _out(repo: Path, *args: str) -> str:
    result = _run(repo, *args)
    if result.returncode != 0:
        details = result.stderr.strip() or f"код выхода {result.returncode}"
        raise CriticError(f"git {' '.join(args)} упал: {details}")
    return result.stdout


class GitCli:
    def ensure_repository(self, path: Path) -> Path:
        if not path.is_dir():
            raise CriticError(f"Папка не найдена: {path}")
        result = _run(path, "rev-parse", "--show-toplevel")
        if result.returncode != 0:
            raise CriticError(f"Это не Git-репозиторий: {path}")
        return Path(result.stdout.strip()).resolve()

    def has_commits(self, repo: Path) -> bool:
        return _run(repo, "rev-parse", "--verify", "--quiet", "HEAD").returncode == 0

    def current_branch(self, repo: Path) -> str:
        result = _run(repo, "symbolic-ref", "--short", "-q", "HEAD")
        if result.returncode == 0:
            return result.stdout.strip()
        sha = _run(repo, "rev-parse", "--short", "HEAD").stdout.strip()
        return f"(detached {sha})" if sha else "(нет ветки)"

    def status(self, repo: Path) -> list[FileChange]:
        return logic.parse_status(_out(repo, "status", "--porcelain=v1", "-z", "-uall"))

    def diff(self, repo: Path, *, staged: bool = False, path: str | None = None) -> str:
        args = ["diff", "--no-color"]
        if staged:
            args.append("--cached")
        if path:
            args += ["--", path]
        return _out(repo, *args)

    def diff_head(self, repo: Path) -> str:
        if not self.has_commits(repo):
            return _out(repo, "diff", "--cached", "--no-color")
        return _out(repo, "diff", "HEAD", "--no-color")

    def log(self, repo: Path, count: int) -> list[Commit]:
        if not self.has_commits(repo):
            return []
        return logic.parse_log(
            _out(repo, "log", "-n", str(count), logic.LOG_FORMAT, logic.LOG_DATE)
        )

    def log_patches(self, repo: Path, count: int) -> str:
        if not self.has_commits(repo):
            return ""
        return _out(repo, "log", "-n", str(count), "-p", "--no-color")

    def branches(self, repo: Path) -> list[Branch]:
        return logic.parse_branches(_out(repo, "for-each-ref", logic.BRANCH_FORMAT, "refs/heads"))

    def commit_dates(self, repo: Path, since: date) -> list[date]:
        if not self.has_commits(repo):
            return []
        output = _out(
            repo,
            "log",
            "--all",
            f"--since={since.isoformat()} 00:00",
            "--pretty=format:%ad",
            "--date=format-local:%Y-%m-%d",
        )
        return logic.parse_dates(output)
