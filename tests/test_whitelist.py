import pytest
from unittest.mock import AsyncMock, patch
from app.webhook.handler import process_incoming_message
from app.services.contacts import add_or_update_contact, delete_contact, load_contacts


@pytest.mark.asyncio
async def test_whitelist_unregistered_user_ignored():
    """Pesan dari user yang tidak dikenal/belum di-whitelist harus diabaikan (tidak dibalas)."""
    with patch("app.webhook.handler.is_duplicate_msg", new=AsyncMock(return_value=False)), \
         patch("app.webhook.handler._send", new=AsyncMock()) as mock_send, \
         patch("app.webhook.handler.session_manager.save_user_message", new=AsyncMock()) as mock_save_user:

        # Kirim dari user tidak dikenal
        payload = {
            "key": {"id": "msg_unknown_1", "fromMe": False, "remoteJid": "6289999999999@s.whatsapp.net"},
            "message": {"conversation": "Halo notion agent"},
            "pushName": "Stranger",
        }

        await process_incoming_message(payload)

        # Harusnya tidak simpan session dan tidak kirim pesan
        mock_save_user.assert_not_called()
        mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_whitelist_registered_telegram_and_wa():
    """User yang terdaftar di contacts (via phone atau telegram) harus diproses."""
    # Pastikan contact ditambahkan
    await add_or_update_contact(
        name="Test User",
        phone="628111222333",
        role="Staff",
        division="Tech",
        telegram="test_tg_user"
    )

    with patch("app.webhook.handler.is_duplicate_msg", new=AsyncMock(return_value=False)), \
         patch("app.webhook.handler.get_guard_state", new=AsyncMock(return_value={"enabled": False})), \
         patch("app.webhook.handler._send", new=AsyncMock()) as mock_send, \
         patch("app.webhook.handler.session_manager.save_user_message", new=AsyncMock()) as mock_save_user, \
         patch("app.webhook.handler.session_manager.save_assistant_response", new=AsyncMock()), \
         patch("app.webhook.handler.handle_smart_message", new=AsyncMock(return_value="AI output")), \
         patch("app.webhook.handler.handle_command", new=AsyncMock(return_value="Help output")):

        # 1. Test via Telegram username
        tg_payload = {
            "key": {"id": "msg_tg_1", "fromMe": False, "remoteJid": "123456789"},
            "message": {"conversation": "/help"},
            "pushName": "Random TG Name",
        }
        await process_incoming_message(tg_payload, telegram_username="test_tg_user")
        mock_save_user.assert_called()
        mock_send.assert_called()

        mock_save_user.reset_mock()
        mock_send.reset_mock()

        # 2. Test via WA Phone
        wa_payload = {
            "key": {"id": "msg_wa_1", "fromMe": False, "remoteJid": "628111222333@s.whatsapp.net"},
            "message": {"conversation": "/help"},
            "pushName": "Test User",
        }
        await process_incoming_message(wa_payload)
        mock_save_user.assert_called()
        mock_send.assert_called()

    # Cleanup
    await delete_contact("628111222333")
