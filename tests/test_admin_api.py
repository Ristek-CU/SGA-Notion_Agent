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


def test_admin_guard_config_toggle():
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


@patch("app.admin.wa._evolution_request")
def test_admin_wa_status(mock_evo):
    mock_evo.return_value = {"state": "open"}
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/admin/wa/status", headers=headers)
    assert res.status_code == 200
    assert res.json()["data"]["state"] == "open"


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
