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
from app.services.formatter import format_for_telegram

router = APIRouter()

TELEGRAM_API = "https://api.telegram.org"


async def tg_call(token: str, method: str, payload: Dict[str, Any] | None = None) -> dict:
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(f"{TELEGRAM_API}/bot{token}/{method}", json=payload or {})
        data = resp.json()
        if not data.get("ok"):
            raise RuntimeError(data.get("description", f"Telegram API error {resp.status_code}"))
        return data.get("result", {})


def _wa_md_to_tg_html(text: str) -> str:
    """Balasan bot ditulis dgn markdown gaya WA / standar (*bold*, _italic_, ~strike~, `mono`, [link](url)).
    Konversi ke HTML parse_mode Telegram secara aman."""
    return format_for_telegram(text)


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


async def send_telegram_document(
    chat_id: Any,
    document_url: str,
    caption: str | None = None,
    filename: str | None = None,
) -> dict:
    """Kirim dokumen / file via Telegram sendDocument.
    Mendukung URL publik atau download/stream ke Telegram.
    """
    token = await get_platform_token("telegram")
    if not token:
        raise RuntimeError("Telegram platform disabled or bot_token not configured")

    caption_html = _wa_md_to_tg_html(caption) if caption else ""

    # Coba kirim via URL langsung terlebih dahulu
    payload = {
        "chat_id": chat_id,
        "document": document_url,
    }
    if caption_html:
        payload["caption"] = caption_html
        payload["parse_mode"] = "HTML"

    try:
        return await tg_call(token, "sendDocument", payload)
    except Exception as e:
        # Jika gagal kirim via URL langsung (misal Telegram bot server tidak bisa fetch URL atau parse error),
        # download file secara streaming/buffer dan upload multipart ke Telegram API
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                file_resp = await client.get(document_url)
                file_resp.raise_for_status()
                file_bytes = file_resp.content

            upload_filename = filename or document_url.split("/")[-1] or "document"
            data = {"chat_id": str(chat_id)}
            if caption:
                data["caption"] = caption_html or caption
                if caption_html:
                    data["parse_mode"] = "HTML"

            files = {"document": (upload_filename, file_bytes)}
            async with httpx.AsyncClient(timeout=60.0) as client:
                res = await client.post(
                    f"{TELEGRAM_API}/bot{token}/sendDocument",
                    data=data,
                    files=files,
                )
                res_data = res.json()
                if not res_data.get("ok"):
                    # Fallback plain caption tanpa HTML parse_mode
                    if "parse" in res_data.get("description", "").lower() and caption:
                        data.pop("parse_mode", None)
                        data["caption"] = caption
                        res2 = await client.post(
                            f"{TELEGRAM_API}/bot{token}/sendDocument",
                            data=data,
                            files={"document": (upload_filename, file_bytes)},
                        )
                        res2_data = res2.json()
                        if res2_data.get("ok"):
                            return res2_data.get("result", {})
                    raise RuntimeError(res_data.get("description", f"Telegram API error {res.status_code}"))
                return res_data.get("result", {})
        except Exception as upload_err:
            raise RuntimeError(f"Gagal kirim dokumen Telegram: {upload_err}")


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
    chat_id_str = str(chat.get("id", ""))

    # Auto-save telegram_chat_id permanen di DB & Redis cache
    if tg_username and chat_id_str:
        from app.services.contacts import update_contact_telegram_chat_id
        asyncio.create_task(update_contact_telegram_chat_id(tg_username, chat_id_str))

    from app.services.queue import queue_manager
    queue_manager.start()
    sender_name = frm.get("first_name") or tg_username or chat_id_str
    await queue_manager.enqueue_chat(
        handler=lambda: _process_and_reply(norm, chat_id_str, tg_username=tg_username, tg_chat_id=chat_id_str),
        sender=sender_name,
        platform="Telegram",
        preview=text,
    )
    return {"status": "processing"}


async def _process_and_reply(norm: dict, chat_id: str, tg_username: str | None = None, tg_chat_id: str | None = None):
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
        await process_incoming_message(
            norm,
            reply_override=tg_send,
            telegram_username=tg_username,
            telegram_chat_id=tg_chat_id or chat_id,
        )
    finally:
        stop.set()
        typing_task.cancel()

    for text in sent:
        await send_telegram_message(chat_id, text)
