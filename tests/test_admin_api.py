import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings

client = TestClient(app)


def test_admin_login_success():
    res = client.post(
        "/admin/login",
        json={"username": settings.admin_user, "password": settings.admin_password},
    )
    assert res.status_code == 200
    data = res.json()
    assert "data" in data
    assert "token" in data["data"]
    assert data["data"]["user"]["username"] == settings.admin_user


def test_admin_login_invalid():
    res = client.post(
        "/admin/login",
        json={"username": "wrong_user", "password": "wrong_password"},
    )
    assert res.status_code == 401


def test_admin_unauthorized_access():
    res = client.get("/admin/system/env")
    assert res.status_code == 403 or res.status_code == 401


def get_auth_token():
    res = client.post(
        "/admin/login",
        json={"username": settings.admin_user, "password": settings.admin_password},
    )
    return res.json()["data"]["token"]


def test_admin_system_env():
    token = get_auth_token()
    res = client.get(
        "/admin/system/env",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["data"]["NODE_ENV"] == settings.node_env


@patch("app.admin.notify.record_audit_log")
@patch("app.admin.notify.get_guard_state")
@patch("app.admin.notify.update_guard_state")
def test_admin_guard_config_toggle(mock_update, mock_get, mock_audit):
    mock_get.return_value = {"enabled": True, "strict_mode": True}
    mock_update.return_value = {"enabled": False, "strict_mode": True}
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/admin/guard/config", headers=headers)
    assert res.status_code == 200
    assert res.json()["data"]["enabled"] is True

    res2 = client.post("/admin/guard/config", json={"enabled": False}, headers=headers)
    assert res2.status_code == 200
    assert res2.json()["data"]["enabled"] is False


def test_admin_contacts_crud():
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    # List contacts
    res = client.get("/admin/contacts", headers=headers)
    assert res.status_code == 200

    # Add contact
    res_add = client.post(
        "/admin/contacts",
        json={"name": "Test User", "phone": "628999000", "role": "Tester", "division": "Ristek"},
        headers=headers,
    )
    assert res_add.status_code == 200
    assert res_add.json()["data"]["name"] == "Test User"

    # Delete contact
    res_del = client.delete("/admin/contacts/628999000", headers=headers)
    assert res_del.status_code == 200


@patch("app.admin.wa._waha_request")
def test_admin_wa_status(mock_waha):
    mock_waha.return_value = {"name": "wa-bot", "status": "WORKING"}
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/admin/wa/status", headers=headers)
    assert res.status_code == 200
    assert res.json()["data"]["status"] == "WORKING"


@patch("app.admin.wa._waha_request")
def test_admin_wa_test_connection(mock_waha):
    mock_waha.return_value = {
        "name": "wa-bot",
        "status": "WORKING",
        "me": {"id": "6285111219086@c.us", "pushName": "Bot Admin"},
        "engine": {"engine": "WEBJS", "state": "CONNECTED"},
        "config": {
            "webhooks": [
                {"url": settings.waha_webhook_url, "events": ["message"]}
            ]
        },
    }
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/admin/wa/test", headers=headers)
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["ok"] is True
    assert data["phone"] == "6285111219086@c.us"
    assert data["pushName"] == "Bot Admin"
    assert data["webhook_configured"] is True


@patch("app.admin.platforms._tg")
@patch("app.services.platform_config.save_platform_config")
@patch("app.services.platform_config.load_platform_config")
def test_admin_telegram_put_auto_webhook(mock_load, mock_save, mock_tg):
    from app.services.platform_config import PlatformConfig
    mock_load.return_value = PlatformConfig(enabled=True, bot_token="123456:ABC-DEF")
    mock_save.return_value = True
    mock_tg.return_value = True

    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    res = client.put(
        "/admin/platforms/telegram",
        json={"enabled": True, "bot_token": "123456:ABC-DEF"},
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["enabled"] is True
    assert "webhook" in data
    assert data["webhook"]["result"] is True
    mock_tg.assert_called_once()


@patch("app.admin.notion.query_tickets_direct")
@patch("app.admin.notion.get_backlog_stats")
def test_admin_notion_backlog(mock_stats, mock_tickets):
    mock_tickets.return_value = [
        {"id": "t1", "title": "Fix bug", "status": "In Progress", "division": "Ristek", "pic": "Budi"},
    ]
    mock_stats.return_value = {"total": 1, "by_status": {"In Progress": 1}, "by_division": {"Ristek": 1}}
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/admin/notion/backlog", headers=headers)
    assert res.status_code == 200
    assert len(res.json()["data"]) == 1

    res_overview = client.get("/admin/notion/overview", headers=headers)
    assert res_overview.status_code == 200
    assert res_overview.json()["data"]["total"] == 1
