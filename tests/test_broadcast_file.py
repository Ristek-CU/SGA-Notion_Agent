import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.services.queue import QueueManager, resolve_file_url_for_waha
from app.wa.sender import send_whatsapp_file
from app.telegram.bot import send_telegram_document


def test_resolve_file_url_for_waha():
    # Relative path
    rel = "/uploads/test.pdf"
    resolved = resolve_file_url_for_waha(rel)
    assert resolved.startswith("http")
    assert "/uploads/test.pdf" in resolved

    # Absolute URL
    abs_url = "https://roro-api.mannn.app/uploads/test.pdf"
    assert resolve_file_url_for_waha(abs_url) == abs_url


@pytest.mark.asyncio
async def test_send_whatsapp_file_payload():
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": "waha_msg_123"}
        mock_post.return_value = mock_resp

        res = await send_whatsapp_file(
            number_or_jid="628123456789",
            file_url="https://roro-api.mannn.app/uploads/Tutorial-roro.pdf",
            filename="Tutorial-roro.pdf",
            caption="*Halo* ini file tutorial",
            mimetype="application/pdf",
        )

        assert res["id"] == "waha_msg_123"
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert "/api/sendFile" in args[0]
        json_body = kwargs["json"]
        assert json_body["chatId"] == "628123456789@c.us"
        assert json_body["file"]["url"] == "https://roro-api.mannn.app/uploads/Tutorial-roro.pdf"
        assert json_body["file"]["filename"] == "Tutorial-roro.pdf"
        assert json_body["file"]["mimetype"] == "application/pdf"
        assert "caption" in json_body


@pytest.mark.asyncio
async def test_send_telegram_document():
    with patch("app.telegram.bot.get_platform_token", new=AsyncMock(return_value="test_bot_token")), \
         patch("app.telegram.bot.tg_call", new_callable=AsyncMock) as mock_tg_call:
        mock_tg_call.return_value = {"message_id": 999}

        res = await send_telegram_document(
            chat_id="12345678",
            document_url="https://roro-api.mannn.app/uploads/Tutorial-roro.pdf",
            caption="Ini tutorial roro",
            filename="Tutorial-roro.pdf",
        )

        assert res["message_id"] == 999
        mock_tg_call.assert_called_once()
        token, method, payload = mock_tg_call.call_args[0]
        assert method == "sendDocument"
        assert payload["chat_id"] == "12345678"
        assert payload["document"] == "https://roro-api.mannn.app/uploads/Tutorial-roro.pdf"
        assert "caption" in payload


@pytest.mark.asyncio
async def test_queue_broadcast_with_attachment():
    qm = QueueManager()

    mock_contacts = [
        {"id": 1, "name": "Budi", "phone": "62899991", "division": "Tech"},
        {"id": 2, "name": "Andi", "telegram": "@andi", "telegram_chat_id": "98765", "division": "Tech"},
    ]

    sent_wa_files = []
    sent_tg_docs = []

    async def dummy_wa_file(number_or_jid, file_url, filename=None, caption=None, mimetype=None, instance=None):
        sent_wa_files.append({"to": number_or_jid, "url": file_url, "filename": filename, "caption": caption})
        return {"id": "wa_msg_ok"}

    async def dummy_tg_doc(chat_id, document_url, caption=None, filename=None):
        sent_tg_docs.append({"to": chat_id, "url": document_url, "filename": filename, "caption": caption})
        return {"message_id": 100}

    with patch("app.services.contacts.get_all_contacts", new=AsyncMock(return_value=mock_contacts)), \
         patch.object(qm, "_db_create_broadcast_job", new=AsyncMock()), \
         patch.object(qm, "_db_update_recipient", new=AsyncMock()), \
         patch.object(qm, "_db_update_job_status", new=AsyncMock()), \
         patch("app.wa.sender.send_whatsapp_file", side_effect=dummy_wa_file), \
         patch("app.telegram.bot.send_telegram_document", side_effect=dummy_tg_doc):

        job = await qm.enqueue_broadcast(
            message="Halo ini file tutorial roro",
            division="Tech",
            platform="all",
            delay_seconds=0.01,
            file_url="https://roro-api.mannn.app/uploads/Tutorial-roro.pdf",
            file_name="Tutorial-roro.pdf",
            file_mimetype="application/pdf",
            file_size=102400,
        )

        assert job["file_name"] == "Tutorial-roro.pdf"
        assert job["file_url"] == "https://roro-api.mannn.app/uploads/Tutorial-roro.pdf"
        assert job["total"] == 2

        # Allow worker to complete
        await asyncio.sleep(0.15)

        assert len(sent_wa_files) == 1
        assert sent_wa_files[0]["to"] == "62899991"
        assert sent_wa_files[0]["filename"] == "Tutorial-roro.pdf"

        assert len(sent_tg_docs) == 1
        assert sent_tg_docs[0]["to"] == "98765"
        assert sent_tg_docs[0]["filename"] == "Tutorial-roro.pdf"

        # Check job status in memory
        in_mem = next(j for j in qm.broadcast_jobs if j["id"] == job["id"])
        assert in_mem["sent"] == 2
        assert in_mem["status"] == "completed"


def test_broadcast_upload_api():
    from app.config import settings
    client_test = TestClient(app)
    res_login = client_test.post(
        "/admin/login",
        json={"username": settings.admin_user, "password": settings.admin_password},
    )
    login_data = res_login.json()
    if "token" in login_data.get("data", {}):
        token = login_data["data"]["token"]
    else:
        sid = login_data.get("session_id") or login_data["data"]["session_id"]
        import json
        from app.services.session import session_manager
        fake_redis = getattr(session_manager, "_fake_redis", None)
        raw = fake_redis.store.get(f"admin:otp:{sid}") if fake_redis else None
        otp = json.loads(raw)["otp"] if raw else "123456"
        v_res = client_test.post(
            "/admin/login/verify-otp",
            json={"session_id": sid, "otp": otp},
        )
        token = v_res.json()["data"]["token"]
    headers = {"Authorization": f"Bearer {token}"}

    test_content = b"%PDF-1.4 dummy pdf file content"
    files = {
        "file": ("Tutorial-roro.pdf", test_content, "application/pdf")
    }

    res = client_test.post("/admin/broadcast/upload", files=files, headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["data"]["file_name"] == "Tutorial-roro.pdf"
    assert body["data"]["file_mimetype"] == "application/pdf"
    assert "/uploads/" in body["data"]["file_url"]
