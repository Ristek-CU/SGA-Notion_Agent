import asyncio
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings
from app.services.queue import QueueManager

client = TestClient(app)


def get_auth_token():
    res = client.post(
        "/admin/login",
        json={"username": settings.admin_user, "password": settings.admin_password},
    )
    data = res.json()
    if "token" in data.get("data", {}):
        return data["data"]["token"]

    session_id = data.get("session_id") or data.get("data", {}).get("session_id")
    import json
    from app.services.session import session_manager
    fake_redis = getattr(session_manager, "_fake_redis", None)
    raw = fake_redis.store.get(f"admin:otp:{session_id}") if fake_redis else None
    otp = json.loads(raw)["otp"] if raw else "123456"
    verify_res = client.post(
        "/admin/login/verify-otp",
        json={"session_id": session_id, "otp": otp},
    )
    return verify_res.json()["data"]["token"]


def test_contact_divisions_endpoint():
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}
    res = client.get("/admin/contacts/divisions", headers=headers)
    assert res.status_code == 200
    data = res.json()["data"]
    assert isinstance(data, list)
    assert len(data) > 0
    assert "BPH" in data


@pytest.mark.asyncio
@patch("app.admin.notify.record_audit_log", new=AsyncMock())
async def test_queue_endpoints():
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    # Test status endpoint
    res = client.get("/admin/queues/status", headers=headers)
    assert res.status_code == 200
    body = res.json()["data"]
    assert "chat_queue" in body
    assert "broadcast_jobs" in body

    # Also test alias /admin/broadcast/queues
    res2 = client.get("/admin/broadcast/queues", headers=headers)
    assert res2.status_code == 200

    # Test enqueue broadcast via API
    with patch("app.services.queue.QueueManager._run_broadcast_job", new=AsyncMock()):
        post_res = client.post(
            "/admin/broadcast",
            headers=headers,
            json={
                "message": "Halo test broadcast",
                "division": "BPH",
                "platform": "wa",
                "delay_seconds": 2.0,
            },
        )
        assert post_res.status_code == 200
        b_data = post_res.json()["data"]
        assert b_data["division"] == "BPH"
        assert b_data["platform"] == "wa"
        job_id = b_data["id"]

        # Cancel broadcast endpoint
        cancel_res = client.post(
            "/admin/broadcast/cancel",
            headers=headers,
            json={"job_id": job_id},
        )
        assert cancel_res.status_code == 200

        # Test active jobs endpoint
        active_res = client.get("/admin/broadcast/active", headers=headers)
        assert active_res.status_code == 200
        assert isinstance(active_res.json()["data"], list)

        # Test history jobs endpoint
        history_res = client.get("/admin/broadcast/history", headers=headers)
        assert history_res.status_code == 200
        assert isinstance(history_res.json()["data"], list)

        # Test job detail endpoint
        detail_res = client.get(f"/admin/broadcast/jobs/{job_id}", headers=headers)
        assert detail_res.status_code == 200
        d_data = detail_res.json()["data"]
        assert d_data["id"] == job_id
        assert "recipients" in d_data

        # Test resume endpoint
        with patch("app.services.queue.QueueManager.resume_broadcast", new=AsyncMock(return_value={"id": job_id, "status": "running"})):
            resume_res = client.post(f"/admin/broadcast/{job_id}/resume", headers=headers)
            assert resume_res.status_code == 200
            assert resume_res.json()["data"]["id"] == job_id


@pytest.mark.asyncio
async def test_broadcast_recipient_status_tracking():
    qm = QueueManager()
    qm.start()

    sent_targets = []

    async def dummy_wa_send(phone, text):
        if phone == "fail_phone":
            raise ValueError("Invalid phone number")
        sent_targets.append(phone)

    mock_contacts = [
        {"name": "Sukses User", "phone": "628111", "division": "Tech"},
        {"name": "Gagal User", "phone": "fail_phone", "division": "Tech"},
    ]

    with patch("app.services.contacts.get_all_contacts", new=AsyncMock(return_value=mock_contacts)), \
         patch("app.wa.sender.send_direct_message", side_effect=dummy_wa_send):

        job = await qm.enqueue_broadcast(
            message="Halo tim Tech",
            division="Tech",
            platform="wa",
            delay_seconds=0.01,
        )

        assert job["total"] == 2
        # Let worker finish sending both
        await asyncio.sleep(0.3)

        updated_job = await qm.get_job(job["id"])
        assert updated_job is not None
        assert updated_job["status"] == "completed"
        assert updated_job["sent"] == 1
        assert updated_job["failed"] == 1

        recipients = updated_job["recipients"]
        assert len(recipients) == 2

        r_success = next(r for r in recipients if r["target"] == "628111")
        assert r_success["status"] == "sent"
        assert r_success["error"] is None
        assert r_success["sent_at"] is not None

        r_fail = next(r for r in recipients if r["target"] == "fail_phone")
        assert r_fail["status"] == "failed"
        assert "Invalid phone number" in r_fail["error"]
        assert r_fail["sent_at"] is not None

    await qm.stop()


