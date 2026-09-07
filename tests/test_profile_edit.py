import pytest
from unittest.mock import AsyncMock, patch
from app.ai.commands import parse_command, handle_command
from app.services.contacts import (
    add_or_update_contact,
    find_contact_by_phone,
    update_contact_profile,
    load_contacts,
)
from app.webhook.handler import process_incoming_message
from app.services.session import session_manager


@pytest.fixture(autouse=True)
def preserve_contacts_cache():
    import app.services.contacts as c_mod
    original_cache = c_mod._contacts_cache
    original_mtime = c_mod._last_mtime
    yield
    c_mod._contacts_cache = None
    c_mod._last_mtime = 0.0
    from app.services.identity import clear_identity_cache
    clear_identity_cache()


def test_parse_profile_commands():
    # 1. Profile check
    assert parse_command("profil")[0] == "my_profile"
    assert parse_command("profil saya")[0] == "my_profile"
    assert parse_command("cek profil")[0] == "my_profile"
    assert parse_command("data diri")[0] == "my_profile"

    # 2. Edit name
    cmd, args = parse_command("ganti nama Muhammad Salman Firdaus")
    assert cmd == "edit_profile_name"
    assert args["name"] == "Muhammad Salman Firdaus"

    cmd, args = parse_command("ubah nama lengkap saya jadi Salman Firdaus")
    assert cmd == "edit_profile_name"
    assert args["name"] == "Salman Firdaus"

    # 3. Edit nickname
    cmd, args = parse_command("ganti nickname Maman")
    assert cmd == "edit_profile_nickname"
    assert args["nickname"] == "Maman"

    cmd, args = parse_command("panggil aku Salman")
    assert cmd == "edit_profile_nickname"
    assert args["nickname"] == "Salman"

    # 4. Edit phone
    cmd, args = parse_command("ganti nomor wa jadi 081234567890")
    assert cmd == "edit_profile_phone"
    assert args["phone"] == "081234567890"

    cmd, args = parse_command("ubah no hp ke 085175019086")
    assert cmd == "edit_profile_phone"
    assert args["phone"] == "085175019086"

    # 5. Edit telegram
    cmd, args = parse_command("ganti telegram jadi @salman_f")
    assert cmd == "edit_profile_telegram"
    assert args["telegram"] == "@salman_f"

    cmd, args = parse_command("ubah username telegram ke msalman")
    assert cmd == "edit_profile_telegram"
    assert args["telegram"] == "msalman"


@pytest.mark.asyncio
async def test_immediate_profile_edit_name_and_nickname(tmp_path, monkeypatch):
    import json
    fake_contacts_file = tmp_path / "contacts.json"
    fake_contacts_file.write_text("[]", encoding="utf-8")
    monkeypatch.setattr("app.services.contacts.get_contacts_file_path", lambda: str(fake_contacts_file))
    import app.services.contacts as c_mod
    c_mod._contacts_cache = None
    c_mod._last_mtime = 0.0
    c_mod._last_file_path = None

    phone = "628999111222"
    await add_or_update_contact(
        name="Nama Awal",
        phone=phone,
        nickname="Awal",
        division="Research and Technology",
        role="Staff",
        telegram="awal_tg"
    )

    sender_info = {
        "name": "Nama Awal",
        "nickname": "Awal",
        "phone": phone,
        "division": "Research and Technology",
        "role": "Staff",
        "is_known": True,
    }

    # Test update nama lengkap
    res_name = await handle_command("edit_profile_name", {"name": "Nama Baru Lengkap"}, sender_info)
    assert "✅ Berhasil!" in res_name
    assert "Nama Baru Lengkap" in res_name

    c = await find_contact_by_phone(phone)
    assert c is not None
    assert c["name"] == "Nama Baru Lengkap"

    # Test update nickname
    res_nick = await handle_command("edit_profile_nickname", {"nickname": "KawanBaru"}, sender_info)
    assert "✅ Siap!" in res_nick
    assert "KawanBaru" in res_nick

    c = await find_contact_by_phone(phone)
    assert c is not None
    assert c["nickname"] == "KawanBaru"


