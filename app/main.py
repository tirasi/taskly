"""Taskly API: tasks, projects, recurrence, voice commands, voice notes, email-to-comment."""
from __future__ import annotations

import hmac
import logging
import re
import secrets
import sqlite3
import uuid
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import ai, config, db, nlp
from .recurrence import Recurrence, describe, fmt_time, next_for_completion

log = logging.getLogger("taskly")
STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init()
    yield


app = FastAPI(title="Taskly", lifespan=lifespan)


# ------------------------------------------------------------------ helpers
def now_local() -> datetime:
    """Current time in the app's timezone as a naive datetime (tests monkeypatch this)."""
    return datetime.now(ZoneInfo(config.TZ)).replace(tzinfo=None, second=0, microsecond=0)


def now_iso() -> str:
    return now_local().isoformat(timespec="seconds")


def get_db():
    conn = db.connect()
    try:
        yield conn
    finally:
        conn.close()


BASE_SELECT = """
SELECT t.*, p.name AS project_name,
       (SELECT COUNT(*) FROM comments c WHERE c.task_id = t.id) AS comment_count
FROM tasks t JOIN projects p ON p.id = t.project_id
"""


def friendly_date(d: date | None, today: date) -> str:
    if not d:
        return ""
    delta = (d - today).days
    if delta == 0:
        return "today"
    if delta == 1:
        return "tomorrow"
    return d.strftime("%a %-d %b")


def task_dict(r: sqlite3.Row) -> dict:
    rec = Recurrence.from_json(r["recurrence"])
    return {
        "id": r["id"], "title": r["title"], "project_id": r["project_id"], "project_name": r["project_name"],
        "priority": r["priority"], "due_date": r["due_date"], "due_time": r["due_time"],
        "recurrence": asdict(rec) if rec else None,
        "recurrence_text": describe(rec, r["due_time"]) if rec else None,
        "done": bool(r["done"]), "completed_at": r["completed_at"],
        "email": f"t-{r['email_token']}@{config.EMAIL_DOMAIN}",
        "comment_count": r["comment_count"],
    }


