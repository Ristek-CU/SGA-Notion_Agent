import json
import re
from typing import Any, Dict, List
from app.ai.client import create_message
from app.ai.prompts import SYSTEM_PROMPT, EXTRACTION_PROMPT, CHAT_PROMPT
import app.notion.ticket_service as T
from app.notion.ticket_service import create_ticket_direct, resolve_division_id


def _page_title(pg: Dict[str, Any]) -> str:
    for v in pg.get("properties", {}).values():
        t = v.get("title", [])
        if t:
            return t[0].get("plain_text", "")
    return ""


async def _gather_task_context(sender_info: Dict[str, Any]) -> str:
    """Kumpulkan data tiket live pengirim utk diinjeksi ke konteks LLM."""
    try:
        from app.notion import ticket_service as T
        from app.services.contacts import get_all_contacts, load_contacts, normalize_phone

        pages = await T.query_tickets_direct()
        sender_name = (sender_info.get("name") or "").lower()
        sender_nickname = (sender_info.get("nickname") or "").lower()

        # Load contacts & find sender aliases
        contacts = await get_all_contacts()
        sender_contact = next(
            (c for c in contacts if normalize_phone(c.get("phone", "")) == normalize_phone(sender_info.get("phone", ""))),
            None
        )
        aliases = [sender_name, sender_nickname]
        if sender_contact:
            if sender_contact.get("name"):
                aliases.append(sender_contact.get("name").lower())
            if sender_contact.get("nickname"):
                aliases.append(sender_contact.get("nickname").lower())
            aliases.extend([a.lower() for a in sender_contact.get("aliases", [])])
        aliases = [a for a in set(aliases) if a]

        # In Notion DB, PIC is a Relation property pointing to Member Pages (ID e.g. 3313f1cb-81ff-8083-bc67-fcf95d8b85ff).
        # We also check if the sender name/nickname appears in any text or if pic_ids match.
        mine = []
        for p in pages:
            e = T._extract(p)
            title = e.get("title", "")
            title_lower = title.lower()
            status = e.get("status", "")
            
            # Jangan sertakan task yang sudah Done jika user menanyakan task aktif
            if status == "Done":
                continue

            is_mine = False
            pic_ids = e.get("pic_ids", [])
            pic_str = (e.get("pic") or "").lower()
            
            # Hanya cocokan jika alias pengirim ada di kolom PIC (bukan di judul)
            for alias in aliases:
                if alias and pic_str and (alias in pic_str or pic_str in alias):
                    is_mine = True
                    break
            
            # Known Salman PIC Relation ID fallback jika member list relation belum terpetakan di API
            if "3313f1cb-81ff-8083-bc67-fcf95d8b85ff" in pic_ids:
                is_mine = True

            if is_mine:
                mine.append(f"- {title} (Status: {status}, Prioritas: {e['priority'] or '-'})")

        ctx = ""
        if mine:
            ctx += "\n\nTASK SAYA HARI INI (PIC = Saya):\n" + "\n".join(mine)
        else:
            ctx += "\n\nTASK SAYA HARI INI: Tidak ada task aktif yang di-assign ke saya.\n"

        ctx += "\n\nATURAN RESPON RORO SAAT JAWAB TASK/SUMMARY:\n"
        ctx += "1. Sebutkan SEMUA task dari daftar 'TASK SAYA HARI INI' di atas.\n"
        ctx += "2. JANGAN PERNAH menampilkan daftar task tim / backlog umum milik orang lain kecuali user meminta daftar seluruh tim.\n"
        ctx += "3. Tampilkan jawaban dengan ringkas, ramah, dan to the point.\n"
        return ctx
    except Exception as e:
        return ""


