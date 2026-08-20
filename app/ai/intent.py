import json
from typing import Dict, Any
from app.ai.client import create_message
from app.ai.prompts import SYSTEM_PROMPT, EXTRACTION_PROMPT, CHAT_PROMPT
from app.notion.ticket_service import create_ticket_direct


async def handle_smart_message(message: str, sender_info: Dict[str, Any]) -> str:
    # 1. Ekstrak intent via AI
    messages = [
        {"role": "user", "content": f"{EXTRACTION_PROMPT}\nPesan: {message}"}
    ]
    try:
        raw_res = await create_message(messages, max_tokens=300)
        # Parse JSON
        start = raw_res.find("{")
        end = raw_res.rfind("}") + 1
        if start != -1 and end != -1:
            parsed = json.loads(raw_res[start:end])
            title = parsed.get("title")
            div = parsed.get("division")
            prio = parsed.get("priority", "Medium")
            desc = parsed.get("description")

            if title:
                # Direct creation if title found
                res = await create_ticket_direct(
                    title=title,
                    division=div,
                    priority=prio,
                    description=desc,
                )
                tid = res.get("ticket_id")
                return (
                    f"✅ *Tiket Otomatis Dibuat!*\n"
                    f"• *ID:* {tid}\n"
                    f"• *Judul:* {title}\n"
                    f"• *Divisi:* {div or 'Unassigned'}\n"
                    f"• *Prioritas:* {prio}"
                )
    except Exception:
        pass

    # Fallback to AI chat response if extraction fails
    return await handle_chat(message, sender_info)


async def handle_chat(message: str, sender_info: Dict[str, Any]) -> str:
    nickname = sender_info.get("nickname", "User")
    sys = f"{SYSTEM_PROMPT}\nUser bernama {nickname} dari divisi {sender_info.get('division') or 'Umum'}."
    messages = [{"role": "user", "content": message}]
    return await create_message(messages, system=sys, max_tokens=500)
