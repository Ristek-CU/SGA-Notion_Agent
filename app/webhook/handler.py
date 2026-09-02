import asyncio
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Request
from app.webhook.guard import check_out_of_scope
from app.services.identity import resolve_identity
from app.services.session import session_manager
from app.services.store import get_guard_state
from app.ai.commands import parse_command, handle_command
from app.ai.intent import handle_smart_message
from app.wa.sender import send_whatsapp_message, reply_to_group, lookup_lid_cache, set_lid_cache

router = APIRouter()


async def is_duplicate_msg(msg_id: str) -> bool:
    """Dedup persisten: SET NX EX 60 — aman lintas restart & worker."""
    r = await session_manager.get_redis()
    key = f"dedup:{msg_id}"
    return not await r.set(key, 1, ex=60, nx=True)


class WebhookPayload(BaseModel):
    event: Optional[str] = None
    instance: Optional[str] = None
    session: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)
    data: Dict[str, Any] = Field(default_factory=dict)


def normalize_waha_message(msg: Dict[str, Any]) -> Dict[str, Any]:
    """Map payload pesan WaHa (flatten) ke bentuk yang dimengerti process_incoming_message."""
    from_me = bool(msg.get("fromMe") or msg.get("isFromMe"))
    chat_id = msg.get("chatId") or msg.get("from") or ""
    sender = msg.get("sender") or {}
    is_group = chat_id.endswith("@g.us")
    participant = sender.get("id") or msg.get("from") or chat_id
    text = (
        msg.get("body")
        or msg.get("text")
        or (msg.get("message") or {}).get("text")
        or (msg.get("message") or {}).get("conversation")
        or ""
    )
    return {
        "key": {
            "id": msg.get("id"),
            "fromMe": from_me,
            "remoteJid": chat_id,
            "participant": participant if is_group else chat_id,
        },
        "message": {"conversation": text},
        "pushName": msg.get("fromName") or sender.get("name"),
    }


async def _send(reply_override, remote_jid: str, text: str, instance_name: Optional[str]):
    """Kirim balasan via override (mis. Telegram) jika ada, selain itu via WhatsApp."""
    if reply_override is not None:
        await reply_override(remote_jid, text)
    else:
        await send_whatsapp_message(remote_jid, text, instance=instance_name)


async def process_incoming_message(data: Dict[str, Any], instance_name: Optional[str] = None, reply_override=None, telegram_username: Optional[str] = None):
    key = data.get("key", {})
    msg_id = key.get("id")
    if not msg_id or await is_duplicate_msg(msg_id):
        return

    from_me = key.get("fromMe", False)
    if from_me:
        return

    remote_jid = key.get("remoteJid", "")
    is_group = remote_jid.endswith("@g.us")
    participant = key.get("participant") or remote_jid

    # Extract text from message body
    message_obj = data.get("message", {})
    text = (
        message_obj.get("conversation")
        or message_obj.get("extendedTextMessage", {}).get("text")
        or ""
    ).strip()

    if not text:
        return

    push_name = data.get("pushName")

    # Handle @lid mapping if applicable
    raw_sender = participant.split("@")[0]
    if "@lid" in participant:
        cached_phone = lookup_lid_cache(participant)
        if cached_phone:
            raw_sender = cached_phone

    # Resolve sender identity (Telegram username dipakai utk cocokkan kontak)
    from app.services.identity import resolve_identity_async
    sender_info = await resolve_identity_async(raw_sender, push_name=push_name, telegram_username=telegram_username)

    # Whitelist check: Abaikan pesan jika user tidak dikenal (tidak ada di daftar kontak/whitelist)
    if not sender_info.get("is_known"):
        return

    # Save user message to session
    await session_manager.save_user_message(sender_info["phone"], text)

    # Guard check out-of-scope (hormati toggle persisten di Redis)
    guard_cfg = await get_guard_state()
    guard_res = check_out_of_scope(text)
    if guard_cfg.get("enabled") and guard_res["is_out_of_scope"]:
        reply_text = guard_res["reason"]
        await session_manager.save_assistant_response(sender_info["phone"], reply_text)
        if is_group:
            await reply_to_group(remote_jid, reply_text, quoted_msg_id=msg_id)
        else:
            await _send(reply_override, remote_jid, reply_text, instance_name)
        return

    # Check for commands
    parsed = parse_command(text)
    if parsed:
        cmd_type, args = parsed
        reply_text = await handle_command(cmd_type, args, sender_info)
    else:
        # Fallback to AI intent / ticket / chat
        reply_text = await handle_smart_message(text, sender_info)

    # Save assistant reply to session
    await session_manager.save_assistant_response(sender_info["phone"], reply_text)

    # Send response back to WA (Gunakan sender_info["phone"] jika remote_jid berupa @lid)
    target_jid = sender_info["phone"] if "@lid" in remote_jid else remote_jid
    if is_group:
        await reply_to_group(remote_jid, reply_text, quoted_msg_id=msg_id)
    else:
        await _send(reply_override, target_jid, reply_text, instance_name)


@router.post("/webhook/{instance}")
async def handle_webhook(instance: str, payload: WebhookPayload, request: Request):
    raw_body = {}
    try:
        raw_body = await request.json()
        print(f"[WAHA WEBHOOK RECEIVE] instance={instance} event={payload.event} body={str(raw_body)[:300]}")
    except Exception:
        pass

    # Direct WAHA JSON structure (event: "message" / "message.any", payload: message_obj, atau raw_body)
    msg_data = payload.payload or payload.data or raw_body.get("payload") or raw_body.get("data") or raw_body
    if msg_data and isinstance(msg_data, dict):
        msg = normalize_waha_message(msg_data)
        if msg["key"].get("id"):
            await process_incoming_message(msg, instance_name=instance)
        return {"status": "processing"}

    return {"status": "processing"}
