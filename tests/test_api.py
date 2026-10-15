from app import ai

HEADERS = {"x-inbound-secret": "test-secret"}


def make(client, text, **kw):
    r = client.post("/api/tasks", json={"text": text, **kw})
    assert r.status_code == 201, r.text
    return r.json()


def test_create_recurring_task_and_views(client):
    t = make(client, "set a remainder for every tuesday, thursday 5pm runnning")
    assert t["title"] == "Runnning"
    assert t["recurrence_text"] == "Every Tue, Thu at 5:00 PM"
    assert (t["due_date"], t["due_time"]) == ("2026-10-15", "17:00")
    assert t["email"].startswith("t-") and t["email"].endswith("@inbox.taskly.local")
    assert any(x["id"] == t["id"] for x in client.get("/api/tasks?view=today").json())


def test_completing_recurring_task_moves_it_forward(client):
    t = make(client, "every tuesday and thursday at 5pm gym")
    r = client.post(f"/api/tasks/{t['id']}/complete").json()
    assert r["done"] is False and r["due_date"] == "2026-10-20"      # Thursday -> next Tuesday
    r = client.post(f"/api/tasks/{t['id']}/complete").json()
    assert r["due_date"] == "2026-10-22"


def test_completing_normal_task(client):
    t = make(client, "buy milk tomorrow")
    assert client.post(f"/api/tasks/{t['id']}/complete").json()["done"] is True
    assert any(x["id"] == t["id"] for x in client.get("/api/tasks?view=completed").json())
    assert client.post(f"/api/tasks/{t['id']}/reopen").json()["done"] is False


def test_project_tag_creates_project(client):
    t = make(client, "read paper #Research-Lab p2")
    assert t["project_name"] == "Research-Lab" and t["priority"] == 2


def test_patch_schedule(client):
    t = make(client, "stretch")
    r = client.patch(f"/api/tasks/{t['id']}", json={"schedule": "every mon at 9am"}).json()
    assert r["recurrence_text"] == "Every Mon at 9:00 AM" and r["due_date"] == "2026-10-19"
    assert client.patch(f"/api/tasks/{t['id']}", json={"schedule": ""}).json()["due_date"] is None
    assert client.patch(f"/api/tasks/{t['id']}", json={"schedule": "blah"}).status_code == 422


def test_patch_date_and_time(client):
    t = make(client, "wash car")
    r = client.patch(f"/api/tasks/{t['id']}", json={"due_date": "2026-10-17", "due_time": "04:40"}).json()
    assert r["due_date"] == "2026-10-17"
    assert r["due_time"] == "04:40"
    r2 = client.patch(f"/api/tasks/{t['id']}", json={"due_time": ""}).json()
    assert r2["due_date"] == "2026-10-17"
    assert r2["due_time"] is None


def test_quick_add_validation(client):
    assert client.post("/api/tasks", json={"text": "   every tuesday 5pm"}).status_code == 422


# ---------------------------------------------------------------- email -> comment
def test_email_becomes_comment(client):
    t = make(client, "plan offsite")
    payload = {"recipient": t["email"], "sender": "Asha <asha@example.com>", "subject": "Venue",
               "text": "Booked the hall for Friday.\n\nOn Mon, 12 Oct 2026, Ritu wrote:\n> earlier text\n",
               "Message-Id": "<abc@mail>"}
    r = client.post("/api/email/inbound", json=payload, headers=HEADERS).json()
    assert r["status"] == "ok"
    c = client.get(f"/api/tasks/{t['id']}/comments").json()
    assert len(c) == 1 and c[0]["kind"] == "email"
    assert c[0]["body"] == "Booked the hall for Friday." and c[0]["subject"] == "Venue"
    # same Message-Id delivered twice -> ignored
    assert client.post("/api/email/inbound", json=payload, headers=HEADERS).json()["status"] == "duplicate"
    assert len(client.get(f"/api/tasks/{t['id']}/comments").json()) == 1


