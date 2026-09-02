import time
from typing import Dict, Any, Optional
from app.services.contacts import (
    find_contact_by_telegram,
    find_contact_by_phone,
    find_contact_by_push_name,
    find_name_by_phone,
    normalize_phone,
    _load_contacts_from_file,
)

_identity_cache: Dict[str, tuple[Dict[str, Any], float]] = {}
CACHE_TTL = 1800.0  # 30 minutes


def clear_identity_cache():
    """Clear cached resolved identities saat kontak ditambah/diupdate/dihapus."""
    global _identity_cache
    _identity_cache.clear()


async def resolve_identity_async(raw_identifier: str, push_name: Optional[str] = None, telegram_username: Optional[str] = None) -> Dict[str, Any]:
    cache_key = f"{raw_identifier}:{push_name or ''}:{telegram_username or ''}"
    now = time.monotonic()
    
    if cache_key in _identity_cache:
        res, exp = _identity_cache[cache_key]
        if now < exp:
            return res
        del _identity_cache[cache_key]

    phone = normalize_phone(raw_identifier) if raw_identifier and raw_identifier.replace("+", "").isdigit() else None
    matched_contact = None

    # 0. Username Telegram -> kontak
    if telegram_username:
        matched_contact = await find_contact_by_telegram(telegram_username)

    # 1. Phone lookup
    if not matched_contact and phone:
        matched_contact = await find_contact_by_phone(phone)

    # 2. Push name lookup
    if not matched_contact and push_name:
        matched_contact = await find_contact_by_push_name(push_name)

    if not matched_contact and raw_identifier and not phone:
        matched_contact = await find_contact_by_push_name(raw_identifier)

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


def resolve_identity(raw_identifier: str, push_name: Optional[str] = None, telegram_username: Optional[str] = None) -> Dict[str, Any]:
    """Sync wrapper using cache or sync lookups."""
    cache_key = f"{raw_identifier}:{push_name or ''}:{telegram_username or ''}"
    now = time.monotonic()
    if cache_key in _identity_cache:
        res, exp = _identity_cache[cache_key]
        if now < exp:
            return res
        del _identity_cache[cache_key]

    phone = normalize_phone(raw_identifier) if raw_identifier and raw_identifier.replace("+", "").isdigit() else None
    matched_contact = None

    # Sync file lookup fallback
    contacts = _load_contacts_from_file()
    if telegram_username:
        u = telegram_username.strip().lower().lstrip("@").rstrip("_")
        for c in contacts:
            tg = (c.get("telegram") or "").strip().lower().lstrip("@").rstrip("_")
            if tg and tg == u:
                matched_contact = c
                break

    if not matched_contact and phone:
        for c in contacts:
            if normalize_phone(c.get("phone", "")) == phone:
                matched_contact = c
                break

    if not matched_contact and push_name:
        pn_clean = push_name.strip().lower()
        for c in contacts:
            if c.get("name", "").strip().lower() == pn_clean or c.get("nickname", "").strip().lower() == pn_clean:
                matched_contact = c
                break
            aliases = [a.lower() for a in c.get("aliases", [])]
            if pn_clean in aliases:
                matched_contact = c
                break

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
