import json
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings
from app.services.session import session_manager

client = TestClient(app)


def test_login_invalid_credentials():
    res = client.post(
        "/admin/login",
        json={"username": "wrong_user", "password": "wrong_password"},
    )
    assert res.status_code == 401
    assert "Username atau password salah" in res.json()["detail"]


@patch("app.admin.auth.send_whatsapp_message", new_callable=AsyncMock)
@patch("app.admin.auth.send_telegram_message", new_callable=AsyncMock)
def test_login_step1_generates_otp_and_notifies(mock_tg, mock_wa):
    mock_wa.return_value = {"success": True}
    mock_tg.return_value = {"ok": True}

    res = client.post(
        "/admin/login",
        json={"username": settings.admin_user, "password": settings.admin_password},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "otp_required"
    assert "session_id" in data
    assert data["expires_in"] == 300
    assert "Kode OTP telah dikirim" in data["message"]

    # Verify notification sent to Salman
    mock_wa.assert_called_once()
    assert mock_wa.call_args[0][0] == "6285175019086"
    assert "Kode OTP Anda:" in mock_wa.call_args[0][1]

    mock_tg.assert_called_once()
    assert mock_tg.call_args[0][0] == "195340229"
    assert "Kode OTP Anda:" in mock_tg.call_args[0][1]

    # Verify OTP saved in redis
    fake_redis = getattr(session_manager, "_fake_redis", None)
    assert fake_redis is not None
    key = f"admin:otp:{data['session_id']}"
    assert key in fake_redis.store
    stored = json.loads(fake_redis.store[key])
    assert len(stored["otp"]) == 6
    assert stored["otp"].isdigit()
    assert stored["attempts"] == 0


def test_verify_otp_invalid_session():
    res = client.post(
        "/admin/login/verify-otp",
        json={"session_id": "non_existent_session", "otp": "123456"},
    )
    assert res.status_code == 400
    assert "kadaluarsa" in res.json()["detail"]


@patch("app.admin.auth.send_whatsapp_message", new_callable=AsyncMock)
@patch("app.admin.auth.send_telegram_message", new_callable=AsyncMock)
def test_verify_otp_wrong_code_and_rate_limit(mock_tg, mock_wa):
    # Step 1: Request OTP
    res1 = client.post(
        "/admin/login",
        json={"username": settings.admin_user, "password": settings.admin_password},
    )
    sid = res1.json()["session_id"]
    fake_redis = getattr(session_manager, "_fake_redis", None)
    stored = json.loads(fake_redis.store[f"admin:otp:{sid}"])
    correct_otp = stored["otp"]
    wrong_otp = "000000" if correct_otp != "000000" else "111111"

    # Step 2: Try wrong OTP 4 times
    for i in range(1, 5):
        res = client.post(
            "/admin/login/verify-otp",
            json={"session_id": sid, "otp": wrong_otp},
        )
        assert res.status_code == 400
        assert f"Sisa percobaan: {5 - i}" in res.json()["detail"]

    # 5th attempt (reaching max limit)
    res5 = client.post(
        "/admin/login/verify-otp",
        json={"session_id": sid, "otp": wrong_otp},
    )
    assert res5.status_code == 400

    # 6th attempt (exceeded max limit) -> 429 Too Many Requests and key deleted
    res6 = client.post(
        "/admin/login/verify-otp",
        json={"session_id": sid, "otp": wrong_otp},
    )
    assert res6.status_code == 429
    assert "Batas percobaan OTP terlampaui" in res6.json()["detail"]
    assert f"admin:otp:{sid}" not in fake_redis.store


@patch("app.admin.auth.send_whatsapp_message", new_callable=AsyncMock)
@patch("app.admin.auth.send_telegram_message", new_callable=AsyncMock)
def test_verify_otp_success_and_invalidation(mock_tg, mock_wa):
    # 1. Login
    res1 = client.post(
        "/admin/login",
        json={"username": settings.admin_user, "password": settings.admin_password},
    )
    sid = res1.json()["session_id"]
    fake_redis = getattr(session_manager, "_fake_redis", None)
    stored = json.loads(fake_redis.store[f"admin:otp:{sid}"])
    otp = stored["otp"]

    # 2. Verify with correct OTP
    res2 = client.post(
        "/admin/login/verify-otp",
        json={"session_id": sid, "otp": otp},
    )
    assert res2.status_code == 200
    body = res2.json()
    assert body["status"] == "success"
    assert "token" in body
    assert body["user"] == settings.admin_user
    assert "token" in body["data"]

    # 3. Verify OTP invalidated in Redis
    assert f"admin:otp:{sid}" not in fake_redis.store

    # 4. Trying to verify again fails
    res3 = client.post(
        "/admin/login/verify-otp",
        json={"session_id": sid, "otp": otp},
    )
    assert res3.status_code == 400


@patch("app.admin.auth.send_whatsapp_message", new_callable=AsyncMock)
@patch("app.admin.auth.send_telegram_message", new_callable=AsyncMock)
def test_resend_otp_flow(mock_tg, mock_wa):
    # 1. Login
    res1 = client.post(
        "/admin/login",
        json={"username": settings.admin_user, "password": settings.admin_password},
    )
    sid = res1.json()["session_id"]
    fake_redis = getattr(session_manager, "_fake_redis", None)
    old_otp = json.loads(fake_redis.store[f"admin:otp:{sid}"])["otp"]

    # 2. Resend OTP
    res2 = client.post(
        "/admin/login/resend-otp",
        json={"session_id": sid},
    )
    assert res2.status_code == 200
    assert res2.json()["status"] == "resent"

    new_stored = json.loads(fake_redis.store[f"admin:otp:{sid}"])
    new_otp = new_stored["otp"]
    assert new_stored["attempts"] == 0

    # 3. Old OTP no longer valid if new OTP is different
    # (new OTP is freshly generated)
    # 4. Verify with new OTP succeeds
    res3 = client.post(
        "/admin/login/verify-otp",
        json={"session_id": sid, "otp": new_otp},
    )
    assert res3.status_code == 200
    assert "token" in res3.json()


def test_otp_disabled_fallback(monkeypatch):
    monkeypatch.setattr(settings, "otp_enabled", False)
    res = client.post(
        "/admin/login",
        json={"username": settings.admin_user, "password": settings.admin_password},
    )
    assert res.status_code == 200
    data = res.json()
    assert "token" in data["data"]
    assert data["message"] == "Login successful"