@pytest.mark.asyncio
async def test_security_confirmation_flow_phone(tmp_path, monkeypatch):
    fake_contacts_file = tmp_path / "contacts.json"
    fake_contacts_file.write_text("[]", encoding="utf-8")
    monkeypatch.setattr("app.services.contacts.get_contacts_file_path", lambda: str(fake_contacts_file))
    import app.services.contacts as c_mod
    c_mod._contacts_cache = None
    c_mod._last_mtime = 0.0
    c_mod._last_file_path = None

    class InMemoryRedis:
        def __init__(self):
            self.store = {}
        async def get(self, k):
            return self.store.get(k)
        async def set(self, k, v, ex=None, nx=False):
            if nx and k in self.store:
                return False
            self.store[k] = v
            return True
        async def delete(self, k):
            self.store.pop(k, None)

    fake_redis = InMemoryRedis()
    monkeypatch.setattr(session_manager, "get_redis", AsyncMock(return_value=fake_redis))

    curr_phone = "628999333444"
    await add_or_update_contact(
        name="User Phone Test",
        phone=curr_phone,
        nickname="PhoneTest",
        telegram="phone_tg"
    )

    sender_info = {
        "name": "User Phone Test",
        "nickname": "PhoneTest",
        "phone": curr_phone,
        "is_known": True,
    }

    # 1. Trigger ganti nomor WA -> harus minta konfirmasi dan belum update DB
    reply = await handle_command("edit_profile_phone", {"phone": "081299887766"}, sender_info)
    assert "⚠️ *Konfirmasi Perubahan Nomor WhatsApp*" in reply
    assert "Ketik *YA* atau *KONFIRMASI*" in reply

    # Contact phone masih yang lama
    c_old = await find_contact_by_phone(curr_phone)
    assert c_old is not None
    assert c_old["phone"] == curr_phone

    # 2. Balas YA -> Terupdate
    sent_msgs = []
    async def mock_send(reply_override, target_jid, text, instance_name=None):
        sent_msgs.append(text)

    wa_msg = {
        "key": {"id": "msg_conf_1", "fromMe": False, "remoteJid": f"{curr_phone}@s.whatsapp.net"},
        "message": {"conversation": "YA"},
        "pushName": "User Phone Test",
    }
    with patch("app.webhook.handler.is_duplicate_msg", new=AsyncMock(return_value=False)), \
         patch("app.webhook.handler._send", new=AsyncMock(side_effect=mock_send)):
        await process_incoming_message(wa_msg)

    assert any("Nomor WhatsApp Berhasil Diubah" in m for m in sent_msgs)
    
    # DB Contact harusnya sudah berubah ke nomor baru
    c_new = await find_contact_by_phone("6281299887766")
    assert c_new is not None
    assert c_new["name"] == "User Phone Test"

    # Pending state di Redis harus bersih
    pending = await session_manager.get_pending_profile_update(curr_phone)
    assert pending is None


@pytest.mark.asyncio
async def test_security_confirmation_flow_telegram_and_cancel(tmp_path, monkeypatch):
    fake_contacts_file = tmp_path / "contacts.json"
    fake_contacts_file.write_text("[]", encoding="utf-8")
    monkeypatch.setattr("app.services.contacts.get_contacts_file_path", lambda: str(fake_contacts_file))
    import app.services.contacts as c_mod
    c_mod._contacts_cache = None
    c_mod._last_mtime = 0.0
    c_mod._last_file_path = None

    class InMemoryRedis:
        def __init__(self):
            self.store = {}
        async def get(self, k):
            return self.store.get(k)
        async def set(self, k, v, ex=None, nx=False):
            if nx and k in self.store:
                return False
            self.store[k] = v
            return True
        async def delete(self, k):
            self.store.pop(k, None)

    fake_redis = InMemoryRedis()
    monkeypatch.setattr(session_manager, "get_redis", AsyncMock(return_value=fake_redis))

    curr_phone = "628999555666"
    await add_or_update_contact(
        name="User TG Test",
        phone=curr_phone,
        nickname="TGTest",
        telegram="old_tg_handle"
    )

    sender_info = {
        "name": "User TG Test",
        "nickname": "TGTest",
        "phone": curr_phone,
        "is_known": True,
    }

    # 1. Trigger ganti telegram
    reply = await handle_command("edit_profile_telegram", {"telegram": "new_tg_handle"}, sender_info)
    assert "⚠️ *Konfirmasi Perubahan Akun Telegram*" in reply

    # 2. User balas BATAL
    sent_msgs = []
    async def mock_send(reply_override, target_jid, text, instance_name=None):
        sent_msgs.append(text)

    wa_msg = {
        "key": {"id": "msg_cancel_1", "fromMe": False, "remoteJid": f"{curr_phone}@s.whatsapp.net"},
        "message": {"conversation": "batal"},
        "pushName": "User TG Test",
    }
    with patch("app.webhook.handler.is_duplicate_msg", new=AsyncMock(return_value=False)), \
         patch("app.webhook.handler._send", new=AsyncMock(side_effect=mock_send)):
        await process_incoming_message(wa_msg)

    assert any("dibatalkan" in m for m in sent_msgs)

    # Telegram handle tidak berubah
    c = await find_contact_by_phone(curr_phone)
    assert c is not None
    assert c["telegram"] == "old_tg_handle"

    # Pending state di Redis harus bersih
    pending = await session_manager.get_pending_profile_update(curr_phone)
    assert pending is None
