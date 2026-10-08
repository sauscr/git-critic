"""Статистика активности: чистые функции."""

from __future__ import annotations

from collections import Counter
from datetime import date, timedelta

from gcritic_core.types import DayCount


def window_start(today: date, days: int) -> date:
    return today - timedelta(days=days - 1)


def daily_counts(commit_dates: list[date], today: date, days: int) -> list[DayCount]:
    """Коммиты по дням за последние days дней, включая сегодня; пустые дни — с нулём."""
    start = window_start(today, days)
    counter = Counter(commit_dates)
    return [DayCount(day, counter[day]) for day in (start + timedelta(n) for n in range(days))]
