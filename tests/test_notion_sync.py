import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.notion_sync import (
    extract_member_data,
    get_division_mapping,
    sync_notion_members_to_contacts,
    update_notion_member_phone,
)
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings

client = TestClient(app)


def test_extract_member_data_valid():
    page = {
        "id": "notion-page-123",
        "properties": {
            "Member Name": {
                "type": "title",
                "title": [{"plain_text": "budi santoso"}],
            },
            "WhatsApp": {
                "type": "rich_text",
                "rich_text": [{"plain_text": "08123456789"}],
            },
            "Role": {
                "type": "select",
                "select": {"name": "Staff of Division"},
            },
            "Division": {
                "type": "relation",
                "relation": [{"id": "div-page-456"}],
            },
        },
    }
    div_map = {"div-page-456": "Research and Technology"}
    extracted = extract_member_data(page, div_map)

    assert extracted is not None
    assert extracted["notion_member_id"] == "notion-page-123"
    assert extracted["name"] == "Budi Santoso"
    assert extracted["phone"] == "628123456789"
    assert extracted["role"] == "Staff of Division"
    assert extracted["division"] == "Research and Technology"


def test_extract_member_data_missing_name():
    page = {
        "id": "notion-page-999",
        "properties": {
            "Member Name": {
                "type": "title",
                "title": [],
            },
        },
    }
    extracted = extract_member_data(page)
    assert extracted is None


@pytest.mark.asyncio
async def test_get_division_mapping():
    mock_client = MagicMock()
    mock_client.query_all = AsyncMock(return_value=[
        {
            "id": "div-1",
            "properties": {
                "Division Name": {
                    "type": "title",
                    "title": [{"plain_text": "Research and Technology"}],
                }
            }
        },
        {
            "id": "div-2",
            "properties": {
                "Division Name": {
                    "type": "title",
                    "title": [{"plain_text": "Executive"}],
                }
            }
        }
    ])

    mapping = await get_division_mapping(mock_client)
    assert mapping["div-1"] == "Research and Technology"
    assert mapping["div-2"] == "Executive"


@pytest.mark.asyncio
async def test_sync_notion_members_to_contacts():
    mock_pages = [
        {
            "id": "notion-p1",
            "properties": {
                "Member Name": {"type": "title", "title": [{"plain_text": "User One"}]},
                "WhatsApp": {"type": "rich_text", "rich_text": [{"plain_text": "0811111111"}]},
                "Role": {"type": "select", "select": {"name": "Staff"}},
                "Division": {"type": "relation", "relation": [{"id": "div-1"}]},
            }
        },
        {
            "id": "notion-p2",
            "properties": {
                "Member Name": {"type": "title", "title": [{"plain_text": "User Two"}]},
                "WhatsApp": {"type": "rich_text", "rich_text": [{"plain_text": "0822222222"}]},
                "Role": {"type": "select", "select": {"name": "Head"}},
                "Division": {"type": "relation", "relation": []},
            }
        }
    ]

    with patch("app.services.notion_sync.get_division_mapping", new=AsyncMock(return_value={"div-1": "Ristek"})), \
         patch("app.notion.core.NotionClient.query_all", new=AsyncMock(return_value=mock_pages)), \
         patch("app.services.database.get_db_pool", new=AsyncMock(return_value=None)), \
         patch("app.services.contacts.add_or_update_contact", new=AsyncMock(return_value={"status": "ok"})):

        res = await sync_notion_members_to_contacts()
        assert res["success"] is True
        assert res["total_notion_pages"] == 2
        assert res["updated"] == 2


@pytest.mark.asyncio
async def test_update_notion_member_phone():
    with patch("app.notion.core.NotionClient.request", new=AsyncMock(return_value={"id": "page-123"})) as mock_req:
        res = await update_notion_member_phone("page-123", "08123456789")
        assert res is True
        mock_req.assert_called_once()
        args, kwargs = mock_req.call_args
        assert args[0] == "PATCH"
        assert args[1] == "/pages/page-123"
        assert kwargs["body"]["properties"]["WhatsApp"]["rich_text"][0]["text"]["content"] == "628123456789"


@pytest.mark.asyncio
async def test_sync_notion_members_match_by_name_in_db():
    mock_pages = [
        {
            "id": "notion-salman",
            "properties": {
                "Member Name": {"type": "title", "title": [{"plain_text": "Muhammad Salman Firdaus"}]},
                "WhatsApp": {"type": "rich_text", "rich_text": [{"plain_text": "6285175019086"}]},
                "Role": {"type": "select", "select": {"name": "Staff"}},
                "Division": {"type": "relation", "relation": []},
            }
        }
    ]

    mock_conn = AsyncMock()
    # 1st call by notion_id -> None
    # 2nd call by phone -> None (misal nomor lama di DB masih beda)
    # 3rd call by name -> existing row
    mock_conn.fetchrow.side_effect = [
        None,
        None,
        {"id": 103, "name": "Muhammad Salman Firdaus", "phone": "62851727834", "telegram": "pangestuu19", "telegram_chat_id": "195340229"},
    ]
    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

    with patch("app.services.notion_sync.get_division_mapping", new=AsyncMock(return_value={})), \
         patch("app.notion.core.NotionClient.query_all", new=AsyncMock(return_value=mock_pages)), \
         patch("app.services.database.get_db_pool", new=AsyncMock(return_value=mock_pool)), \
         patch("app.services.contacts.get_all_contacts", new=AsyncMock(return_value=[])), \
         patch("app.services.contacts._save_contacts_to_file"):

        res = await sync_notion_members_to_contacts()
        assert res["success"] is True
        assert res["updated"] == 1
        assert res["inserted"] == 0
        
        # Verify UPDATE was called with ID 103 instead of INSERT
        mock_conn.execute.assert_called_once()
        exec_args = mock_conn.execute.call_args[0]
        assert "UPDATE contacts" in exec_args[0]
        assert exec_args[6] == 103  # existing['id']


def test_admin_sync_members_endpoint():
    # Login admin
    login_res = client.post(
        "/admin/login",
        json={"username": settings.admin_user, "password": settings.admin_password},
    )
    token = login_res.json()["data"]["token"]
    headers = {"Authorization": f"Bearer {token}"}

    with patch("app.services.notion_sync.sync_notion_members_to_contacts", new=AsyncMock(return_value={"success": True, "inserted": 1, "updated": 2, "skipped": 0})):
        res = client.post("/admin/sync-members", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["data"]["success"] is True
        assert data["data"]["inserted"] == 1
        assert data["data"]["updated"] == 2
