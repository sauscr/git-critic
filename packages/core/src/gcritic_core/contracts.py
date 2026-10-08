"""Контракты сервисов. TUI знает только их; реализации подставляет apps/cli.

Методы принимают и возвращают простые данные (пути, строки, dataclass'ы),
чтобы любой сервис можно было вынести в процесс за JSON-RPC без изменения TUI.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Protocol

from gcritic_core.types import BackendInfo, Branch, CodeSample, Commit, DayCount, FileChange, Review


class GitService(Protocol):
    def ensure_repository(self, path: Path) -> Path:
        """Корень репозитория, содержащего path; CriticError, если это не репозиторий."""
        ...

    def has_commits(self, repo: Path) -> bool: ...

    def current_branch(self, repo: Path) -> str: ...

    def status(self, repo: Path) -> list[FileChange]: ...

    def diff(self, repo: Path, *, staged: bool = False, path: str | None = None) -> str:
        """Дифф рабочей копии (или индекса при staged), опционально по одному файлу."""
        ...

    def diff_head(self, repo: Path) -> str:
        """Все незакоммиченные изменения относительно HEAD."""
        ...

    def log(self, repo: Path, count: int) -> list[Commit]: ...

    def log_patches(self, repo: Path, count: int) -> str: ...

    def branches(self, repo: Path) -> list[Branch]: ...

    def commit_dates(self, repo: Path, since: date) -> list[date]:
        """Даты коммитов всех веток начиная с since (локальное время)."""
        ...


class CriticService(Protocol):
    @property
    def backend(self) -> str:
        """Текущий бэкенд (openai | codex | claude) или "", если доступных нет."""
        ...

    def backends(self) -> list[BackendInfo]: ...

    def use(self, name: str) -> None:
        """Переключить бэкенд; auto — выбрать заново. CriticError, если недоступен."""
        ...

    def build_sample(self, working_diff: str, recent_patches: str, commits: int) -> CodeSample: ...

    def review(self, sample: CodeSample) -> Review: ...


class StatsService(Protocol):
    @property
    def days(self) -> int: ...

    def activity(self, commit_dates: list[date], today: date) -> list[DayCount]: ...
