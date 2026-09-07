import pytest
from unittest.mock import AsyncMock, patch
from app.ai.intent import _gather_task_context, get_user_member_ids
from app.ai.commands import handle_command
from app.services.identity import resolve_identity_async, resolve_identity


@pytest.mark.asyncio
async def test_identity_resolution_dynamic_wa_and_telegram():
    # 1. WhatsApp resolution by Phone
    id_salman_wa = await resolve_identity_async("6285175019086")
    assert id_salman_wa["is_known"] is True
    assert id_salman_wa["nickname"] == "Salman"
    assert id_salman_wa["phone"] == "6285175019086"

    id_yasin_wa = await resolve_identity_async("628888902026")
    assert id_yasin_wa["is_known"] is True
    assert id_yasin_wa["nickname"] == "Yaa"

    # 2. Telegram resolution by username
    id_salman_tg = await resolve_identity_async("unknown_sender", telegram_username="msalman")
    assert id_salman_tg["is_known"] is True
    assert id_salman_tg["nickname"] == "Salman"
    assert id_salman_tg["phone"] == "6285175019086"

    # 3. Telegram resolution by telegram_chat_id
    mock_contacts = [
        {
            "name": "Yaa Siin",
            "nickname": "Yaa",
            "phone": "628888902026",
            "telegram": "yaasiin",
            "telegram_chat_id": "987654321",
            "division": "Research and Technology",
            "role": "Head",
            "aliases": ["yaa", "yasin"]
        }
    ]
    with patch("app.services.contacts._load_contacts_from_file", return_value=mock_contacts), \
         patch("app.services.database.get_db_pool", new=AsyncMock(return_value=None)):
        id_yasin_tg = await resolve_identity_async("unknown_tg", telegram_chat_id="987654321")
        assert id_yasin_tg["is_known"] is True
        assert id_yasin_tg["nickname"] == "Yaa"


@pytest.mark.asyncio
async def test_dynamic_task_filtering_salman_vs_yasin():
    """Verify that Salman only sees Salman's tasks, and Yasin only sees Yasin's tasks."""
    mock_members = [
        {
            "id": "mem_page_salman",
            "properties": {
                "Member Name": {"title": [{"plain_text": "Muhammad Salman Firdaus"}]},
                "WhatsApp": {"rich_text": [{"plain_text": "6285175019086"}]},
            },
        },
        {
            "id": "mem_page_yasin",
            "properties": {
                "Member Name": {"title": [{"plain_text": "Yaa Siin"}]},
                "WhatsApp": {"rich_text": [{"plain_text": "628888902026"}]},
            },
        },
    ]

    mock_tickets = [
        {
            "id": "ticket_salman_1",
            "properties": {
                "Name": {"title": [{"plain_text": "Fix Bug Authentication"}]},
                "Status": {"status": {"name": "In progress"}},
                "Priority Level": {"select": {"name": "High"}},
                "PIC": {"relation": [{"id": "mem_page_salman"}]},
                "ID": {"rich_text": [{"plain_text": "TK-001"}]},
            },
        },
        {
            "id": "ticket_yasin_1",
            "properties": {
                "Name": {"title": [{"plain_text": "Review Research Roadmap"}]},
                "Status": {"status": {"name": "Not started"}},
                "Priority Level": {"select": {"name": "Medium"}},
                "PIC": {"relation": [{"id": "mem_page_yasin"}]},
                "ID": {"rich_text": [{"plain_text": "TK-002"}]},
            },
        },
    ]

    with patch("app.notion.ticket_service.query_tickets_direct", new=AsyncMock(return_value=mock_tickets)), \
         patch("app.notion.org_service.list_members", new=AsyncMock(return_value=mock_members)):

        # Salman asks for context / tasks
        salman_sender = {"name": "Muhammad Salman Firdaus", "nickname": "Salman", "phone": "6285175019086"}
        salman_ctx = await _gather_task_context(salman_sender)
        assert "Fix Bug Authentication" in salman_ctx
        assert "Review Research Roadmap" not in salman_ctx

        # Salman calls 'my_tickets' command
        salman_cmd = await handle_command("my_tickets", {}, salman_sender)
        assert "Fix Bug Authentication" in salman_cmd
        assert "Review Research Roadmap" not in salman_cmd

        # Yasin asks for context / tasks
        yasin_sender = {"name": "Yaa Siin", "nickname": "Yaa", "phone": "628888902026"}
        yasin_ctx = await _gather_task_context(yasin_sender)
        assert "Review Research Roadmap" in yasin_ctx
        assert "Fix Bug Authentication" not in yasin_ctx

        # Yasin calls 'my_tickets' command
        yasin_cmd = await handle_command("my_tickets", {}, yasin_sender)
        assert "Review Research Roadmap" in yasin_cmd
        assert "Fix Bug Authentication" not in yasin_cmd
