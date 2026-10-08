"""Доменные типы и константы, общие для сервисов и TUI."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

VERDICTS = ("ИЗУМИТЕЛЬНО", "ПОХВАЛЬНО", "ПРОХОДНЯК", "МУСОР")
METRIC_NAMES = ("Чистота кода", "Архитектура", "Уровень костылей")
INVERTED_METRICS = frozenset({"Уровень костылей"})  # для них больше = хуже
METRIC_MAX = 10


@dataclass(frozen=True)
class FileChange:
    path: str
    index: str  # статус в индексе (X из porcelain), " " — без изменений
    worktree: str  # статус в рабочей копии (Y из porcelain)
    orig_path: str | None = None  # для переименований

    @property
    def staged(self) -> bool:
        return self.index not in {" ", "?", "!"}

    @property
    def unstaged(self) -> bool:
        return self.worktree != " "


@dataclass(frozen=True)
class Commit:
    sha: str
    author: str
    date: str
    subject: str


@dataclass(frozen=True)
class Branch:
    name: str
    current: bool
    upstream: str
    track: str  # "[ahead 1, behind 2]" / "[gone]" / ""


@dataclass(frozen=True)
class CodeSample:
    source: str
    text: str
    truncated: bool


@dataclass(frozen=True)
class Review:
    verdict: str
    review: str
    metrics: dict[str, int]


@dataclass(frozen=True)
class DayCount:
    day: date
    count: int


@dataclass(frozen=True)
class BackendInfo:
    name: str
    available: bool
    hint: str  # как подключить или чем является
