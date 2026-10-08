from datetime import date

from gcritic_core.types import DayCount
from gcritic_stats import Stats, window_start

TODAY = date(2026, 10, 8)


def test_window_start():
    assert window_start(TODAY, 7) == date(2026, 10, 2)
    assert window_start(TODAY, 1) == TODAY


def test_activity_counts_and_ignores_outside_window():
    dates = [TODAY, TODAY, date(2026, 10, 2), date(2026, 10, 1), date(2026, 10, 9)]
    days = Stats(7).activity(dates, TODAY)
    assert len(days) == 7
    assert days[0] == DayCount(date(2026, 10, 2), 1)
    assert days[-1] == DayCount(TODAY, 2)
    assert sum(d.count for d in days) == 3
