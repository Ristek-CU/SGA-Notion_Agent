"""Telegram platform: sender + webhook router.

Reuses process_incoming_message() dari app/webhook/handler.py sehingga
pipeline AI/guard/session identik dengan WhatsApp.
"""
import asyncio
import html as _html
import re as _re

import httpx
from typing import Dict, Any
from fastapi import APIRouter, Request
from app.services.platform_config import get_platform_token

router = APIRouter()

TELEGRAM_API = "https://api.telegram.org"


async def tg_call(token: str, method: str, payload: Dict[str, Any] | None = None) -> dict:
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(f"{TELEGRAM_API}/bot{token}/{method}", json=payload or {})
        data = resp.json()
        if not data.get("ok"):
            raise RuntimeError(data.get("description", f"Telegram API error {resp.status_code}"))
        return data.get("result", {})


_MD_BOLD = _re.compile(r"\*([^*\n]+)\*")


def _wa_md_to_tg_html(text: str) -> str:
    """Balasan bot ditulis dgn markdown gaya WA (*bold*, _italic_, ~strike~, `mono`).
    Konversi ke HTML parse_mode Telegram secara aman."""
    out = _html.escape(text, quote=False)
    # Multiline / Single-line code block: ```code``` -> <pre>code</pre>
    out = _re.sub(r"```(?:\w+)?\n?(.*?)```", r"<pre>\1</pre>", out, flags=_re.DOTALL)
    # Bold: *text* -> <b>text</b>
    out = _re.sub(r"\*([^*\n]+)\*", r"<b>\1</b>", out)
    # Italic: _text_ -> <i>text</i>
    out = _re.sub(r"_([^_\n]+)_", r"<i>\1</i>", out)
    # Strikethrough: ~text~ -> <s>text</s>
    out = _re.sub(r"~([^~\n]+)~", r"<s>\1</s>", out)
    # Inline code: `text` -> <code>text</code>
    out = _re.sub(r"`([^`\n]+)`", r"<code>\1</code>", out)
    return out


async def send_telegram_message(chat_id: Any, text: str) -> dict:
    token = await get_platform_token("telegram")
    if not token:
        raise RuntimeError("Telegram platform disabled or bot_token not configured")
    
    html_text = _wa_md_to_tg_html(text)
    try:
        return await tg_call(token, "sendMessage",
                             {"chat_id": chat_id, "text": html_text,
                              "parse_mode": "HTML",
                              "link_preview_options": {"is_disabled": True}})
    except Exception as e:
        # Fallback 1: Coba MarkdownV2 / plain jika parse HTML gagal
        try:
            return await tg_call(token, "sendMessage",
                                 {"chat_id": chat_id, "text": text,
                                  "link_preview_options": {"is_disabled": True}})
        except Exception:
            return await tg_call(token, "sendMessage", {"chat_id": chat_id, "text": text})


async def send_typing(chat_id: Any):
    """Kirim action 'typing' sekali (berlaku ~5 detik)."""
    try:
        token = await get_platform_token("telegram")
        if token:
            await tg_call(token, "sendChatAction", {"chat_id": chat_id, "action": "typing"})
    except Exception:
        pass


async def _typing_loop(chat_id: Any, stop: asyncio.Event):
    """Kirim ulang 'typing' tiap 4 detik sampai balasan siap."""
    while not stop.is_set():
        await send_typing(chat_id)
        try:
            await asyncio.wait_for(stop.wait(), timeout=4.0)
        except asyncio.TimeoutError:
            pass


@router.post("/webhook/telegram/{token}")
async def telegram_webhook(token: str, request: Request):
    expected = await get_platform_token("telegram")
    # Secret-path validation: no-op kalau token beda / config belum ada.
    if not expected or token != expected:
        return {"status": "ignored"}
    update: Dict[str, Any] = await request.json()
    msg = update.get("message") or {}
    text = (msg.get("text") or "").strip()
    chat = msg.get("chat") or {}
    frm = msg.get("from") or {}
    if not text:
        return {"status": "ignored"}

    norm = {
        "key": {
            "id": str(msg.get("message_id")),
            "fromMe": bool(frm.get("is_bot")),
            "remoteJid": str(chat.get("id", "")),
            "participant": str(frm.get("id", "")),
        },
        "message": {"conversation": text},
        "pushName": frm.get("first_name") or frm.get("username"),
    }
    tg_username = frm.get("username")
    from app.services.queue import queue_manager
    queue_manager.start()
    sender_name = frm.get("first_name") or tg_username or str(chat.get("id"))
    await queue_manager.enqueue_chat(
        handler=lambda: _process_and_reply(norm, str(chat.get("id")), tg_username=tg_username),
        sender=sender_name,
        platform="Telegram",
        preview=text,
    )
    return {"status": "processing"}


async def _process_and_reply(norm: dict, chat_id: str, tg_username: str | None = None):
    """Jalankan pipeline WaHa lalu balas via Telegram sendMessage.

    reply_override mengarahkan semua balasan non-group ke Telegram tanpa
    monkeypatch global (aman terhadap pesan concurrent).
    Selama memproses, tampilkan indikator 'typing...' di profil bot.
    """
    from app.webhook.handler import process_incoming_message

    stop = asyncio.Event()
    typing_task = asyncio.create_task(_typing_loop(chat_id, stop))
    sent: list = []

    async def tg_send(remote_jid, text, **kw):
        sent.append(text)

    try:
        await process_incoming_message(norm, reply_override=tg_send, telegram_username=tg_username)
    finally:
        stop.set()
        typing_task.cancel()

    for text in sent:
        await send_telegram_message(chat_id, text)
