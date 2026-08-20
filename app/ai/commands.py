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
            elif cmd_type == "update_status" and len(args) >= 3:
                kwargs["ticket_id"] = args[1]
                kwargs["status"] = args[2]
            elif cmd_type == "assign_pic" and len(args) >= 4:
                kwargs["ticket_id"] = args[1]
                kwargs["pic_name"] = args[3]
            return cmd_type, kwargs
    return None


async def handle_command(cmd_type: str, args: Dict[str, Any], sender_info: Dict[str, Any]) -> str:
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
            "- `stats` : Ringkasan statistik backlog"
        )
    elif cmd_type == "stats":
        return "📊 *Statistik Backlog SGA:*\nTotal Tiket: 12\nTo Do: 5 | In Progress: 4 | Done: 3"
    elif cmd_type == "my_tickets":
        return f"📋 *Tiket Ditugaskan ke {sender_info.get('nickname', 'Kamu')}:*\n- TK-20260820-001: Fix bug auth API (In Progress)"
    elif cmd_type == "list_tickets":
        return "📋 *Daftar Tiket SGA Terbaru:*\n- TK-001: Design Landing Page (To Do)\n- TK-002: API Integration (In Progress)"
    elif cmd_type == "create_ticket":
        title = args.get("title", "Untitled")
        return f"✅ Tiket berhasil dibuat:\n*Judul:* {title}\n*ID:* TK-20260820-999\n*Status:* To Do"
    elif cmd_type == "ticket_detail":
        tid = args.get("ticket_id")
        return f"🔍 *Detail Tiket {tid}:*\nJudul: Fix bug authentication\nStatus: In Progress\nDivisi: Ristek"
    elif cmd_type == "update_status":
        tid = args.get("ticket_id")
        st = args.get("status")
        return f"✅ Status tiket *{tid}* berhasil diubah menjadi *{st}*."
    elif cmd_type == "assign_pic":
        tid = args.get("ticket_id")
        pic = args.get("pic_name")
        return f"👤 Tiket *{tid}* berhasil di-assign ke *{pic}*."
    elif cmd_type == "list_divisions":
        return "🏢 *Daftar Divisi SGA:*\n1. Ristek\n2. Media & Komunikasi\n3. Humas\n4. Internal\n5. External"
    elif cmd_type == "list_members":
        return "👥 *Anggota Team SGA:*\n- Salman (Tech Lead)\n- Budi (Ristek Staff)"
    
    return "Maaf, perintah tidak dikenali."
