from datetime import date, datetime

from app.nlp import parse
from app.recurrence import Recurrence, describe

NOW = datetime(2026, 10, 15, 15, 50)  # Thursday


def test_the_voice_example():
    p = parse("set a remainder for every tuesday, thursday 5pm runnning", NOW)
    assert p.title == "Runnning"
    assert p.recurrence == Recurrence("weekly", 1, [1, 3])
    assert p.due_time == "17:00"
    assert p.due_date == date(2026, 10, 15)          # today is Thursday and 5pm is still ahead
    assert describe(p.recurrence, p.due_time) == "Every Tue, Thu at 5:00 PM"


def test_slot_already_passed_starts_next_matching_day():
    p = parse("every thursday at 9am yoga", NOW)
    assert p.due_date == date(2026, 10, 22)


def test_weekday_variants():
    assert parse("gym every mon, wed and fri", NOW).recurrence.byweekday == [0, 2, 4]
    assert parse("gym every mon-fri", NOW).recurrence.byweekday == [0, 1, 2, 3, 4]
    assert parse("gym every weekday", NOW).recurrence.byweekday == [0, 1, 2, 3, 4]
    assert parse("hike every weekend", NOW).recurrence.byweekday == [5, 6]
    assert parse("church on sundays", NOW).recurrence.byweekday == [6]
    assert parse("sync every other tuesday", NOW).recurrence == Recurrence("weekly", 2, [1])


def test_intervals_and_monthly():
    assert parse("water plants every 3 days", NOW).recurrence == Recurrence("daily", 3)
    assert parse("review daily", NOW).recurrence == Recurrence("daily", 1)
    r = parse("pay rent on the 1st of every month", NOW)
    assert r.recurrence == Recurrence("monthly", 1, [], 1) and r.due_date == date(2026, 11, 1)
    assert parse("invoice every month on the 15th", NOW).due_date == date(2026, 10, 15)
    assert parse("standup every 2 weeks on monday", NOW).recurrence == Recurrence("weekly", 2, [0])


def test_one_off_dates_and_times():
    p = parse("Submit report tomorrow p1 #Work", NOW)
    assert (p.title, p.due_date, p.priority, p.project) == ("Submit report", date(2026, 10, 16), 1, "Work")
    assert parse("call mom at 7pm", NOW).due_time == "19:00"
    assert parse("call mom at 7pm", NOW).due_date == date(2026, 10, 15)
    assert parse("call mom at 3pm", NOW).due_date == date(2026, 10, 16)   # 3pm already passed today
    assert parse("lunch with sam friday 12:30", NOW).due_date == date(2026, 10, 16)
    assert parse("dentist 2026-11-02 10:00", NOW).due_date == date(2026, 11, 2)
    assert parse("party oct 31", NOW).due_date == date(2026, 10, 31)
    assert parse("renew passport in 3 weeks", NOW).due_date == date(2026, 11, 5)
    assert parse("finish homework yesterday", NOW).due_date == date(2026, 10, 14)
    assert parse("stretch in 2 hours", NOW).due_time == "17:50"
    assert parse("tonight at 9 take medicine", NOW).due_time == "21:00"


def test_names_that_look_like_dates_are_left_alone():
    assert parse("call Tom tomorrow", NOW).title == "Call Tom"
    assert parse("Morning run every sat", NOW).title == "Morning run"


def test_plain_text_has_no_schedule():
    p = parse("buy milk", NOW)
    assert (p.title, p.due_date, p.due_time, p.recurrence) == ("Buy milk", None, None, None)