def get_task_row(conn: sqlite3.Connection, task_id: int) -> sqlite3.Row:
    row = conn.execute(BASE_SELECT + " WHERE t.id = ?", (task_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Task not found")
    return row


def project_id_for(conn: sqlite3.Connection, name: str | None) -> int:
    if not name:
        return 1
    row = conn.execute("SELECT id FROM projects WHERE lower(name) = lower(?)", (name,)).fetchone()
    if row:
        return row["id"]
    return conn.execute("INSERT INTO projects (name, created_at) VALUES (?, ?)", (name, now_iso())).lastrowid


def insert_task(conn: sqlite3.Connection, p: nlp.Parsed, project_id: int | None = None) -> dict:
    pid = project_id_for(conn, p.project) if p.project else (project_id or 1)
    cur = conn.execute(
        "INSERT INTO tasks (title, project_id, priority, due_date, due_time, recurrence, email_token, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (p.title, pid, p.priority, p.due_date.isoformat() if p.due_date else None, p.due_time,
         p.recurrence.to_json() if p.recurrence else None, secrets.token_hex(6), now_iso()))
    conn.commit()
    return task_dict(get_task_row(conn, cur.lastrowid))


def complete_task(conn: sqlite3.Connection, row: sqlite3.Row) -> dict:
    """Tick a task. Recurring tasks jump to their next occurrence instead of becoming done."""
    rec = Recurrence.from_json(row["recurrence"])
    conn.execute("INSERT INTO completions (task_id, due_date, completed_at) VALUES (?, ?, ?)",
                 (row["id"], row["due_date"], now_iso()))
    if rec and row["due_date"]:
        nxt = next_for_completion(rec, date.fromisoformat(row["due_date"]), now_local().date())
        conn.execute("UPDATE tasks SET due_date = ? WHERE id = ?", (nxt.isoformat(), row["id"]))
    else:
        conn.execute("UPDATE tasks SET done = 1, completed_at = ? WHERE id = ?", (now_iso(), row["id"]))
    conn.commit()
    return task_dict(get_task_row(conn, row["id"]))


def comment_dict(r: sqlite3.Row) -> dict:
    return {"id": r["id"], "task_id": r["task_id"], "kind": r["kind"], "body": r["body"], "subject": r["subject"],
            "from": r["from_addr"], "created_at": r["created_at"],
            "audio_url": f"/api/audio/{r['audio_file']}" if r["audio_file"] else None}


def add_comment(conn, task_id: int, kind: str, body: str, *, subject=None, from_addr=None,
                audio_file=None, message_id=None) -> dict:
    cur = conn.execute(
        "INSERT INTO comments (task_id, kind, body, subject, from_addr, audio_file, message_id, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (task_id, kind, body, subject, from_addr, audio_file, message_id, now_iso()))
    conn.commit()
    return comment_dict(conn.execute("SELECT * FROM comments WHERE id = ?", (cur.lastrowid,)).fetchone())


def preview(p: nlp.Parsed) -> dict:
    return {"title": p.title, "due_date": p.due_date.isoformat() if p.due_date else None, "due_time": p.due_time,
            "recurrence_text": describe(p.recurrence, p.due_time) if p.recurrence else None,
            "priority": p.priority, "project": p.project, "chips": p.chips}


# ------------------------------------------------------------------ models
class ParseIn(BaseModel):
    text: str = Field(max_length=500)


class TaskIn(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    project_id: int | None = None
    default_today: bool = False          # quick-add from the Today view with no date -> due today


class TaskPatch(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=500)
    priority: int | None = Field(None, ge=1, le=4)
    project_id: int | None = None
    schedule: str | None = Field(None, max_length=200)   # natural language; "" clears the schedule
    due_date: str | None = None
    due_time: str | None = None
    recurrence: str | None = None


class CommentIn(BaseModel):
    body: str = Field(min_length=1, max_length=5000)


class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)


class VoiceTextIn(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


class SimEmailIn(BaseModel):
    task_id: int
    sender: str = "friend@example.com"
    subject: str = ""
    body: str = Field(min_length=1, max_length=20000)


# ------------------------------------------------------------------ config / sidebar / projects
@app.get("/api/config")
def get_config():
    return {"debug": config.DEBUG, "email_domain": config.EMAIL_DOMAIN, "tz": config.TZ,
            "stt_enabled": ai.STT_ENABLED, "llm_enabled": ai.LLM_ENABLED}


@app.get("/api/sidebar")
def sidebar(conn=Depends(get_db)):
    today = now_local().date().isoformat()
    one = lambda sql, *a: conn.execute(sql, a).fetchone()[0]
    projects = conn.execute(
        "SELECT p.id, p.name, (SELECT COUNT(*) FROM tasks t WHERE t.project_id = p.id AND t.done = 0) AS count "
        "FROM projects p ORDER BY p.id").fetchall()
    return {
        "today": one("SELECT COUNT(*) FROM tasks WHERE done = 0 AND due_date IS NOT NULL AND due_date <= ?", today),
        "upcoming": one("SELECT COUNT(*) FROM tasks WHERE done = 0 AND due_date > ?", today),
        "projects": [dict(p) for p in projects],
    }


@app.get("/api/projects")
def list_projects(conn=Depends(get_db)):
    return [dict(r) for r in conn.execute("SELECT id, name FROM projects ORDER BY id")]


@app.post("/api/projects", status_code=201)
def create_project(body: ProjectIn, conn=Depends(get_db)):
    pid = project_id_for(conn, body.name.strip())
    conn.commit()
    return {"id": pid, "name": body.name.strip()}


@app.delete("/api/projects/{project_id}", status_code=204)
def delete_project(project_id: int, conn=Depends(get_db)):
    if project_id == 1:
        raise HTTPException(400, "The Inbox can't be deleted")
    conn.execute("UPDATE tasks SET project_id = 1 WHERE project_id = ?", (project_id,))
    conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    conn.commit()


# ------------------------------------------------------------------ tasks
@app.get("/api/tasks")
def list_tasks(view: str = "today", project_id: int | None = None, conn=Depends(get_db)):
    today = now_local().date().isoformat()
    args: tuple = ()
    if view == "today":
        where, order, args = "t.done = 0 AND t.due_date IS NOT NULL AND t.due_date <= ?", \
            "t.due_date, (t.due_time IS NULL), t.due_time, t.priority, t.id", (today,)
    elif view == "upcoming":
        where, order, args = "t.done = 0 AND t.due_date > ?", \
            "t.due_date, (t.due_time IS NULL), t.due_time, t.priority, t.id", (today,)
    elif view == "inbox":
        where, order = "t.done = 0 AND t.project_id = 1", "t.priority, (t.due_date IS NULL), t.due_date, t.id"
    elif view == "project":
        if project_id is None:
            raise HTTPException(400, "project_id required")
        where, order, args = "t.done = 0 AND t.project_id = ?", \
            "t.priority, (t.due_date IS NULL), t.due_date, t.id", (project_id,)
    elif view == "completed":
        where, order = "t.done = 1", "t.completed_at DESC LIMIT 100"
    else:
        raise HTTPException(400, "unknown view")
    return [task_dict(r) for r in conn.execute(f"{BASE_SELECT} WHERE {where} ORDER BY {order}", args)]


@app.post("/api/parse")
def parse_preview(body: ParseIn):
    """Live preview for the quick-add box: what the parser understood. Creates nothing."""
    return preview(nlp.parse(body.text, now_local()))


@app.post("/api/tasks", status_code=201)
def create_task(body: TaskIn, conn=Depends(get_db)):
    now = now_local()
    p = nlp.parse(body.text, now)
    if not p.title:
        raise HTTPException(422, "Please include what the task is.")
    if body.default_today and not p.due_date and not p.recurrence:
        p.due_date = now.date()
    return insert_task(conn, p, body.project_id)


@app.get("/api/tasks/{task_id}")
def get_task(task_id: int, conn=Depends(get_db)):
    return task_dict(get_task_row(conn, task_id))


@app.patch("/api/tasks/{task_id}")
def update_task(task_id: int, body: TaskPatch, conn=Depends(get_db)):
    get_task_row(conn, task_id)
    sets: dict[str, object] = {}
    if body.title is not None:
        sets["title"] = body.title.strip()
    if body.priority is not None:
        sets["priority"] = body.priority
    if body.project_id is not None:
        if not conn.execute("SELECT 1 FROM projects WHERE id = ?", (body.project_id,)).fetchone():
            raise HTTPException(404, "Project not found")
        sets["project_id"] = body.project_id
    if body.schedule is not None:
        if not body.schedule.strip():
            sets.update(due_date=None, due_time=None, recurrence=None)
        else:
            p = nlp.parse(body.schedule, now_local())
            if not (p.due_date or p.recurrence):
                raise HTTPException(422, "I couldn't understand that schedule. Try 'every mon at 9am' or 'tomorrow 5pm'.")
            sets.update(due_date=p.due_date.isoformat() if p.due_date else None, due_time=p.due_time,
                        recurrence=p.recurrence.to_json() if p.recurrence else None)
    if body.due_date is not None:
        sets["due_date"] = body.due_date.strip() if body.due_date.strip() else None
    if body.due_time is not None:
        sets["due_time"] = body.due_time.strip() if body.due_time.strip() else None
    if body.recurrence is not None:
        sets["recurrence"] = body.recurrence.strip() if body.recurrence.strip() else None
    if sets:
        conn.execute(f"UPDATE tasks SET {', '.join(f'{k} = ?' for k in sets)} WHERE id = ?", (*sets.values(), task_id))
        conn.commit()
    return task_dict(get_task_row(conn, task_id))


@app.delete("/api/tasks/{task_id}", status_code=204)
def delete_task(task_id: int, conn=Depends(get_db)):
    get_task_row(conn, task_id)
    files = [r["audio_file"] for r in conn.execute(
        "SELECT audio_file FROM comments WHERE task_id = ? AND audio_file IS NOT NULL", (task_id,))]
    conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    for f in files:
        (config.AUDIO_DIR / f).unlink(missing_ok=True)


@app.post("/api/tasks/{task_id}/complete")
def complete(task_id: int, conn=Depends(get_db)):
    row = get_task_row(conn, task_id)
    if row["done"]:
        return task_dict(row)
    return complete_task(conn, row)


@app.post("/api/tasks/{task_id}/reopen")
def reopen(task_id: int, conn=Depends(get_db)):
    get_task_row(conn, task_id)
    conn.execute("UPDATE tasks SET done = 0, completed_at = NULL WHERE id = ?", (task_id,))
    conn.commit()
    return task_dict(get_task_row(conn, task_id))


# ------------------------------------------------------------------ comments, voice notes, audio
AUDIO_EXT = {"audio/webm": "webm", "audio/ogg": "ogg", "audio/mp4": "m4a", "audio/x-m4a": "m4a",
             "audio/m4a": "m4a", "audio/mpeg": "mp3", "audio/wav": "wav", "audio/x-wav": "wav"}
EXT_MIME = {"webm": "audio/webm", "ogg": "audio/ogg", "m4a": "audio/mp4", "mp3": "audio/mpeg", "wav": "audio/wav"}
AUDIO_NAME = re.compile(r"^[0-9a-f]{32}\.(webm|ogg|m4a|mp3|wav)$")


async def read_audio(file: UploadFile) -> tuple[bytes, str, str]:
    ctype = (file.content_type or "").split(";")[0].strip().lower()
    ext = AUDIO_EXT.get(ctype)
    if not ext:
        raise HTTPException(415, "Unsupported audio type")
    data = await file.read(config.MAX_AUDIO_BYTES + 1)
    if not data:
        raise HTTPException(400, "Empty recording")
    if len(data) > config.MAX_AUDIO_BYTES:
        raise HTTPException(413, "Recording too large")
    return data, ext, ctype


@app.get("/api/tasks/{task_id}/comments")
def list_comments(task_id: int, conn=Depends(get_db)):
    get_task_row(conn, task_id)
    return [comment_dict(r) for r in conn.execute(
        "SELECT * FROM comments WHERE task_id = ? ORDER BY id", (task_id,))]


@app.post("/api/tasks/{task_id}/comments", status_code=201)
def post_comment(task_id: int, body: CommentIn, conn=Depends(get_db)):
    get_task_row(conn, task_id)
    return add_comment(conn, task_id, "text", body.body.strip())


@app.post("/api/tasks/{task_id}/voice-note", status_code=201)
async def post_voice_note(task_id: int, audio: UploadFile = File(...), conn=Depends(get_db)):
    """A comment recorded by voice: the audio is kept and, if STT is configured, transcribed."""
    get_task_row(conn, task_id)
    data, ext, ctype = await read_audio(audio)
    name = f"{uuid.uuid4().hex}.{ext}"
    (config.AUDIO_DIR / name).write_bytes(data)
    try:
        transcript = await ai.transcribe(data, name, ctype)
    except ai.AIError as e:
        log.info("voice note saved without transcript: %s", e)
        transcript = ""
    return add_comment(conn, task_id, "voice", transcript, audio_file=name)


@app.get("/api/audio/{name}")
def get_audio(name: str):
    if not AUDIO_NAME.match(name):                  # strict allow-list: blocks path traversal
        raise HTTPException(404)
    path = config.AUDIO_DIR / name
    if not path.is_file():
        raise HTTPException(404)
    return FileResponse(path, media_type=EXT_MIME[name.rsplit(".", 1)[1]])


# ------------------------------------------------------------------ voice commands
def _open_tasks(conn) -> list[sqlite3.Row]:
    return conn.execute("SELECT id, title FROM tasks WHERE done = 0 ORDER BY id DESC LIMIT 200").fetchall()


def _summary(t: dict) -> str:
    today = now_local().date()
    due = friendly_date(date.fromisoformat(t["due_date"]), today) if t["due_date"] else ""
    at = f" at {fmt_time(t['due_time'])}" if t["due_time"] else ""
    if t["recurrence_text"]:
        when = f"{t['recurrence_text']} (next: {due})"
    elif due:
        when = f"due {due}{at}"
    else:
        when = ""
    return f"Added “{t['title']}”" + (f" — {when}" if when else "")


async def run_command(conn, transcript: str) -> dict:
    now = now_local()
    rows = _open_tasks(conn)
    cmd = await ai.interpret(transcript, now, [r["title"] for r in rows])
    intent = cmd.get("intent", "unclear")
    out = {"transcript": transcript, "intent": intent}

    if intent == "add_task":
        if cmd.get("raw"):                                   # offline path: parse the whole sentence
            p = nlp.parse(cmd["raw"], now)
        else:                                                # AI path: title verbatim, schedule via nlp
            sched = nlp.parse(cmd.get("schedule") or "", now)
            title = (cmd.get("title") or "").strip()
            p = nlp.Parsed(title, sched.due_date, sched.due_time, sched.recurrence,
                           cmd.get("priority") or sched.priority, (cmd.get("project") or "").strip() or None)
            if p.project:
                p.project = re.sub(r"\s+", "-", p.project)
            if not title:
                p = nlp.parse(transcript, now)
        if not p.title:
            return {**out, "ok": False, "message": "I couldn't work out what the task is."}
        task = insert_task(conn, p)
        return {**out, "ok": True, "message": _summary(task), "task": task}

    if intent in ("complete_task", "add_comment"):
        tid = ai.match_task(cmd.get("target_task", ""), [(r["id"], r["title"]) for r in rows])
        if tid is None:
            return {**out, "ok": False, "message": f"I couldn't find a task called “{cmd.get('target_task', '')}”."}
        row = get_task_row(conn, tid)
        if intent == "complete_task":
            task = complete_task(conn, row)
            more = f" — next {task['due_date']}" if task["recurrence"] else ""
            return {**out, "ok": True, "message": f"Completed “{task['title']}”{more}", "task": task}
        comment = (cmd.get("comment") or "").strip()
        if not comment:
            return {**out, "ok": False, "message": "What should the comment say?"}
        add_comment(conn, tid, "text", comment)
        return {**out, "ok": True, "message": f"Commented on “{row['title']}”", "task": task_dict(get_task_row(conn, tid))}

    return {**out, "ok": False, "message": "I didn't catch a task in that. Try “remind me to call mom tomorrow at 5”."}


@app.post("/api/voice/command")
async def voice_command(audio: UploadFile = File(...), conn=Depends(get_db)):
    """Speak a command. The audio is transcribed and discarded; only the resulting task is stored."""
    data, ext, ctype = await read_audio(audio)
    try:
        transcript = await ai.transcribe(data, f"speech.{ext}", ctype)
    except ai.AIError as e:
        raise HTTPException(503, str(e))
    if not transcript:
        raise HTTPException(422, "I couldn't hear anything.")
    return await run_command(conn, transcript)


@app.post("/api/voice/interpret")
async def voice_interpret(body: VoiceTextIn, conn=Depends(get_db)):
    """Same pipeline minus the microphone: handy for testing and for the typed 'ask' box."""
    return await run_command(conn, body.text.strip())


# ------------------------------------------------------------------ email-to-comment
TOKEN_RX = re.compile(r"\bt-([0-9a-f]{12})@", re.I)
_QUOTE_START = re.compile(r"^(?:on .{5,200} wrote:|-{2,}\s*original message\s*-{2,}|_{5,}|from:\s.+|sent from my .+)\s*$", re.I)


def clean_email_body(text: str) -> str:
    """Keep what the sender typed: drop quoted replies, signatures and trailing blank lines."""
    keep: list[str] = []
    for line in text.replace("\r\n", "\n").split("\n"):
        if line.strip() == "--" or line.startswith("-- ") or line.lstrip().startswith(">") or (
                keep and _QUOTE_START.match(line.strip())):
            break
        keep.append(line)
    return "\n".join(keep).strip()[:20000]


def _pick(data: dict, *keys: str) -> str:
    for k in keys:
        v = data.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def ingest_email(conn, data: dict) -> dict:
    recipients = " ".join(str(data.get(k, "")) for k in ("recipient", "to", "To", "envelope", "cc", "Cc"))
    m = TOKEN_RX.search(recipients)
    row = conn.execute("SELECT id FROM tasks WHERE email_token = ?", (m.group(1).lower(),)).fetchone() if m else None
    if not row:                                  # 200 so mail providers don't retry; reveals nothing
        return {"status": "unknown_recipient"}
    subject = _pick(data, "subject", "Subject")
    body = clean_email_body(_pick(data, "stripped-text", "text", "body-plain", "TextBody", "plain", "body"))
    if not body and not subject:
        return {"status": "empty"}
    try:
        c = add_comment(conn, row["id"], "email", body or subject, subject=subject or None,
                        from_addr=_pick(data, "sender", "from", "From", "FromEmail")[:200] or None,
                        message_id=_pick(data, "Message-Id", "message-id", "message_id", "MessageID") or None)
    except sqlite3.IntegrityError:
        return {"status": "duplicate"}
    return {"status": "ok", "comment": c}


@app.post("/api/email/inbound")
async def inbound_email(request: Request, conn=Depends(get_db)):
    """Webhook for your mail provider's inbound-parse feature (Mailgun, SendGrid, Postmark...)."""
    secret = request.headers.get("x-inbound-secret") or request.query_params.get("secret", "")
    if not hmac.compare_digest(secret.encode(), config.INBOUND_SECRET.encode()):
        raise HTTPException(401, "Bad secret")
    if "json" in request.headers.get("content-type", ""):
        data = await request.json()
    else:
        data = dict(await request.form())
    if not isinstance(data, dict):
        raise HTTPException(400, "Expected an object")
    return ingest_email(conn, data)


@app.post("/api/dev/simulate-email")
def simulate_email(body: SimEmailIn, conn=Depends(get_db)):
    """DEBUG only: pretend an email arrived, so the feature can be tried without a mail provider."""
    if not config.DEBUG:
        raise HTTPException(404)
    t = task_dict(get_task_row(conn, body.task_id))
    return ingest_email(conn, {"recipient": t["email"], "sender": body.sender, "subject": body.subject,
                               "text": body.body, "Message-Id": f"<sim-{uuid.uuid4().hex}@local>"})


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
