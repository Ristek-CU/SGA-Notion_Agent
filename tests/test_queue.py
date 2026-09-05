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
    return res.json()["data"]["token"]


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

        updated_job = qm.get_job(job["id"])
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

        updated_job = qm.get_job(job["id"])
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

        # Let queue run
        await asyncio.sleep(3.6)

        # Verify chat processed and broadcast yielded
        assert "chat_processed" in events
        assert any(e.startswith("send_broadcast") for e in events)

    await qm.stop()
