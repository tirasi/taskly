from datetime import date

from app.recurrence import Recurrence, first_on_or_after, next_after, next_for_completion

TUE_THU = Recurrence("weekly", 1, [1, 3])


def test_weekly_multi_day_walk():
    d = date(2026, 10, 15)                       # Thursday
    assert next_after(TUE_THU, d) == date(2026, 10, 20)       # -> Tuesday
    assert next_after(TUE_THU, date(2026, 10, 20)) == date(2026, 10, 22)
    assert first_on_or_after(TUE_THU, date(2026, 10, 16)) == date(2026, 10, 20)


def test_every_other_week_skips_a_week():
    r = Recurrence("weekly", 2, [0])
    assert next_after(r, date(2026, 10, 19)) == date(2026, 11, 2)


def test_monthly_clamps_short_months():
    r = Recurrence("monthly", 1, [], 31)
    assert next_after(r, date(2026, 1, 31)) == date(2026, 2, 28)
    assert next_after(r, date(2026, 2, 28)) == date(2026, 3, 31)


def test_yearly_leap_day():
    assert next_after(Recurrence("yearly"), date(2028, 2, 29)) == date(2029, 2, 28)


def test_overdue_completion_skips_the_past():
    today = date(2026, 10, 15)
    daily = Recurrence("daily")
    assert next_for_completion(daily, date(2026, 10, 10), today) == date(2026, 10, 16)
    assert next_for_completion(TUE_THU, date(2026, 10, 13), today) == date(2026, 10, 20)   # Tue overdue -> Thu is today -> next Tue
    assert next_for_completion(daily, date(2026, 10, 20), today) == date(2026, 10, 21)     # completed early
