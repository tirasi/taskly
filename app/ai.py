"""Cloud AI layer: speech -> text -> intent.

  audio --(OpenAI-compatible /audio/transcriptions)--> transcript
  transcript --(Claude, forced tool call)--> {intent, title, schedule, ...}

Claude only *understands* the sentence (fixes speech typos, splits "what" from "when",
picks which existing task is meant). Exact dates and recurrence rules are then computed by
nlp.py, so scheduling never depends on the model doing calendar maths.

With no API keys configured everything degrades gracefully to the local rule parser.
"""
from __future__ import annotations

import difflib
import logging
import re
from datetime import datetime

import httpx

from . import config

log = logging.getLogger("taskly.ai")

STT_ENABLED = bool(config.STT_API_KEY)
LLM_ENABLED = bool(config.ANTHROPIC_API_KEY)

# Hint text that biases the speech model toward scheduling vocabulary.
STT_PROMPT = "Task reminders: every Tuesday, Thursday at 5pm; tomorrow at 9am; remind me to call mom; p1; hashtag work."

COMMAND_TOOL = {
    "name": "record_command",
    "description": "Record what the user asked their task app to do.",
    "input_schema": {
        "type": "object",
        "properties": {
            "intent": {"type": "string", "enum": ["add_task", "complete_task", "add_comment", "unclear"]},
            "title": {"type": "string",
                      "description": "Short task title with NO schedule words. Fix obvious speech-recognition typos. Only for add_task."},
            "schedule": {"type": "string",
                         "description": "When/how often, in plain English such as 'every tuesday and thursday at 5pm', "
                                        "'tomorrow at 9am', 'every 2 weeks on monday', 'on the 1st of every month'. "
                                        "Empty string if no timing was mentioned."},
            "priority": {"type": "integer", "enum": [1, 2, 3, 4], "description": "1 = urgent ... 4 = normal (default)."},
            "project": {"type": "string", "description": "Project name if one was mentioned, else empty."},
            "target_task": {"type": "string",
                            "description": "For complete_task / add_comment: the title of the existing task meant, copied from the open-task list."},
            "comment": {"type": "string", "description": "For add_comment: the comment text."},
        },
        "required": ["intent"],
    },
}


class AIError(Exception):
    pass


async def transcribe(audio: bytes, filename: str, content_type: str) -> str:
    """Cloud speech-to-text. Raises AIError if not configured or the call fails."""
    if not STT_ENABLED:
        raise AIError("Speech-to-text is not configured (set STT_API_KEY).")
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                f"{config.STT_BASE_URL.rstrip('/')}/audio/transcriptions",
                headers={"Authorization": f"Bearer {config.STT_API_KEY}"},
                data={"model": config.STT_MODEL, "prompt": STT_PROMPT},
                files={"file": (filename, audio, content_type)},
            )
        r.raise_for_status()
        return (r.json().get("text") or "").strip()
    except httpx.HTTPError as e:
        log.warning("transcription failed: %s", e)
        raise AIError("Transcription failed.") from e


async def interpret(transcript: str, now: datetime, open_tasks: list[str]) -> dict:
    """Understand a spoken command. Uses Claude when configured, else local rules."""
    if LLM_ENABLED:
        try:
            return await _interpret_llm(transcript, now, open_tasks)
        except (httpx.HTTPError, KeyError, ValueError) as e:
            log.warning("LLM interpret failed, using rules: %s", e)
    return interpret_rules(transcript)


async def _interpret_llm(transcript: str, now: datetime, open_tasks: list[str]) -> dict:
    system = (
        "You turn a spoken command for a to-do app into a structured action. "
        f"Today is {now:%A, %Y-%m-%d}, local time {now:%H:%M} ({config.TZ}). "
        "The transcript comes from speech recognition and may contain typos. "
        "Always call record_command. Never invent details the user did not say.\n\n"
        "Open tasks (for complete_task / add_comment, copy the matching title exactly):\n"
        + "\n".join(f"- {t}" for t in open_tasks[:100])
    )
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": config.ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            json={"model": config.ANTHROPIC_MODEL, "max_tokens": 400, "system": system,
                  "tools": [COMMAND_TOOL], "tool_choice": {"type": "tool", "name": "record_command"},
                  "messages": [{"role": "user", "content": transcript}]},
        )
    r.raise_for_status()
    for block in r.json()["content"]:
        if block.get("type") == "tool_use":
            return block["input"]
    raise ValueError("no tool call in response")


# ------------------------------------------------------------------ offline fallback
_DONE = re.compile(r"^(?:please\s+)?(?:(?:mark|set)\s+)?(?:complete|finish|done with|tick off|check off)\s+(?P<t>.+)$", re.I)
_DONE2 = re.compile(r"^(?:mark\s+)?(?P<t>.+?)\s+(?:as\s+)?(?:done|complete|completed|finished)$", re.I)
_COMMENT = re.compile(r"^(?:add\s+(?:a\s+)?)?(?:comment|note)\s+(?:on|to|for)\s+(?P<t>.+?)\s*[:,]\s*(?P<c>.+)$", re.I)


def interpret_rules(transcript: str) -> dict:
    t = transcript.strip().rstrip(".!")
    if m := _COMMENT.match(t):
        return {"intent": "add_comment", "target_task": m["t"], "comment": m["c"]}
    if m := _DONE.match(t) or _DONE2.match(t):
        return {"intent": "complete_task", "target_task": m["t"]}
    return {"intent": "add_task", "raw": t}      # nlp.parse handles the whole sentence


def match_task(target: str, tasks: list[tuple[int, str]]) -> int | None:
    """Fuzzy-match a spoken task name to (id, title) pairs. Returns the id or None."""
    target = target.lower().strip()
    if not target:
        return None
    titles: dict[str, int] = {}
    for tid, title in tasks:                      # newest first: keep the most recent duplicate
        titles.setdefault(title.lower(), tid)
    if target in titles:
        return titles[target]
    contains = [tid for title, tid in titles.items() if target in title or title in target]
    if len(contains) == 1:
        return contains[0]
    close = difflib.get_close_matches(target, list(titles), n=1, cutoff=0.6)
    return titles[close[0]] if close else None