async def handle_smart_message(message: str, sender_info: Dict[str, Any]) -> str:
    # 1. Ekstrak intent via AI
    messages = [
        {"role": "user", "content": f"{EXTRACTION_PROMPT}\nPesan: {message}"}
    ]
    try:
        raw_res = ""
        for attempt in range(2):  # retry: 9router kadang memotong stream -> JSON invalid
            try:
                raw_res = await create_message(messages, max_tokens=2000)  # reasoning model makan budget
                start = raw_res.find("{")
                end = raw_res.rfind("}") + 1
                if start != -1 and end != -1:
                    break
            except Exception:
                if attempt == 0:
                    import asyncio as _a
                    await _a.sleep(2)
        if not raw_res:
            return await handle_chat_with_context(message, sender_info)
        # Parse JSON
        start = raw_res.find("{")
        end = raw_res.rfind("}") + 1
        if start != -1 and end != -1:
            parsed = json.loads(raw_res[start:end])
            action = (parsed.get("action") or ("create" if parsed.get("title") else "none")).lower()
            title = parsed.get("title")
            div = parsed.get("division")
            prio = parsed.get("priority", "Medium") or "Medium"
            desc = parsed.get("description")

            if action in ("rename", "rename_and_status") and title:
                # cari tiket by judul/kode (resolver sama dgn jalur perintah)
                from app.ai.commands import _resolve_ticket
                pages = await T.query_tickets_direct()
                page, ambig = _resolve_ticket(pages, title)
                if ambig:
                    opts = "\n".join(f"- {t}" for t in ambig)
                    return f"🤔 Ada beberapa tiket mirip \"{title}\" — maksudmu yang mana?\n{opts}"
                if not page:
                    return f"Tiket \"{title}\" tidak ketemu di backlog. Cek judulnya atau kirim `list tiket` ya."
                new_props: Dict[str, Any] = {}
                new_title = parsed.get("new_title")
                if action == "rename" and not new_title:
                    return "Judul barunya apa? Contoh: `ganti nama tiket testing Roro jadi Testing Roro v2`"
                if new_title:
                    new_props["Name"] = {"title": [{"text": {"content": new_title}}]}
                if action in ("update_status", "rename_and_status"):
                    st = T.normalize_status(parsed.get("new_status") or "")
                    if not st:
                        return "Statusnya belum kebaca. Sebutkan misal: not started / in progress / done."
                    new_props["Status"] = {"status": {"name": st}}
                await T.update_ticket_direct(page["id"], new_props)
                e = T._extract(page)
                parts = ["✅ *Tiket berhasil diupdate!*"]
                if new_title:
                    parts += [f"• *Judul:* {new_title}", f"• *Nama lama:* {e['title']}"]
                else:
                    parts.append(f"• *Judul:* {e['title']}")
                if "Status" in new_props:
                    st = (new_props["Status"]["status"]["name"])
                    parts.append(f"• *Status:* {st}")
                parts.append(f"Cek: `detail tiket {T.ticket_code(page['id'])}`")
                return "\n".join(parts)

            if action == "create" and title:
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
                if pic_name and not pic_id:
                    out += f"\n⚠️ @{pic_name} tidak ditemukan di daftar anggota — tiket dibuat tanpa PIC."
                if pic_id and pic_name:
                    out += f"\n• *PIC:* {pic_name}"
                out += f"\nCek: `detail tiket {T.ticket_code(page_id)}`"
                return out
    except Exception:
        pass

    # Fallback to AI chat response if extraction fails
    return await handle_chat_with_context(message, sender_info)


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

    reply = await create_message(messages, system=sys, max_tokens=2000)
    return reply.strip() or "Maaf, coba ulangi pertanyaannya ya."


async def handle_chat_with_context(message: str, sender_info: Dict[str, Any]) -> str:
    """handle_chat + injeksi data tiket live — bot jawab pertanyaan data dgn bahasa natural."""
    task_ctx = await _gather_task_context(sender_info)
    if not task_ctx:
        return await handle_chat(message, sender_info)
    try:
        from app.services.session import session_manager
        sess = await session_manager.get_session(sender_info["phone"])
        history = [
            {"role": m["role"], "content": m["content"]}
            for m in (sess.messages if sess else [])[-8:]
            if m.get("role") in ("user", "assistant") and m.get("content")
        ] or []
    except Exception:
        history = []
    sys = (
        f"{SYSTEM_PROMPT}\nKamu punya akses data tiket live berikut. "
        f"Gunakan untuk menjawab pertanyaan soal task/tiket dengan bahasa natural — "
        f"JANGAN suruh user ketik perintah kalau kamu sudah bisa jawab langsung dari data ini."
        f"{task_ctx}"
    )
    messages = history + [{"role": "user", "content": message}]
    reply = await create_message(messages, system=sys, max_tokens=2000)
    return reply.strip() or "Maaf, coba ulangi pertanyaannya ya."
