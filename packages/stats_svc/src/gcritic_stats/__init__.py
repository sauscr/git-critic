"""gcritic stats_svc: активность по дням."""

from __future__ import annotations

from datetime import date

from gcritic_core.types import DayCount

from gcritic_stats.logic import daily_counts, window_start


class Stats:
    def __init__(self, days: int) -> None:
        self._days = days

    @property
    def days(self) -> int:
        return self._days

    def activity(self, commit_dates: list[date], today: date) -> list[DayCount]:
        return daily_counts(commit_dates, today, self._days)


__all__ = ["Stats", "daily_counts", "window_start"]
