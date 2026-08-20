import asyncio
from typing import Optional
from app.services.contacts import find_phone_by_name
from app.wa.sender import send_direct_message


async def notify_pic(pic_name: str, ticket_id: str, ticket_title: str, assigner: str) -> bool:
    phone = find_phone_by_name(pic_name)
    if not phone:
        return False

    msg = (
        f"🔔 *Penugasan Tiket Baru*\n\n"
        f"Halo {pic_name},\n"
        f"Kamu telah ditunjuk oleh *{assigner}* untuk menangani tiket:\n"
        f"• *ID:* {ticket_id}\n"
        f"• *Judul:* {ticket_title}\n\n"
        f"Silakan periksa Notion SGA untuk detail lebih lanjut."
    )

    for attempt in range(2):
        try:
            await send_direct_message(phone, msg)
            return True
        except Exception:
            if attempt == 0:
                await asyncio.sleep(2.0)

    return False
