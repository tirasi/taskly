"""Natural-language task parser (rule based, deterministic, no network).

"set a reminder for every tuesday, thursday 5pm running"
    -> title "Running", recurrence weekly [Tue, Thu], time 17:00, first due = next Tue/Thu

The cloud-AI layer (ai.py) does the *understanding* of speech; this module turns the
cleaned-up phrase into exact dates, times and recurrence rules, so the scheduling logic
is always the same tested code no matter how the task was entered.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from .recurrence import Recurrence, _add_months, first_on_or_after

WD_NAMES = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
NUM_WORDS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
             "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}

_I = re.I
_WD = r"\b(?:mon(?:day)?|tue(?:s(?:day)?)?|wed(?:s|nesday)?|thu(?:r(?:s(?:day)?)?)?|fri(?:day)?|sat(?:urday)?|sun(?:day)?)\b"
_SEP = r"(?:\s*(?:,|&|and)\s*(?:and\s+)?|\s+)"
_WDLIST = rf"{_WD}(?:{_SEP}{_WD})*"
_RANGE = rf"(?P<ra>{_WD})\s*(?:-|–|to|through|thru|till|until)\s*(?P<rb>{_WD})"
_PLURAL = r"\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)s\b"
_MONTH = r"(?P<mon>jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"

# ---- leading "set a reminder for / remind me to / add a task" noise ----
LEAD = re.compile(
    r"^\s*(?:please\s+)?(?:"
    r"(?:(?:can|could)\s+you\s+)?(?:set|create|add|make|schedule)\s+(?:me\s+)?(?:up\s+)?(?:a|an|the|my)?\s*(?:new\s+)?"
    r"(?:reminders?|remainders?|tasks?|to-?dos?)\s*(?:for|to|about|called|named|:)?"
    r"|remind\s+me\s*(?:to|about|of)?"
    r")\s*", _I)

RX_PRIORITY = re.compile(r"(?<!\w)(?:p([1-4])|priority\s*([1-4]))\b", _I)
RX_PROJECT = re.compile(r"(?<!\w)#([\w-]+)", _I)

# ---- recurrence ----
RX_MONTH_DAY_OF = re.compile(r"(?:\bon\s+)?\bthe\s+(?P<d>\d{1,2})(?:st|nd|rd|th)\s+of\s+(?:every|each)\s+month\b", _I)
RX_EVERY_MONTH = re.compile(r"\b(?:every|each)\s+(?:(?P<n>\d+|other)\s+)?months?\b(?:\s+on(?:\s+the)?\s+(?P<d>\d{1,2})(?:st|nd|rd|th)?\b)?", _I)
RX_EVERY_NTH = re.compile(r"\b(?:every|each)\s+(?P<d>\d{1,2})(?:st|nd|rd|th)\b", _I)
RX_WORKDAYS = re.compile(r"\b(?:(?:every|each)\s+(?:week\s?day|work\s?day)s?|weekdays)\b", _I)
RX_WEEKEND = re.compile(r"\b(?:every|each)\s+weekends?\b", _I)
RX_EVERY_WD = re.compile(rf"\b(?:every|each)\s+(?:(?P<o>other|second)\s+)?(?:(?P<range>{_RANGE})|(?P<list>{_WDLIST}))", _I)
RX_EVERY_UNIT = re.compile(r"\b(?:every|each)\s+(?:(?P<n>\d+)\s*|(?P<o>other|second)\s+)?(?P<u>day|week|month|year)s?\b", _I)
RX_ADVERB = re.compile(r"\b(?P<a>daily|weekly|monthly|yearly|annually)\b", _I)
RX_EVERY_PART = re.compile(r"\bevery\s+(?P<p>morning|afternoon|evening|night)\b", _I)
RX_PLURAL_WD = re.compile(rf"(?:\bon\s+)?(?P<list>{_PLURAL}(?:{_SEP}{_PLURAL})*)", _I)
RX_ON_WD_LIST = re.compile(rf"(?:\bon\s+)?(?P<list>{_WDLIST})", _I)

# ---- time of day ----
RX_DAYPART = re.compile(r"\b(?:this\s+(?P<p>morning|afternoon|evening)|(?P<t>tonight))\b", _I)
RX_T_COLON = re.compile(r"(?:\bat\s+)?\b(?P<h>\d{1,2}):(?P<m>\d{2})\s*(?P<ap>[ap]\.?m\.?)?(?!\w)", _I)
RX_T_AMPM = re.compile(r"(?:\bat\s+)?\b(?P<h>\d{1,2})\s*(?P<ap>[ap]\.?m\.?)(?!\w)", _I)
RX_T_NOON = re.compile(r"\b(?:at\s+)?(?P<w>noon|midday|midnight)\b", _I)
RX_T_AT = re.compile(r"\bat\s+(?P<h>\d{1,2})\b(?![\d:/-])(?!\s*(?:st|nd|rd|th)\b)", _I)

# ---- dates ----
RX_ISO = re.compile(r"\b(?P<y>\d{4})-(?P<m>\d{2})-(?P<d>\d{2})\b")
RX_IN = re.compile(r"\bin\s+(?P<n>\d+|a|an|one|two|three|four|five|six|seven|eight|nine|ten)\s*(?P<u>minutes?|mins?|hours?|hrs?|days?|weeks?|months?)\b", _I)
RX_DAY_AFTER = re.compile(r"\bday\s+after\s+tomorrow\b", _I)
RX_TOMORROW = re.compile(r"\b(?:tomorrow|tmrw|tmr)\b", _I)
RX_YESTERDAY = re.compile(r"\byesterday\b", _I)
RX_TODAY = re.compile(r"\btoday\b", _I)
RX_NEXT_WEEK = re.compile(r"\bnext\s+week\b", _I)
RX_WEEKEND_DATE = re.compile(r"\b(?:this|next|on\s+the)\s+weekend\b", _I)
RX_DMY = re.compile(rf"\b(?P<d>\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?{_MONTH}\b", _I)
RX_MDY = re.compile(rf"\b{_MONTH}\s+(?P<d>\d{{1,2}})(?:st|nd|rd|th)?\b", _I)
RX_THE_NTH = re.compile(r"(?:\bon\s+)?\bthe\s+(?P<d>\d{1,2})(?:st|nd|rd|th)\b", _I)
RX_WEEKDAY = re.compile(rf"(?:\b(?:on|this|next|coming)\s+)?(?P<wd>{_WD})", _I)


@dataclass
class Parsed:
    title: str
    due_date: date | None = None
    due_time: str | None = None          # "HH:MM" 24h
    recurrence: Recurrence | None = None
    priority: int = 4
    project: str | None = None
    chips: list[dict] = field(default_factory=list)   # what was understood, for the UI preview


def _take(rx: re.Pattern, s: str):
    m = rx.search(s)
    return (m, s[:m.start()] + " " + s[m.end():]) if m else (None, s)


def _wd_indices(text: str) -> list[int]:
    return sorted({WD_NAMES.index(t[:3].lower()) for t in re.findall(_WD, text, _I)})


def _range_indices(a: str, b: str) -> list[int]:
    i, j = WD_NAMES.index(a[:3].lower()), WD_NAMES.index(b[:3].lower())
    return list(range(i, j + 1)) if i <= j else list(range(i, 7)) + list(range(0, j + 1))


# ------------------------------------------------------------------ recurrence
def _parse_recurrence(s: str):
    """Returns (Recurrence | None, remaining text, matched phrase, default time)."""
    m, r = _take(RX_MONTH_DAY_OF, s)
    if m:
        return Recurrence("monthly", 1, [], int(m["d"])), r, m.group(0).strip(), None

    m, r = _take(RX_EVERY_MONTH, s)
    if m:
        n = m["n"]
        interval = 2 if n and n.lower() == "other" else int(n) if n else 1
        return Recurrence("monthly", interval, [], int(m["d"]) if m["d"] else None), r, m.group(0).strip(), None

    m, r = _take(RX_EVERY_NTH, s)
    if m:
        return Recurrence("monthly", 1, [], int(m["d"])), r, m.group(0).strip(), None

    m, r = _take(RX_WORKDAYS, s)
    if m:
        return Recurrence("weekly", 1, [0, 1, 2, 3, 4]), r, m.group(0).strip(), None

    m, r = _take(RX_WEEKEND, s)
    if m:
        return Recurrence("weekly", 1, [5, 6]), r, m.group(0).strip(), None

    m, r = _take(RX_EVERY_WD, s)
    if m:
        days = _range_indices(m["ra"], m["rb"]) if m["range"] else _wd_indices(m["list"])
        return Recurrence("weekly", 2 if m["o"] else 1, days), r, m.group(0).strip(), None

    m, r = _take(RX_EVERY_UNIT, s)
    if m:
        freq = {"day": "daily", "week": "weekly", "month": "monthly", "year": "yearly"}[m["u"].lower()]
        interval = 2 if m["o"] else int(m["n"]) if m["n"] else 1
        rec, phrase = Recurrence(freq, interval), m.group(0).strip()
        if freq == "weekly":                                  # "every 2 weeks on monday"
            m2, r2 = _take(RX_ON_WD_LIST, r)
            if m2:
                rec.byweekday, r, phrase = _wd_indices(m2["list"]), r2, f"{phrase} {m2.group(0).strip()}"
        return rec, r, phrase, None

    m, r = _take(RX_ADVERB, s)
    if m:
        freq = {"daily": "daily", "weekly": "weekly", "monthly": "monthly", "yearly": "yearly", "annually": "yearly"}[m["a"].lower()]
        rec, phrase = Recurrence(freq), m.group(0).strip()
        if freq == "weekly":                                  # "weekly on friday"
            m2, r2 = _take(RX_ON_WD_LIST, r)
            if m2:
                rec.byweekday, r, phrase = _wd_indices(m2["list"]), r2, f"{phrase} {m2.group(0).strip()}"
        return rec, r, phrase, None

    m, r = _take(RX_EVERY_PART, s)
    if m:
        t = {"morning": "09:00", "afternoon": "15:00", "evening": "18:00", "night": "21:00"}[m["p"].lower()]
        return Recurrence("daily"), r, m.group(0).strip(), t

    m, r = _take(RX_PLURAL_WD, s)                             # "tuesdays and thursdays"
    if m:
        singular = re.sub(r"(day)s\b", r"\1", m["list"], flags=_I)
        return Recurrence("weekly", 1, _wd_indices(singular)), r, m.group(0).strip(), None

    return None, s, "", None


# ------------------------------------------------------------------ time of day
def _to_24h(h: int, mi: int, ap: str | None, pm_hint: bool, am_hint: bool) -> tuple[int, int] | None:
    if mi > 59:
        return None
    if ap:
        if not 1 <= h <= 12:
            return None
        if ap[0].lower() == "p":
            h = h % 12 + 12
        else:
            h = h % 12
        return h, mi
    if h > 23:
        return None
    if 1 <= h <= 12:                       # bare number: guess am/pm
        if pm_hint:
            h = h % 12 + 12
        elif am_hint:
            h = h % 12
        elif h <= 6:
            h += 12                        # "at 5" -> 5 pm
        elif h == 12:
            pass                           # noon
    return h, mi


def _parse_time(s: str):
    """Returns ("HH:MM" | None, remaining text, [phrases], forced_today)."""
    phrases, forced_today, default = [], False, None
    pm_hint = am_hint = False

    m, r = _take(RX_DAYPART, s)
    if m:
        w = (m["p"] or m["t"]).lower()
        default = {"tonight": "20:00", "morning": "09:00", "afternoon": "15:00", "evening": "18:00"}[w]
        pm_hint, am_hint, forced_today = w != "morning", w == "morning", True
        s = r
        phrases.append(m.group(0).strip())

    for rx in (RX_T_COLON, RX_T_AMPM, RX_T_AT):
        for m in rx.finditer(s):
            ap = m.groupdict().get("ap")
            hm = _to_24h(int(m["h"]), int(m.groupdict().get("m") or 0), ap, pm_hint, am_hint)
            if hm:
                s = s[:m.start()] + " " + s[m.end():]
                phrases.append(m.group(0).strip())
                return f"{hm[0]:02d}:{hm[1]:02d}", s, phrases, forced_today
    m, r = _take(RX_T_NOON, s)
    if m:
        t = "00:00" if m["w"].lower() == "midnight" else "12:00"
        return t, r, phrases + [m.group(0).strip()], forced_today
    return default, s, phrases, forced_today


# ------------------------------------------------------------------ dates
def _parse_date(s: str, now: datetime):
    """Returns (date | None, time-override | None, remaining text, phrase)."""
    today = now.date()

    for m in RX_ISO.finditer(s):
        try:
            d = date(int(m["y"]), int(m["m"]), int(m["d"]))
        except ValueError:
            continue
        return d, None, s[:m.start()] + " " + s[m.end():], m.group(0)

    m, r = _take(RX_IN, s)
    if m:
        n = NUM_WORDS.get(m["n"].lower()) or int(m["n"])
        u = m["u"].lower()
        if u.startswith(("min", "hour", "hr")):
            dt = (now + (timedelta(minutes=n) if u.startswith("min") else timedelta(hours=n))).replace(second=0, microsecond=0)
            return dt.date(), dt.strftime("%H:%M"), r, m.group(0)
        if u.startswith("day"):
            return today + timedelta(days=n), None, r, m.group(0)
        if u.startswith("week"):
            return today + timedelta(weeks=n), None, r, m.group(0)
        return _add_months(today, n), None, r, m.group(0)

    for rx, fn in ((RX_DAY_AFTER, lambda: today + timedelta(days=2)),
                   (RX_TOMORROW, lambda: today + timedelta(days=1)),
                   (RX_YESTERDAY, lambda: today - timedelta(days=1)),
                   (RX_TODAY, lambda: today),
                   (RX_NEXT_WEEK, lambda: today + timedelta(days=7)),
                   (RX_WEEKEND_DATE, lambda: today + timedelta(days=(5 - today.weekday()) % 7))):
        m, r = _take(rx, s)
        if m:
            return fn(), None, r, m.group(0).strip()

    for rx in (RX_DMY, RX_MDY):
        m, r = _take(rx, s)
        if m:
            mon = MONTHS.index(m["mon"][:3].lower()) + 1
            try:
                d = date(today.year, mon, int(m["d"]))
                if d < today:
                    d = date(today.year + 1, mon, int(m["d"]))
            except ValueError:
                continue
            return d, None, r, m.group(0).strip()

    m, r = _take(RX_THE_NTH, s)
    if m:
        day = int(m["d"])
        if 1 <= day <= 31:
            d = _add_months(today.replace(day=1), 0, day)
            if d < today:
                d = _add_months(today.replace(day=1), 1, day)
            return d, None, r, m.group(0).strip()

    m, r = _take(RX_WEEKDAY, s)
    if m:
        target = WD_NAMES.index(m["wd"][:3].lower())
        return today + timedelta(days=(target - today.weekday()) % 7 or 7), None, r, m.group(0).strip()

    return None, None, s, ""


# ------------------------------------------------------------------ title cleanup
_EDGE_L = re.compile(r"^(?:to|for|about|that|and|on|at|by|every|each|starting|from|beginning|then)\s+", _I)
_EDGE_R = re.compile(r"\s+(?:on|at|by|from|starting|beginning|for|to|every|each|and|then)$", _I)


def _clean_title(s: str) -> str:
    s = re.sub(r"\s+", " ", s).strip(" ,.;:-–")
    prev = None
    while prev != s:
        prev = s
        s = _EDGE_R.sub("", _EDGE_L.sub("", s)).strip(" ,.;:-–")
    first = s.split(" ", 1)[0] if s else ""
    return s[:1].upper() + s[1:] if first.islower() else s


# ------------------------------------------------------------------ public API
def parse(text: str, now: datetime) -> Parsed:
    today = now.date()
    s = " " + LEAD.sub("", text.strip(), count=1) + " "
    chips: list[dict] = []

    priority, project = 4, None
    m, s = _take(RX_PRIORITY, s)
    if m:
        priority = int(m.group(1) or m.group(2))
        chips.append({"kind": "priority", "text": f"P{priority}"})
    m, s = _take(RX_PROJECT, s)
    if m:
        project = m.group(1)
        chips.append({"kind": "project", "text": f"#{project}"})

    rec, s, rec_phrase, default_time = _parse_recurrence(s)
    due_time, s, time_phrases, forced_today = _parse_time(s)
    due_date, rel_time, s, date_phrase = _parse_date(s, now)

    if rel_time:                                  # "in 2 hours"
        due_time = rel_time
    if due_time is None and default_time:
        due_time = default_time
    if forced_today and due_date is None:
        due_date = today

    if rec:
        if due_date is None:
            base = today
            if due_time and now.strftime("%H:%M") >= due_time:
                base = today + timedelta(days=1)      # today's slot already passed
            due_date = first_on_or_after(rec, base)
        else:
            due_date = first_on_or_after(rec, due_date)
        chips.append({"kind": "recurrence", "text": rec_phrase})
    elif due_date is None and due_time:
        due_date = today if now.strftime("%H:%M") < due_time else today + timedelta(days=1)

    if date_phrase:
        chips.append({"kind": "date", "text": date_phrase})
    for p in time_phrases:
        chips.append({"kind": "time", "text": p})

    return Parsed(_clean_title(s), due_date, due_time, rec, priority, project, chips)
