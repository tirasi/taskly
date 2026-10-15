# Taskly: a Todoist-style app you can read end to end

FastAPI + SQLite backend, plain-JS frontend (no build step). It was written to study how Todoist-like products work, so the code is small and commented.

## Run it

```bash
cd taskly
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # optional: add API keys for cloud voice AI
uvicorn app.main:app --reload
# open http://localhost:8000
python3 -m pytest               # 27 tests
```

## What it does

| Feature | Try this | Where it lives |
|---|---|---|
| Natural-language quick add | `gym every mon, wed 6am p2 #Health` | `app/nlp.py` |
| Recurrence (daily/weekly/monthly/yearly, every N, weekdays, "every other tue", "on the 1st of every month") | `set a reminder for every tuesday, thursday 5pm running` | `app/recurrence.py` |
| Completing a recurring task moves it to the next occurrence (overdue ones skip the past) | tick the circle | `main.complete_task` |
| Voice commands: add, complete, comment | tap 🎙 and say "set a reminder for every Tuesday, Thursday 5pm running" | `app/ai.py`, `main.run_command` |
| Voice notes on a task (audio kept and transcribed) | open a task, "Record voice note" | `main.post_voice_note` |
| Every task has its own email address; mail sent to it becomes a comment | open a task, copy the address | `main.ingest_email` |
| Today / Upcoming / Inbox / Projects / Completed | sidebar | `main.list_tasks` |
| Browser reminders at the task's time (while the tab is open) | click "Enable reminders" | `app.js checkReminders` |

## How the voice pipeline works

```
mic ──► MediaRecorder (auto-stops when you stop talking)
    ──► POST /api/voice/command
          1. cloud speech-to-text (OpenAI-compatible endpoint)  -> transcript
          2. Claude, forced tool call -> {intent, title, schedule, priority, project, target_task, comment}
          3. nlp.parse(schedule) -> exact dates, times, recurrence rule   (deterministic code, not the model)
          4. create / complete / comment
```

Claude only *understands* the sentence: it fixes speech typos ("runnning" becomes "Running"), separates the **what** from the **when**, and picks which existing task you mean. The calendar maths is always done by the tested code in `nlp.py` and `recurrence.py`, so a model mistake can't create a wrong schedule rule. The command audio is transcribed and discarded; only voice *notes* are stored.

Without API keys the mic button falls back to the browser's speech recognition (Chrome/Edge/Safari) and a rule-based intent parser, so you can try everything offline.

## Email-to-comment setup

Each task shows an address like `t-3f9a1c7b2d4e@inbox.example.com`. To make it real you need a domain and an inbound-email provider (Mailgun Routes, SendGrid Inbound Parse, Postmark Inbound, ...):

1. Point the domain's MX records at the provider.
2. Set the provider's inbound webhook to `POST https://your-host/api/email/inbound?secret=<INBOUND_SECRET>`.
3. Set `EMAIL_DOMAIN` and `INBOUND_SECRET` in `.env`.

The endpoint accepts form-encoded (Mailgun/SendGrid) or JSON bodies, strips quoted replies and signatures, ignores duplicate deliveries (by `Message-Id`) and ignores unknown addresses without revealing whether they exist.

Try it locally without a provider:

```bash
curl -X POST "localhost:8000/api/email/inbound" -H "X-Inbound-Secret: change-me" \
  -H "Content-Type: application/json" \
  -d '{"recipient":"t-<token>@inbox.taskly.local","sender":"me@example.com","subject":"Hi","text":"Hello from email"}'
```

(or use the "simulate an incoming email" box in the task panel while `DEBUG=1`).

## Project map

```
app/
  recurrence.py   Recurrence rule + next-occurrence maths (pure functions)
  nlp.py          "every tue, thu 5pm run" -> title, date, time, rule
  ai.py           speech-to-text + Claude intent extraction + offline fallback
  db.py           SQLite schema (projects, tasks, comments, completions)
  main.py         REST API, voice command runner, email webhook
  static/         index.html, style.css, app.js
tests/            parser, recurrence, API, email, voice (cloud calls mocked)
```

Data model in one glance: a task has `due_date` (for recurring tasks, the *next* occurrence), `due_time`, a JSON `recurrence` rule and an `email_token`. Today, Upcoming and Inbox are just different queries over that one table.

## Known limits (good next steps)

- Single user, no login. Add auth (sessions or OAuth) before exposing it. Email tokens are unguessable, but they are not accounts.
- One timezone (`APP_TZ`). Reminders only fire while a browser tab is open; real push needs a service worker and Web Push.
- The recurrence engine covers the common patterns, not all of iCalendar RRULE. Libraries like `python-dateutil` are the next step for exotic rules.
- Sub-tasks, labels, filters, sharing and sync are not built.