@pytest.mark.asyncio
async def test_telegram_broadcast_chat_id_lookup():
    qm = QueueManager()
    qm.start()

    sent_chat_ids = []

    async def dummy_tg_send(chat_id, text):
        sent_chat_ids.append(chat_id)

    mock_contacts = [
        {"name": "User With ChatID", "telegram": "salman_tg", "telegram_chat_id": "998877", "division": "Tech"},
        {"name": "User Without ChatID", "telegram": "no_chat_user", "telegram_chat_id": None, "division": "Tech"},
    ]

    with patch("app.services.contacts.get_all_contacts", new=AsyncMock(return_value=mock_contacts)), \
         patch("app.telegram.bot.send_telegram_message", side_effect=dummy_tg_send):

        job = await qm.enqueue_broadcast(
            message="Halo tim Telegram",
            division="Tech",
            platform="telegram",
            delay_seconds=0.01,
        )

        assert job["total"] == 2
        await asyncio.sleep(0.3)

        updated_job = await qm.get_job(job["id"])
        assert updated_job is not None
        assert updated_job["status"] == "completed"
        assert updated_job["sent"] == 1
        assert updated_job["failed"] == 1
        assert "998877" in sent_chat_ids

        r_fail = next(r for r in updated_job["recipients"] if r["target"] == "no_chat_user")
        assert r_fail["status"] == "failed"
        assert "telegram_chat_id tidak ditemukan" in r_fail["error"]

    await qm.stop()


@pytest.mark.asyncio
async def test_dual_priority_queue_yielding():
    qm = QueueManager()
    qm.start()

    events = []

    async def dummy_wa_send(phone, text):
        events.append(f"send_broadcast_{phone}")

    async def dummy_chat_handler():
        events.append("chat_processed")

    # Mock contacts for broadcast
    mock_contacts = [
        {"name": "User 1", "phone": "111", "division": "BPH"},
        {"name": "User 2", "phone": "222", "division": "BPH"},
        {"name": "User 3", "phone": "333", "division": "BPH"},
    ]

    with patch("app.services.contacts.get_all_contacts", new=AsyncMock(return_value=mock_contacts)), \
         patch("app.wa.sender.send_direct_message", side_effect=dummy_wa_send):

        job = await qm.enqueue_broadcast(
            message="Notice",
            division="BPH",
            platform="wa",
            delay_seconds=0.3,
        )
        assert job["total"] == 3

        # Wait tiny bit for broadcast to start
        await asyncio.sleep(0.05)

        # Enqueue high priority chat
        await qm.enqueue_chat(
            handler=dummy_chat_handler,
            sender="Tester",
            platform="WhatsApp",
            preview="Hi bot",
        )

        # Let queue run (chat cooldown is 3s)
        await asyncio.sleep(4.0)

        # Verify chat processed and broadcast yielded
        assert "chat_processed" in events
        assert any(e.startswith("send_broadcast") for e in events)

    await qm.stop()


@pytest.mark.asyncio
async def test_broadcast_jitter_and_cooling_pause():
    qm = QueueManager()
    qm.start()

    sleep_calls = []

    async def mock_asyncio_sleep(duration):
        sleep_calls.append(duration)

    # 13 contacts to trigger batch cooling pause (threshold is 10-12)
    mock_contacts = [
        {"name": f"User {i}", "phone": f"62800{i}", "division": "Tech"}
        for i in range(13)
    ]

    with patch("app.services.contacts.get_all_contacts", new=AsyncMock(return_value=mock_contacts)), \
         patch("app.wa.sender.send_direct_message", new=AsyncMock()), \
         patch.object(qm, "_db_create_broadcast_job", new=AsyncMock()), \
         patch.object(qm, "_db_update_recipient", new=AsyncMock()), \
         patch.object(qm, "_db_update_job_status", new=AsyncMock()), \
         patch("asyncio.sleep", side_effect=mock_asyncio_sleep), \
         patch("random.uniform", side_effect=lambda a, b: 2.0 if (a == 1.5 and b == 4.5) else (15.0 if (a == 12.0 and b == 20.0) else (a + b) / 2)), \
         patch("random.randint", return_value=11):

        job_dict = {
            "id": "job_jitter_test",
            "message": "Testing jitter",
            "division": "Tech",
            "platform": "wa",
            "delay_seconds": 5.0,
            "recipients": [
                {
                    "contact_id": str(i),
                    "name": f"User {i}",
                    "platform": "wa",
                    "target": f"62800{i}",
                    "division": "Tech",
                    "status": "pending",
                    "error": None,
                    "sent_at": None,
                }
                for i in range(13)
            ],
            "total": 13,
            "sent": 0,
            "failed": 0,
            "status": "waiting",
        }

        await qm._run_broadcast_job(job_dict)

        assert job_dict["sent"] == 13
        assert job_dict["status"] == "completed"

        # Check that jitter delay was applied: base_delay 5.0 + jitter 2.0 = 7.0s
        # Total sleep calls should include 0.5s steps adding up to 7.0s per message, plus cooling pause (15.0s)
        total_sleep_time = sum(sleep_calls)
        # 13 items * 7.0s = 91.0s, plus 1 cooling break of 15.0s = 106.0s
        assert total_sleep_time >= 105.0

    await qm.stop()


