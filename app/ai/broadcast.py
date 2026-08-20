import asyncio
from typing import List, Dict, Any
from app.services.contacts import get_all_contacts
from app.wa.sender import send_direct_message


async def handle_broadcast_task_notifications(target_division: str = "all", message: str = "") -> Dict[str, Any]:
    contacts = get_all_contacts()
    sent_count = 0
    failed_count = 0

    for contact in contacts:
        phone = contact.get("phone")
        div = contact.get("division")

        if not phone:
            continue

        if target_division != "all" and div and div.lower() != target_division.lower():
            continue

        body = (
            f"📢 *Pengumuman SGA ({div or 'Umum'})*\n\n"
            f"Halo {contact.get('nickname') or contact.get('name')},\n"
            f"{message}\n\n"
            f"— Notion Agent SGA"
        )

        try:
            await send_direct_message(phone, body)
            sent_count += 1
            await asyncio.sleep(1.0)  # Delay 1s to prevent WA spam ban
        except Exception:
            failed_count += 1

    return {"sent": sent_count, "failed": failed_count}
