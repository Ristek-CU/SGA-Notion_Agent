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

    cmd, args = parse_command("Development for the Ai Roro model dah selesai")
    assert cmd == "update_status"
    assert args["ticket_id"] == "Development for the Ai Roro model"
    assert args["status"] == "Done"


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
        assert "✅ Status" in res
        assert "Done" in res
        mock_update.assert_called_once()
