"""Recurrence rules: the "every tuesday, thursday" part of the app.

A rule is a small value object; all the calendar maths lives here so it can be tested alone.
Weekdays follow Python's convention: Monday = 0 ... Sunday = 6.
"""
from __future__ import annotations

import calendar
import json
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta

WD_SHORT = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


@dataclass
class Recurrence:
    freq: str                       # "daily" | "weekly" | "monthly" | "yearly"
    interval: int = 1               # every N days/weeks/months/years
    byweekday: list[int] = field(default_factory=list)   # weekly only, e.g. [1, 3] = Tue, Thu
    bymonthday: int | None = None   # monthly only, e.g. 15

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @staticmethod
    def from_json(raw: str | None) -> "Recurrence | None":
        if not raw:
            return None
        d = json.loads(raw)
        return Recurrence(d["freq"], d.get("interval", 1), d.get("byweekday", []), d.get("bymonthday"))


def _add_months(d: date, months: int, day: int | None = None) -> date:
    m = d.month - 1 + months
    y, m = d.year + m // 12, m % 12 + 1
    want = day or d.day
    return date(y, m, min(want, calendar.monthrange(y, m)[1]))  # Jan 31 + 1 month -> Feb 28


def first_on_or_after(rec: Recurrence, start: date) -> date:
    """First date >= start that fits the rule (used when a recurring task is created)."""
    if rec.freq == "weekly" and rec.byweekday:
        for i in range(7):
            d = start + timedelta(days=i)
            if d.weekday() in rec.byweekday:
                return d
    if rec.freq == "monthly" and rec.bymonthday:
        this_month = _add_months(start.replace(day=1), 0, rec.bymonthday)
        return this_month if this_month >= start else _add_months(start.replace(day=1), 1, rec.bymonthday)
    return start


def next_after(rec: Recurrence, d: date) -> date:
    """Next occurrence strictly after d."""
    n = max(rec.interval, 1)
    if rec.freq == "daily":
        return d + timedelta(days=n)
    if rec.freq == "weekly":
        if not rec.byweekday:
            return d + timedelta(weeks=n)
        days = sorted(rec.byweekday)
        week_start = d - timedelta(days=d.weekday())
        for wd in days:                                  # later this week?
            if wd > d.weekday():
                return week_start + timedelta(days=wd)
        return week_start + timedelta(weeks=n, days=days[0])   # first slot of the next active week
    if rec.freq == "monthly":
        return _add_months(d, n, rec.bymonthday)
    if rec.freq == "yearly":
        return _add_months(d, 12 * n)
    raise ValueError(f"unknown freq {rec.freq}")


def next_for_completion(rec: Recurrence, due: date, today: date) -> date:
    """Where a recurring task moves to when ticked off.

    Overdue tasks skip any occurrences that are already in the past, so ticking off
    last week's "every day" task doesn't leave it overdue again immediately.
    """
    nxt = next_after(rec, due)
    if due <= today:
        while nxt <= today:
            nxt = next_after(rec, nxt)
    return nxt


def _ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def fmt_time(hhmm: str | None) -> str:
    if not hhmm:
        return ""
    h, m = map(int, hhmm.split(":"))
    return f"{h % 12 or 12}:{m:02d} {'AM' if h < 12 else 'PM'}"


def describe(rec: Recurrence, due_time: str | None = None) -> str:
    n = rec.interval
    if rec.freq == "daily":
        text = "Every day" if n == 1 else f"Every {n} days"
    elif rec.freq == "weekly":
        days = sorted(rec.byweekday)
        if days == [0, 1, 2, 3, 4] and n == 1:
            text = "Every weekday"
        elif days == [5, 6] and n == 1:
            text = "Every weekend"
        elif days:
            base = ", ".join(WD_SHORT[d] for d in days)
            text = f"Every {base}" if n == 1 else f"Every {n} weeks on {base}"
        else:
            text = "Every week" if n == 1 else f"Every {n} weeks"
    elif rec.freq == "monthly":
        text = "Every month" if n == 1 else f"Every {n} months"
        if rec.bymonthday:
            text += f" on the {_ordinal(rec.bymonthday)}"
    else:
        text = "Every year" if n == 1 else f"Every {n} years"
    return f"{text} at {fmt_time(due_time)}" if due_time else text
