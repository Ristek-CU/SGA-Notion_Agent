import json
import re
from typing import Dict, Any, List
from app.ai.client import create_message
from app.ai.prompts import SYSTEM_PROMPT, EXTRACTION_PROMPT, CHAT_PROMPT
from app.notion.ticket_service import create_ticket_direct, resolve_division_id


def _page_title(pg: Dict[str, Any]) -> str:
    for v in pg.get("properties", {}).values():
        t = v.get("title", [])
        if t:
            return t[0].get("plain_text", "")
    return ""


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
                # @mention di kalimat natural -> PIC (nickname atau nama, via kontak)
                pic_id = None
                pic_name = None
                m = re.search(r"@([A-Za-z0-9_.\-]+)", message)
                if m:
                    from app.services.contacts import load_contacts
                    from app.notion import org_service as O
                    handle = m.group(1).lower()
                    contact = next((c for c in load_contacts()
                                    if handle in ((c.get("nickname") or "").lower(), (c.get("name") or "").lower())), None)
                    if contact:
                        mems = await O.list_members()
                        target = next((pg for pg in mems if _page_title(pg).lower() == (contact.get("name") or "").lower()), None)
                        if target:
                            pic_id = target["id"]
                            pic_name = contact.get("name")
                div_id = await resolve_division_id(div)
                res = await create_ticket_direct(
                    title=title,
                    division=div,
                    priority=prio,
                    description=desc,
                    pic_id=pic_id,
                    division_id=div_id,
                )
                page_id = res["page"]["id"]
                out = (
                    f"✅ *Tiket Otomatis Dibuat!*\n"
                    f"• *Judul:* {title}\n"
                    f"• *Divisi:* {div or 'Unassigned'}\n"
                    f"• *Prioritas:* {prio}\n"
                    f"• *Status:* Not started"
                )
                if pic_id and pic_name:
                    out += f"\n• *PIC:* {pic_name}"
                out += f"\nCek: `detail tiket {page_id[:8]}`"
                return out
    except Exception:
        pass

    # Fallback to AI chat response if extraction fails
    return await handle_chat(message, sender_info)


async def handle_chat(message: str, sender_info: Dict[str, Any]) -> str:
    nickname = sender_info.get("nickname", "User")
    sys = (
        f"{SYSTEM_PROMPT}\n"
        f"User bernama {nickname} dari divisi {sender_info.get('division') or 'Umum'} "
        f"(role: {sender_info.get('role') or 'anggota'})."
    )
    # Riwayat percakapan (Redis, TTL 30 menit) supaya jawaban kontekstual
    history: List[Dict[str, str]] = []
    try:
        from app.services.session import session_manager
        sess = await session_manager.get_session(sender_info["phone"])
        if sess and sess.messages:
            history = [
                {"role": m["role"], "content": m["content"]}
                for m in sess.messages[-10:]
                if m.get("role") in ("user", "assistant") and m.get("content")
            ]
    except Exception:
        pass  # tanpa riwayat pun tetap jawab

    messages: List[Dict[str, str]] = []
    if history and history[-1].get("role") == "user":
        messages.extend(history[:-1])
        messages.append({"role": "user", "content": message})
    else:
        messages.extend(history)
        if not messages or messages[-1] != {"role": "user", "content": message}:
            messages.append({"role": "user", "content": message})

    reply = await create_message(messages, system=sys, max_tokens=800)
    return reply.strip() or "Maaf, coba ulangi pertanyaannya ya."