@pytest.mark.asyncio
async def test_broadcast_auto_pause_on_waha_failure():
    from app.wa.sender import WAHASessionNotWorkingError

    qm = QueueManager()
    qm.start()

    alert_sent = []

    async def mock_tg_send(chat_id, text):
        alert_sent.append({"chat_id": chat_id, "text": text})

    def mock_wa_fail(*args, **kwargs):
        raise WAHASessionNotWorkingError("WAHA session is not WORKING")

    job_dict = {
        "id": "job_autopause_test",
        "message": "Testing auto pause",
        "division": "Tech",
        "platform": "wa",
        "delay_seconds": 1.0,
        "recipients": [
            {
                "contact_id": "1",
                "name": "User 1",
                "platform": "wa",
                "target": "628001",
                "division": "Tech",
                "status": "pending",
                "error": None,
                "sent_at": None,
            },
            {
                "contact_id": "2",
                "name": "User 2",
                "platform": "wa",
                "target": "628002",
                "division": "Tech",
                "status": "pending",
                "error": None,
                "sent_at": None,
            },
        ],
        "total": 2,
        "sent": 0,
        "failed": 0,
        "status": "running",
    }

    with patch("app.wa.sender.send_direct_message", side_effect=mock_wa_fail), \
         patch("app.telegram.bot.send_telegram_message", side_effect=mock_tg_send), \
         patch.object(qm, "_db_update_job_status", new=AsyncMock()), \
         patch.object(qm, "_db_update_recipient", new=AsyncMock()):

        await qm._run_broadcast_job(job_dict)

        assert job_dict["status"] == "paused"
        # Remaining recipients should stay pending (not failed!)
        assert job_dict["recipients"][0]["status"] == "pending"
        assert job_dict["recipients"][1]["status"] == "pending"
        assert len(alert_sent) == 1
        assert alert_sent[0]["chat_id"] == "6894908477"
        assert "Sesi WhatsApp Terputus" in alert_sent[0]["text"]
        assert "job_autopause_test" in alert_sent[0]["text"]

    await qm.stop()


@pytest.mark.asyncio
async def test_broadcast_resume():
    qm = QueueManager()
    qm.start()

    sent_targets = []

    async def mock_wa_send(target, text):
        sent_targets.append(target)

    job_dict = {
        "id": "job_resume_test",
        "message": "Testing resume",
        "division": "Tech",
        "platform": "wa",
        "delay_seconds": 0.01,
        "recipients": [
            {
                "contact_id": "1",
                "name": "User 1",
                "platform": "wa",
                "target": "628001",
                "division": "Tech",
                "status": "sent",
                "error": None,
                "sent_at": 123456.0,
            },
            {
                "contact_id": "2",
                "name": "User 2",
                "platform": "wa",
                "target": "628002",
                "division": "Tech",
                "status": "pending",
                "error": None,
                "sent_at": None,
            },
        ],
        "total": 2,
        "sent": 1,
        "failed": 0,
        "status": "paused",
    }
    qm.broadcast_jobs.append(job_dict)

    with patch("app.wa.sender.get_session_status", new=AsyncMock(return_value="WORKING")), \
         patch("app.wa.sender.send_direct_message", side_effect=mock_wa_send), \
         patch.object(qm, "_db_update_job_status", new=AsyncMock()), \
         patch.object(qm, "_db_update_recipient", new=AsyncMock()):

        res = await qm.resume_broadcast("job_resume_test")
        assert res["id"] == "job_resume_test"

        # Allow worker task to run
        await asyncio.sleep(0.1)

        assert "628002" in sent_targets
        assert "628001" not in sent_targets  # was already sent
        assert job_dict["status"] == "completed"
        assert job_dict["sent"] == 2

    await qm.stop()


