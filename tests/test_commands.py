import pytest
from app.ai.commands import parse_command, handle_command


def test_parse_command():
    cmd, args = parse_command("help")
    assert cmd == "help"

    cmd, args = parse_command("buat tiket Fix database migration")
    assert cmd == "create_ticket"
    assert args["title"] == "Fix database migration"

    cmd, args = parse_command("detail tiket TK-12345")
    assert cmd == "ticket_detail"
    assert args["ticket_id"] == "TK-12345"


@pytest.mark.asyncio
async def test_handle_command():
    res = await handle_command("help", {}, {"nickname": "Tester"})
    assert "Perintah Notion Agent SGA" in res

    res = await handle_command("create_ticket", {"title": "Test Ticket"}, {"nickname": "Tester"})
    assert "Tiket berhasil dibuat" in res
    assert "Test Ticket" in res
