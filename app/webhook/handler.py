import asyncio
import traceback
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Request
from app.webhook.guard import check_out_of_scope
from app.services.identity import resolve_identity
from app.services.session import session_manager
from app.services.store import get_guard_state
from app.ai.commands import parse_command, handle_command
from app.ai.intent import handle_smart_message
from app.wa.sender import send_whatsapp_message, reply_to_group, lookup_lid_cache, set_lid_cache, start_typing, stop_typing, send_seen

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


async def _wa_typing_loop(chat_id: str, instance_name: Optional[str], stop_event: asyncio.Event):
    """Kirim sinyal typing berkala ke WAHA selama AI memproses pesan."""
    while not stop_event.is_set():
        await start_typing(chat_id, instance=instance_name)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=3.5)
        except asyncio.TimeoutError:
            pass


async def _send(reply_override, remote_jid: str, text: str, instance_name: Optional[str]):
    """Kirim balasan via override (mis. Telegram) jika ada, selain itu via WhatsApp."""
    if reply_override is not None:
        await reply_override(remote_jid, text)
    else:
        await send_whatsapp_message(remote_jid, text, instance=instance_name)


async def process_incoming_message(data: Dict[str, Any], instance_name: Optional[str] = None, reply_override=None, telegram_username: Optional[str] = None):
    stop_typing_event = asyncio.Event()
    typing_task = None
    target_for_typing = ""
    try:
        key = data.get("key", {})
        msg_id = key.get("id")
        # Hanya lakukan dedup jika msg_id bukan berupa ID generator manual atau evt_ ID
        if not msg_id or await is_duplicate_msg(msg_id):
            print(f"[PROCESS_INCOMING] SKIPPED DEDUP msg_id={msg_id}")
            return

        from_me = key.get("fromMe", False)
        if from_me:
            return

        remote_jid = key.get("remoteJid", "")
        is_group = remote_jid.endswith("@g.us")
        participant = key.get("participant") or remote_jid
        target_for_typing = remote_jid

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
        else:
            # Check if raw_sender matches any known LID in cache
            cached_phone = lookup_lid_cache(raw_sender)
            if cached_phone:
                raw_sender = cached_phone

        # Resolve sender identity (Telegram username dipakai utk cocokkan kontak)
        from app.services.identity import resolve_identity_async
        sender_info = await resolve_identity_async(raw_sender, push_name=push_name, telegram_username=telegram_username)

        # Auto-learn LID mapping jika berhasil diresolve ke kontak DB
        if "@lid" in participant and sender_info.get("is_known") and sender_info.get("phone"):
            set_lid_cache(participant, sender_info["phone"])
            set_lid_cache(raw_sender, sender_info["phone"])

        # Whitelist check: Abaikan pesan jika user tidak dikenal (tidak ada di daftar kontak/whitelist)
        if not sender_info.get("is_known"):
            print(f"[PROCESS_INCOMING] DROPPED UNKNOWN USER raw_sender={raw_sender} participant={participant} push_name={push_name}")
            return

        # 1. Pastikan chat di-read (centang biru) terlebih dahulu sampai selesai
        if reply_override is None:
            try:
                await send_seen(
                    chat_id=remote_jid,
                    message_id=msg_id,
                    participant=participant if is_group else None,
                    instance=instance_name,
                )
                await asyncio.sleep(0.3)  # Jeda singkat agar status read terdaftar sempurna di server WhatsApp
            except Exception:
                pass
            # 2. Setelah status read aktif, baru jalankan typing presence
            typing_task = asyncio.create_task(_wa_typing_loop(target_for_typing, instance_name, stop_typing_event))

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
            try:
                reply_text = await handle_smart_message(text, sender_info)
            except Exception as ai_err:
                print(f"[AI_ERROR] AI response generation failed: {ai_err}\n{traceback.format_exc()}")
                reply_text = "Maaf, sistem sedang mengalami kendala sementara saat memproses pesan. Mohon coba beberapa saat lagi ya."

        # Save assistant reply to session
        await session_manager.save_assistant_response(sender_info["phone"], reply_text)

        # Send response back to WA (Gunakan sender_info["phone"] jika remote_jid berupa @lid)
        target_jid = sender_info["phone"] if "@lid" in remote_jid else remote_jid
        if is_group:
            await reply_to_group(remote_jid, reply_text, quoted_msg_id=msg_id)
        else:
            await _send(reply_override, target_jid, reply_text, instance_name)
    except Exception as e:
        print(f"[PROCESS_INCOMING_ERROR] Error processing message {data.get('key', {}).get('id')}: {e}\n{traceback.format_exc()}")
    finally:
        if typing_task:
            stop_typing_event.set()
            typing_task.cancel()
            if target_for_typing and reply_override is None:
                asyncio.create_task(stop_typing(target_for_typing, instance=instance_name))


@router.post("/webhook/{instance}")
async def handle_webhook(instance: str, payload: WebhookPayload, request: Request):
    raw_body = {}
    try:
        raw_body = await request.json()
        print(f"[WAHA WEBHOOK RECEIVE] instance={instance} event={payload.event} body={str(raw_body)[:300]}")
    except Exception:
        pass

    # Process payload/data from request
    msg_data = payload.payload or payload.data or raw_body.get("payload") or raw_body.get("data") or raw_body
    if msg_data and isinstance(msg_data, dict):
        msg = normalize_waha_message(msg_data)
        # Gunakan ID event unik dari outer payload jika inner message ID tidak unik/kosong
        event_id = payload.event and raw_body.get("id")
        if not msg["key"].get("id") and event_id:
            msg["key"]["id"] = event_id
            
        if msg["key"].get("id"):
            # Enqueue incoming WA chat to Chat Priority Queue
            from app.services.queue import queue_manager
            # Ensure queue manager is running
            queue_manager.start()
            sender_preview = msg.get("pushName") or msg["key"].get("participant") or msg["key"].get("remoteJid", "")
            msg_text = (msg.get("message", {}).get("conversation") or msg.get("message", {}).get("extendedTextMessage", {}).get("text") or "")
            await queue_manager.enqueue_chat(
                handler=lambda m=msg, inst=instance: process_incoming_message(m, instance_name=inst),
                sender=sender_preview,
                platform="WhatsApp",
                preview=msg_text,
            )
        return {"status": "processing"}

    return {"status": "processing"}