def test_email_security(client):
    t = make(client, "secret task")
    body = {"recipient": t["email"], "text": "hi"}
    assert client.post("/api/email/inbound", json=body).status_code == 401
    assert client.post("/api/email/inbound", json=body, headers={"x-inbound-secret": "nope"}).status_code == 401
    unknown = {"recipient": "t-000000000000@inbox.taskly.local", "text": "hi"}
    assert client.post("/api/email/inbound", json=unknown, headers=HEADERS).json()["status"] == "unknown_recipient"


def test_email_form_encoded_like_mailgun(client):
    t = make(client, "form task")
    r = client.post("/api/email/inbound", data={"recipient": t["email"], "stripped-text": "via form",
                    "sender": "x@y.z", "Message-Id": "<m1>"}, headers=HEADERS)
    assert r.json()["status"] == "ok"


# ---------------------------------------------------------------- voice
def test_voice_command_offline_rules(client):
    r = client.post("/api/voice/interpret",
                    json={"text": "set a remainder for every tuesday, thursday 5pm running"}).json()
    assert r["ok"] and r["task"]["title"] == "Running"
    assert r["task"]["recurrence_text"] == "Every Tue, Thu at 5:00 PM"
    done = client.post("/api/voice/interpret", json={"text": "mark running as done"}).json()
    assert done["ok"] and done["intent"] == "complete_task" and done["task"]["due_date"] == "2026-10-20"
    cm = client.post("/api/voice/interpret", json={"text": "add comment on running: bring water bottle"}).json()
    assert cm["ok"] and cm["task"]["comment_count"] == 1


def test_voice_command_with_llm(client, monkeypatch):
    async def fake(transcript, now, open_tasks):
        return {"intent": "add_task", "title": "Running", "schedule": "every tuesday and thursday at 5pm", "priority": 2}
    monkeypatch.setattr(ai, "interpret", fake)
    r = client.post("/api/voice/interpret", json={"text": "reminder every tuesday thursday five pm runnning"}).json()
    assert r["task"]["title"] == "Running" and r["task"]["priority"] == 2
    assert r["task"]["recurrence_text"] == "Every Tue, Thu at 5:00 PM"


def test_voice_command_audio_upload(client, monkeypatch):
    async def fake_stt(audio, filename, content_type):
        return "remind me to call dad tomorrow at 6pm"
    monkeypatch.setattr(ai, "transcribe", fake_stt)
    r = client.post("/api/voice/command", files={"audio": ("a.webm", b"fake-bytes", "audio/webm;codecs=opus")})
    assert r.status_code == 200 and r.json()["task"]["title"] == "Call dad"
    assert client.post("/api/voice/command", files={"audio": ("a.txt", b"x", "text/plain")}).status_code == 415


def test_voice_command_without_stt_key_says_so(client):
    r = client.post("/api/voice/command", files={"audio": ("a.webm", b"fake", "audio/webm")})
    assert r.status_code == 503


def test_voice_note_is_stored_and_playable(client, monkeypatch):
    async def fake_stt(audio, filename, content_type):
        return "remember to bring the keys"
    monkeypatch.setattr(ai, "transcribe", fake_stt)
    t = make(client, "meeting")
    c = client.post(f"/api/tasks/{t['id']}/voice-note",
                    files={"audio": ("n.webm", b"RIFFdata", "audio/webm")}).json()
    assert c["kind"] == "voice" and c["body"] == "remember to bring the keys"
    assert client.get(c["audio_url"]).content == b"RIFFdata"
    assert client.get("/api/audio/..%2F..%2Fetc%2Fpasswd").status_code == 404
    assert client.get("/api/audio/not-a-real-name.webm").status_code == 404


def test_voice_note_without_stt_still_saves_audio(client):
    t = make(client, "meeting 2")
    r = client.post(f"/api/tasks/{t['id']}/voice-note", files={"audio": ("n.webm", b"abc", "audio/webm")})
    assert r.status_code == 201 and r.json()["audio_url"] and r.json()["body"] == ""
