"""SQLite storage. One short-lived connection per request keeps things simple and safe."""
import sqlite3
from contextlib import closing
from datetime import datetime

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    title        TEXT NOT NULL,
    project_id   INTEGER NOT NULL REFERENCES projects(id),
    priority     INTEGER NOT NULL DEFAULT 4 CHECK (priority BETWEEN 1 AND 4),
    due_date     TEXT,                 -- YYYY-MM-DD (for recurring tasks: the NEXT occurrence)
    due_time     TEXT,                 -- HH:MM
    recurrence   TEXT,                 -- JSON, see recurrence.py
    done         INTEGER NOT NULL DEFAULT 0,
    completed_at TEXT,
    email_token  TEXT NOT NULL UNIQUE, -- the t-<token>@domain address that comments on this task
    created_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tasks_due ON tasks(done, due_date);

CREATE TABLE IF NOT EXISTS comments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id    INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    kind       TEXT NOT NULL CHECK (kind IN ('text', 'voice', 'email')),
    body       TEXT NOT NULL DEFAULT '',
    subject    TEXT,
    from_addr  TEXT,
    audio_file TEXT,
    message_id TEXT,                   -- email Message-Id, used to drop duplicate deliveries
    created_at TEXT NOT NULL,
    UNIQUE (task_id, message_id)
);
CREATE INDEX IF NOT EXISTS idx_comments_task ON comments(task_id);

-- history of every tick, so recurring tasks (which never become "done") keep a record
CREATE TABLE IF NOT EXISTS completions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id      INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    due_date     TEXT,
    completed_at TEXT NOT NULL
);
"""


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init() -> None:
    with closing(connect()) as conn:
        conn.executescript(SCHEMA)
        conn.execute("INSERT OR IGNORE INTO projects (id, name, created_at) VALUES (1, 'Inbox', ?)",
                     (datetime.now().isoformat(timespec="seconds"),))
        conn.commit()
