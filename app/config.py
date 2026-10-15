"""Settings, read once from environment variables (and a .env file if present)."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("TASKLY_DATA_DIR", BASE_DIR / "data"))
AUDIO_DIR = DATA_DIR / "audio"
DB_PATH = DATA_DIR / "taskly.db"

TZ = os.getenv("APP_TZ", "Asia/Kolkata")
DEBUG = os.getenv("DEBUG", "1") == "1"

# --- Email-to-task: every task gets t-<token>@EMAIL_DOMAIN ---
EMAIL_DOMAIN = os.getenv("EMAIL_DOMAIN", "inbox.taskly.local")
INBOUND_SECRET = os.getenv("INBOUND_SECRET", "change-me")

# --- Cloud AI (all optional: without keys the app falls back to the local rule parser) ---
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-haiku-5-5")

# Speech-to-text: any OpenAI-compatible /audio/transcriptions endpoint (OpenAI, Groq, ...)
STT_API_KEY = os.getenv("STT_API_KEY", "")
STT_BASE_URL = os.getenv("STT_BASE_URL", "https://api.openai.com/v1")
STT_MODEL = os.getenv("STT_MODEL", "whisper-1")

MAX_AUDIO_BYTES = 15 * 1024 * 1024

DATA_DIR.mkdir(parents=True, exist_ok=True)
AUDIO_DIR.mkdir(parents=True, exist_ok=True)
