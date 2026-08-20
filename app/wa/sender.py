import os
import json
import httpx
from typing import Optional, Dict, Any
from app.config import settings

LID_CACHE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "cache", "lid-cache.json")
_lid_cache: Dict[str, str] = {}


def load_lid_cache() -> Dict[str, str]:
    global _lid_cache
    if _lid_cache:
        return _lid_cache
    if os.path.exists(LID_CACHE_FILE):
        try:
            with open(LID_CACHE_FILE, "r", encoding="utf-8") as f:
                _lid_cache = json.load(f)
        except Exception:
            _lid_cache = {}
    
    # Load manual LID_PHONE_MAP from env if provided (format: "lid1=phone1,lid2=phone2")
    if settings.lid_phone_map:
        pairs = settings.lid_phone_map.split(",")
        for pair in pairs:
            if "=" in pair:
                k, v = pair.split("=", 1)
                _lid_cache[k.strip()] = v.strip()
    return _lid_cache


def save_lid_cache():
    os.makedirs(os.path.dirname(LID_CACHE_FILE), exist_ok=True)
    temp_path = f"{LID_CACHE_FILE}.tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(_lid_cache, f, indent=2)
    os.replace(temp_path, LID_CACHE_FILE)


def lookup_lid_cache(lid: str) -> Optional[str]:
    cache = load_lid_cache()
    return cache.get(lid)


def set_lid_cache(lid: str, phone: str):
    cache = load_lid_cache()
    cache[lid] = phone
    save_lid_cache()


async def send_whatsapp_message(
    number_or_jid: str,
    text: str,
    instance: Optional[str] = None,
    quoted_msg_id: Optional[str] = None
) -> Dict[str, Any]:
    target_instance = instance or settings.evolution_instance_name
    url = f"{settings.evolution_api_url.rstrip('/')}/message/sendText/{target_instance}"
    
    # Clean JID/number format
    recipient = number_or_jid
    if not recipient.endswith("@s.whatsapp.net") and not recipient.endswith("@g.us"):
        cleaned = "".join(c for c in recipient if c.isdigit())
        recipient = f"{cleaned}@s.whatsapp.net"

    payload: Dict[str, Any] = {
        "number": recipient,
        "options": {
            "delay": 1200,
            "presence": "composing",
            "linkPreview": True,
        },
        "textMessage": {
            "text": text
        }
    }

    if quoted_msg_id:
        payload["options"]["quoted"] = {"key": {"id": quoted_msg_id}}

    headers = {
        "apikey": settings.evolution_api_key,
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        return resp.json()


async def reply_to_group(group_jid: str, text: str, quoted_msg_id: Optional[str] = None) -> Dict[str, Any]:
    return await send_whatsapp_message(group_jid, text, quoted_msg_id=quoted_msg_id)


async def send_direct_message(phone: str, text: str) -> Dict[str, Any]:
    return await send_whatsapp_message(phone, text)


async def check_number_status(phone: str, instance: Optional[str] = None) -> Dict[str, Any]:
    target_instance = instance or settings.evolution_instance_name
    url = f"{settings.evolution_api_url.rstrip('/')}/chat/whatsappNumbers/{target_instance}"
    headers = {"apikey": settings.evolution_api_key, "Content-Type": "application/json"}
    payload = {"numbers": [phone]}
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        return resp.json()


async def fetch_bot_jid(instance: Optional[str] = None) -> Optional[str]:
    target_instance = instance or settings.evolution_instance_name
    url = f"{settings.evolution_api_url.rstrip('/')}/instance/fetchInstances"
    headers = {"apikey": settings.evolution_api_key}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                for inst in data:
                    if inst.get("name") == target_instance or inst.get("instance", {}).get("instanceName") == target_instance:
                        owner = inst.get("ownerJid") or inst.get("instance", {}).get("owner")
                        if owner:
                            return owner
    except Exception:
        pass
    return None
