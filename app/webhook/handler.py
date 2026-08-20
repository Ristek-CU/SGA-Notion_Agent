import asyncio
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Request
from app.webhook.guard import check_out_of_scope
from app.services.identity import resolve_identity
from app.services.session import session_manager
from app.ai.commands import parse_command, handle_command
from app.ai.intent import handle_smart_message
from app.wa.sender import send_whatsapp_message, reply_to_group, lookup_lid_cache, set_lid_cache

router = APIRouter()

_processed_msg_ids: Dict[str, float] = {}


class WebhookPayload(BaseModel):
    event: Optional[str] = None
    instance: Optional[str] = None
    data: Dict[str, Any] = Field(default_factory=dict)


def is_duplicate_msg(msg_id: str) -> bool:
    import time
    now = time.monotonic()
    # Clean up old ids > 60s
    to_del = [k for k, v in _processed_msg_ids.items() if now - v > 60.0]
    for k in to_del:
        del _processed_msg_ids[k]

    if msg_id in _processed_msg_ids:
        return True
    _processed_msg_ids[msg_id] = now
    return False


async def process_incoming_message(data: Dict[str, Any], instance_name: Optional[str] = None):
    key = data.get("key", {})
    msg_id = key.get("id")
    if not msg_id or is_duplicate_msg(msg_id):
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

    # Resolve sender identity
    sender_info = resolve_identity(raw_sender, push_name=push_name)

    # Save user message to session
    await session_manager.save_user_message(sender_info["phone"], text)

    # Guard check out of scope
    guard_res = check_out_of_scope(text)
    if guard_res["is_out_of_scope"]:
        reply_text = guard_res["reason"]
        await session_manager.save_assistant_response(sender_info["phone"], reply_text)
        if is_group:
            await reply_to_group(remote_jid, reply_text, quoted_msg_id=msg_id)
        else:
            await send_whatsapp_message(remote_jid, reply_text, instance=instance_name)
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

    # Send response back to WA
    if is_group:
        await reply_to_group(remote_jid, reply_text, quoted_msg_id=msg_id)
    else:
        await send_whatsapp_message(remote_jid, reply_text, instance=instance_name)


@router.post("/webhook/{instance}")
async def handle_webhook(instance: str, payload: WebhookPayload):
    data = payload.data
    if payload.event == "messages.upsert" or "message" in data:
        asyncio.create_task(process_incoming_message(data, instance_name=instance))
    return {"status": "processing"}
