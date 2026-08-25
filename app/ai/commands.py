import re
from typing import Optional, Dict, Any, Tuple

COMMAND_PATTERNS = [
    ("help", r"^(help|bantuan|\?)$"),
    ("stats", r"^(stats|statistik|summary|ringkasan)$"),
    ("list_tickets", r"^(list|daftar)\s+(tiket|ticket|backlog)"),
    ("my_tickets", r"^(tiket|tugas)\s+saya$"),
    ("create_ticket", r"^(buat|create|tambah)\s+(tiket|ticket)\s+(.+)"),
    ("ticket_detail", r"^(detail|cek)\s+(tiket|ticket)\s+([a-zA-Z0-9\-]+)$"),
    ("update_status", r"^(update|ubah)\s+status\s+([a-zA-Z0-9\-]+)\s+(.+)"),
    ("assign_pic", r"^(assign|tunjuk)\s+([a-zA-Z0-9\-]+)\s+(ke|to)\s+(.+)"),
    ("list_divisions", r"^(list|daftar)\s+(divisi|division)$"),
    ("list_members", r"^(list|daftar)\s+(member|anggota)$"),
]


def parse_command(message: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    raw_text = message.strip()
    text_lower = raw_text.lower()
    for cmd_type, pat in COMMAND_PATTERNS:
        match_lower = re.search(pat, text_lower, re.IGNORECASE)
        if match_lower:
            # Preserve original case for args
            match_orig = re.search(pat, raw_text, re.IGNORECASE)
            args = match_orig.groups() if match_orig else match_lower.groups()
            kwargs = {}
            if cmd_type == "create_ticket" and len(args) >= 3:
                kwargs["title"] = args[2]
            elif cmd_type == "ticket_detail" and len(args) >= 3:
                kwargs["ticket_id"] = args[2]
            elif cmd_type == "update_status":
                kwargs["ticket_id"] = args[1]
                kwargs["status"] = args[2]
            elif cmd_type == "assign_pic":
                kwargs["ticket_id"] = args[1]
                kwargs["pic_name"] = args[3]
            return cmd_type, kwargs
    return None


def _prop(page: Dict[str, Any], key: str):
    return page.get("properties", {}).get(key, {})


def _title_of(page: Dict[str, Any]) -> str:
    t = _prop(page, "Name").get("title", [])
    return t[0].get("plain_text", "") if t else ""


def _tid_of(page: Dict[str, Any]) -> str:
    rt = _prop(page, "ID").get("rich_text", [])
    return rt[0].get("plain_text", "?") if rt else "?"


async def handle_command(cmd_type: str, args: Dict[str, Any], sender_info: Dict[str, Any]) -> str:
    from app.notion import ticket_service as T
    from app.notion import org_service as O
    from app.services.contacts import load_contacts

    if cmd_type == "help":
        return (
            "📌 *Perintah Notion Agent SGA:*\n"
            "- `list tiket` : Lihat daftar tiket aktif\n"
            "- `tiket saya` : Lihat tiket yang ditugaskan ke kamu\n"
            "- `buat tiket <judul>` : Buat tiket baru\n"
            "- `detail tiket <id>` : Cek detail tiket\n"
            "- `update status <id> <status>` : Ubah status tiket\n"
            "- `assign <id> to <nama>` : Tunjuk PIC tiket\n"
            "- `list divisi` : Lihat daftar divisi\n"
            "- `list anggota` : Daftar anggota tim\n"
            "- `stats` : Ringkasan statistik backlog"
        )

    if cmd_type == "create_ticket":
        title = (args.get("title") or "").strip()
        # format opsional "@nama" di akhir judul -> assign PIC
        pic_name, pic_id = None, None
        m = re.search(r"\s@([A-Za-z0-9_.\-]+)\s*$", title)
        if m:
            pic_name = m.group(1)
            title = title[: m.start()].strip()
        division = sender_info.get("division")
        try:
            if pic_name:
                contacts = load_contacts()
                match = next((c for c in contacts
                              if pic_name.lower() in ((c.get("nickname") or "").lower(), (c.get("name") or "").lower())), None)
                if match:
                    mems = await O.list_members()
                    target = next((pg for pg in mems
                                   if _title_of(pg).lower() == (match.get("name") or "").lower()), None)
                    if target:
                        pic_id = target["id"]
            res = await T.create_ticket_direct(
                title=title,
                division=division,
                description=f"Dibuat via bot oleh {sender_info.get('nickname', 'unknown')}",
                pic_id=pic_id,
            )
            page_id = res["page"]["id"]
            out = (
                f"✅ *Tiket berhasil dibuat!*\n"
                f"• *Judul:* {title}\n"
                f"• *Divisi:* {division or 'Unassigned'}\n"
                f"• *Status:* Not started"
            )
            if pic_id and pic_name:
                out += f"\n• *PIC:* @{pic_name}"
            out += f"\nCek: `detail tiket {page_id[:8]}`"
            return out
        except Exception as e:
            return f"⚠️ Gagal membuat tiket ke Notion: {type(e).__name__}. Coba lagi sebentar ya."

    if cmd_type == "list_tickets":
        try:
            pages = await T.query_tickets_direct()
            pages = pages[:10]
            if not pages:
                return "📋 Belum ada tiket di backlog."
            lines = ["📋 *Daftar Tiket Terbaru:*"]
            for p in pages:
                e = T._extract(p)
                lines.append(f"- `{(e['page_id'] or '?')[:8]}` {e['title'][:40]} ({e['status']})")
            return "\n".join(lines)
        except Exception as e:
            return f"⚠️ Gagal mengambil tiket: {type(e).__name__}"

    if cmd_type == "my_tickets":
        nickname = (sender_info.get("nickname") or "").lower()
        try:
            pages = await T.query_tickets_direct()
            mine = []
            for p in pages:
                pic = _prop(p, "PIC").get("relation", [])
                people = _prop(p, "Assignee").get("people", [])
                names = []
                for rel in pic:
                    names.append(rel.get("id", ""))
                for pe in people:
                    names.append((pe.get("name") or "").lower())
                if not names:
                    continue
                # match via members db id -> nama -> nickname
                if nickname:
                    mems = await O.list_members()
                    id2nick = {}
                    for c in load_contacts():
                        id2nick[(c.get("name") or "").lower()] = (c.get("nickname") or "").lower()
                    for pg in mems:
                        n = _title_of(pg).lower()
                        if id2nick.get(n) == nickname and pg["id"] in names:
                            st = _prop(p, "Status").get("status", {}).get("name", "?")
                            mine.append(f"- `{_tid_of(p)}` {_title_of(p)} ({st})")
                            break
            if not mine:
                return f"📋 Tidak ada tiket yang ditugaskan ke kamu saat ini."
            return f"📋 *Tiket Ditugaskan ke {sender_info.get('nickname')}:*\n" + "\n".join(mine[:10])
        except Exception as e:
            return f"⚠️ Gagal mengambil tiketmu: {type(e).__name__}"

    if cmd_type == "ticket_detail":
        tid = args.get("ticket_id", "")
        try:
            pages = await T.query_tickets_direct()
            page = T._find_by_ticket_prefix(pages, tid)
            if not page:
                return f"🔍 Tiket `{tid}` tidak ditemukan. Cek `list tiket` dulu ya."
            e = T._extract(page)
            return (
                f"🔍 *Detail Tiket*\n"
                f"• Judul: {e['title']}\n"
                f"• Status: {e['status']}\n"
                f"• Prioritas: {e['priority'] or '-'}\n"
                f"• ID: `{(e['page_id'] or '?')[:8]}`"
            )
        except Exception as e:
            return f"⚠️ Gagal ambil detail: {type(e).__name__}"

    if cmd_type == "update_status":
        tid, status = args.get("ticket_id", ""), args.get("status", "")
        status_name = T.normalize_status(status)
        try:
            pages = await T.query_tickets_direct()
            page = T._find_by_ticket_prefix(pages, tid)
            if not page:
                return f"🔍 Tiket `{tid}` tidak ditemukan."
            await T.update_ticket_direct(page["id"], {"Status": {"status": {"name": status_name}}})
            e = T._extract(page)
            return f"✅ Status *{e['title'][:40]}* sekarang *{status_name}*."
        except Exception as e:
            return f"⚠️ Gagal update status: {type(e).__name__} — opsi valid: {', '.join(T.VALID_STATUSES)}."

    if cmd_type == "assign_pic":
        tid, pic_name = args.get("ticket_id", ""), (args.get("pic_name") or "").strip().lstrip("@")
        try:
            pages = await T.query_tickets_direct()
            page = T._find_by_ticket_prefix(pages, tid)
            if not page:
                return f"🔍 Tiket `{tid}` tidak ditemukan."
            mems = await O.list_members()
            nick_map = {((c.get("name") or "").lower()): ((c.get("nickname") or "").lower()) for c in load_contacts()}
            target = next(
                (pg for pg in mems
                 if pic_name.lower() in (_title_of(pg).lower(), nick_map.get(_title_of(pg).lower(), "")))
                , None)
            if not target:
                return f"👤 Anggota \"{pic_name}\" tidak ditemukan di DB Members."
            await T.update_ticket_direct(page["id"], {"PIC": {"relation": [{"id": target["id"]}]}})
            return f"👤 Tiket *{_title_of(page)[:40]}* berhasil di-assign ke *{_title_of(target)}*."
        except Exception as e:
            return f"⚠️ Gagal assign PIC: {type(e).__name__}"

    if cmd_type == "stats":
        try:
            s = await O.get_backlog_stats()
            by_status = s.get("by_status", {})
            total = s.get("total", sum(by_status.values()))
            parts = " | ".join(f"{k}: {v}" for k, v in by_status.items())
            return f"📊 *Statistik Backlog SGA:*\nTotal Tiket: {total}\n{parts}"
        except Exception as e:
            return f"⚠️ Gagal mengambil statistik: {type(e).__name__}"

    if cmd_type == "list_divisions":
        try:
            divs = await O.list_divisions()
            names = []
            for d in divs:
                props = d.get("properties", {})
                t = props.get("Name", {}).get("title", [])
                nm = t[0].get("plain_text") if t else d.get("name")
                if nm:
                    names.append(nm)
            return "🏢 *Daftar Divisi SGA:*\n" + "\n".join(f"{i}. {n}" for i, n in enumerate(sorted(names), 1))
        except Exception as e:
            return f"⚠️ Gagal mengambil divisi: {type(e).__name__}"

    if cmd_type == "list_members":
        try:
            mems = await O.list_members()
            if not mems:
                return "👥 Data anggota kosong."
            contacts = {(c.get("name") or "").lower(): c.get("nickname") for c in await load_contacts()}
            lines = [f"👥 *Anggota SGA ({len(mems)}):*"]
            for pg in mems[:15]:
                n = _title_of(pg)
                lines.append(f"- {n}" + (f" (@{contacts[n.lower()]})" if contacts.get(n.lower()) else ""))
            if len(mems) > 15:
                lines.append(f"... dan {len(mems)-15} lainnya")
            return "\n".join(lines)
        except Exception as e:
            return f"⚠️ Gagal mengambil anggota: {type(e).__name__}"

    return "Perintah tidak dikenali. Ketik `help`."
