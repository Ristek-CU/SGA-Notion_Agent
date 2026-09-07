import pytest
from unittest.mock import patch, AsyncMock
from app.ai.commands import parse_command, handle_command


def test_parse_command():
    cmd, args = parse_command("help")
    assert cmd == "help"

    cmd, args = parse_command("buat tiket Fix bug login")
    assert cmd == "create_ticket"
    assert args["title"] == "Fix bug login"

    cmd, args = parse_command("detail tiket TK-12345")
    assert cmd == "ticket_detail"
    assert args["ticket_id"] == "TK-12345"

    cmd, args = parse_command("update tiket Development for the Ai Roro model ke Done")
    assert cmd == "update_status"
    assert args["ticket_id"] == "Development for the Ai Roro model"
    assert args["status"] == "Done"

    cmd, args = parse_command("Testing roro onprogress, lagi saya test")
    assert cmd == "update_status"
    assert args["ticket_id"] == "Testing roro"
    assert args["status"] == "In progress"

    cmd, args = parse_command("ubah prioritas testing itu menjadi high, karena penting bangett nih supaya harus cepat selesai")
    assert cmd == "update_priority"
    assert args["ticket_id"] == "testing itu"
    assert args["priority"] == "high"

    cmd, args = parse_command("ganti priority TK-12345 ke Low")
    assert cmd == "update_priority"
    assert args["ticket_id"] == "TK-12345"
    assert args["priority"] == "Low"


@pytest.mark.asyncio
async def test_handle_command():
    res = await handle_command("help", {}, {"nickname": "Tester"})
    assert "Perintah Notion Agent SGA" in res

    mock_ticket = {
        "id": "page_roro_1",
        "properties": {
            "Name": {"title": [{"plain_text": "Development for the Ai Roro model"}]},
            "Status": {"status": {"name": "In Progress"}},
            "ID": {"rich_text": [{"plain_text": "TK-101"}]},
        },
    }

    with patch("app.notion.ticket_service.query_tickets_direct", new=AsyncMock(return_value=[mock_ticket])), \
         patch("app.notion.ticket_service.update_ticket_direct", new=AsyncMock()) as mock_update:

        res = await handle_command("update_status", {"ticket_id": "Development for the Ai Roro model", "status": "Done"}, {"nickname": "Tester"})
        assert "✅" in res
        assert "Done" in res
        mock_update.assert_called_once()

    with patch("app.notion.ticket_service.query_tickets_direct", new=AsyncMock(return_value=[mock_ticket])), \
         patch("app.notion.ticket_service.update_ticket_priority", new=AsyncMock()) as mock_update_prio:

        res = await handle_command("update_priority", {"ticket_id": "Development for the Ai Roro model", "priority": "high"}, {"nickname": "Tester"})
        assert "✅" in res
        assert "High" in res
        mock_update_prio.assert_called_once_with("page_roro_1", "High")


@pytest.mark.asyncio
async def test_smart_message_update_priority():
    from app.ai.intent import handle_smart_message

    mock_ticket = {
        "id": "page_roro_1",
        "properties": {
            "Name": {"title": [{"plain_text": "testing itu"}]},
            "Priority Level": {"select": {"name": "Medium"}},
            "Status": {"status": {"name": "In progress"}},
        },
    }

    ai_extraction = '{"action":"update_priority","title":"testing itu","new_priority":"high"}'

    with patch("app.ai.intent.create_message", new=AsyncMock(return_value=ai_extraction)), \
         patch("app.notion.ticket_service.query_tickets_direct", new=AsyncMock(return_value=[mock_ticket])), \
         patch("app.notion.ticket_service.update_ticket_priority", new=AsyncMock()) as mock_update_prio:

        res = await handle_smart_message(
            "ubah prioritas testing itu menjadi high, karena penting bangett nih supaya harus cepat selesai",
            {"name": "Salman", "phone": "628123456789"}
        )
        assert "✅" in res
        assert "High" in res
        mock_update_prio.assert_called_once_with("page_roro_1", "High")

