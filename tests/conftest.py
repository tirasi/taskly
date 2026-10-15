import os
import sys
import tempfile
from pathlib import Path

# Isolated data dir + known secrets BEFORE the app is imported.
os.environ["TASKLY_DATA_DIR"] = tempfile.mkdtemp(prefix="taskly-test-")
os.environ["INBOUND_SECRET"] = "test-secret"
os.environ["DEBUG"] = "1"
os.environ["APP_TZ"] = "Asia/Kolkata"
os.environ.pop("ANTHROPIC_API_KEY", None)
os.environ.pop("STT_API_KEY", None)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import datetime  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import main  # noqa: E402

# Thursday 15 Oct 2026, 15:50 local
NOW = datetime(2026, 10, 15, 15, 50)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main, "now_local", lambda: NOW)
    with TestClient(main.app) as c:
        yield c
