import time
from typing import Dict, Any, Optional
from app.services.contacts import (
    find_contact_by_push_name,
    find_name_by_phone,
    find_phone_by_name,
    get_all_contacts,
    normalize_phone,
)

_identity_cache: Dict[str, tuple[Dict[str, Any], float]] = {}
CACHE_TTL = 1800.0  # 30 minutes


def resolve_identity(raw_identifier: str, push_name: Optional[str] = None, telegram_username: Optional[str] = None) -> Dict[str, Any]:
    cache_key = f"{raw_identifier}:{push_name or ''}:{telegram_username or ''}"
    now = time.monotonic()
    
    if cache_key in _identity_cache:
        res, exp = _identity_cache[cache_key]
        if now < exp:
            return res
        del _identity_cache[cache_key]

    phone = normalize_phone(raw_identifier) if raw_identifier and raw_identifier.replace("+", "").isdigit() else None
    
    matched_name = None
    matched_contact = None

    # 0. Username Telegram -> kontak (field `telegram`)
    if telegram_username:
        from app.services.contacts import find_contact_by_telegram
        matched_contact = find_contact_by_telegram(telegram_username)

    # 1. Hierarki: push_name -> phone lookup -> contact search
    if not matched_contact and push_name:
        matched_contact = find_contact_by_push_name(push_name)
    
    if not matched_contact and phone:
        name_from_phone = find_name_by_phone(phone)
        if name_from_phone:
            matched_contact = find_contact_by_push_name(name_from_phone)

    if not matched_contact and raw_identifier and not phone:
        matched_contact = find_contact_by_push_name(raw_identifier)

    if matched_contact:
        result = {
            "name": matched_contact.get("name"),
            "nickname": matched_contact.get("nickname") or matched_contact.get("name"),
            "phone": matched_contact.get("phone"),
            "division": matched_contact.get("division"),
            "role": matched_contact.get("role"),
            "is_known": True,
        }
    else:
        # Fallback unknown user
        display = push_name or (f"+{phone}" if phone else raw_identifier)
        result = {
            "name": display,
            "nickname": display,
            "phone": phone or raw_identifier,
            "division": None,
            "role": "User",
            "is_known": False,
        }

    _identity_cache[cache_key] = (result, now + CACHE_TTL)
    return result
