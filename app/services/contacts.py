import os
import json
import re
import logging
from typing import Optional, Dict, Any, List
from app.config import settings

logger = logging.getLogger(__name__)


def get_contacts_file_path() -> str:
    base_dir = os.getcwd()
    path = os.path.join(base_dir, "config", "contacts.json")
    if not os.path.exists(path):
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config", "contacts.json")
    return path


def normalize_phone(phone: str) -> str:
    cleaned = re.sub(r"\D", "", phone or "")
    if cleaned.startswith("0"):
        cleaned = "62" + cleaned[1:]
    elif not cleaned.startswith("62") and cleaned:
        cleaned = "62" + cleaned
    return cleaned


_contacts_cache: Optional[List[Dict[str, Any]]] = None
_last_mtime: float = 0.0


def _load_contacts_from_file() -> List[Dict[str, Any]]:
    global _contacts_cache, _last_mtime
    file_path = get_contacts_file_path()
    if not os.path.exists(file_path):
        return []
    try:
        mtime = os.path.getmtime(file_path)
        if _contacts_cache is None or mtime > _last_mtime:
            with open(file_path, "r", encoding="utf-8") as f:
                _contacts_cache = json.load(f)
            _last_mtime = mtime
        return _contacts_cache or []
    except Exception:
        return _contacts_cache or []


def _save_contacts_to_file(contacts: List[Dict[str, Any]]):
    global _contacts_cache, _last_mtime
    file_path = get_contacts_file_path()
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    temp_path = f"{file_path}.tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(contacts, f, indent=2, ensure_ascii=False)
    os.replace(temp_path, file_path)
    _contacts_cache = contacts
    _last_mtime = os.path.getmtime(file_path)
    try:
        from app.services.identity import clear_identity_cache
        clear_identity_cache()
    except Exception:
        pass


async def get_all_contacts() -> List[Dict[str, Any]]:
    """Ambil semua kontak dari PostgreSQL jika tersedia, fallback ke file json."""
    try:
        from app.services.database import get_db_pool
        pool = await get_db_pool()
        if pool:
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT id, name, nickname, phone, telegram, division, role, aliases FROM contacts ORDER BY name ASC"
                )
                return [dict(r) for r in rows]
    except Exception as e:
        logger.warning(f"Error fetching contacts from DB: {e}")
    return _load_contacts_from_file()


def get_all_contacts_sync() -> List[Dict[str, Any]]:
    """Sync fallback for non-async parts."""
    return _load_contacts_from_file()


# Aliases for backward compatibility
def load_contacts() -> List[Dict[str, Any]]:
    return _load_contacts_from_file()


def save_contacts(contacts: List[Dict[str, Any]]):
    _save_contacts_to_file(contacts)


async def find_contact_by_telegram(username: str) -> Optional[Dict[str, Any]]:
    if not username:
        return None
    u = username.strip().lower().lstrip("@").rstrip("_")
    if not u:
        return None

    try:
        from app.services.database import get_db_pool
        pool = await get_db_pool()
        if pool:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT id, name, nickname, phone, telegram, division, role, aliases
                    FROM contacts
                    WHERE LOWER(TRIM(LEADING '@' FROM telegram)) = $1
                    LIMIT 1
                    """,
                    u
                )
                if row:
                    return dict(row)
    except Exception as e:
        logger.warning(f"DB find_contact_by_telegram error: {e}")

    # Fallback to local
    for c in _load_contacts_from_file():
        tg = (c.get("telegram") or "").strip().lower().lstrip("@").rstrip("_")
        if tg and tg == u:
            return c
    return None


async def find_contact_by_phone(phone: str) -> Optional[Dict[str, Any]]:
    if not phone:
        return None
    norm = normalize_phone(phone)
    if not norm:
        return None

    try:
        from app.services.database import get_db_pool
        pool = await get_db_pool()
        if pool:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT id, name, nickname, phone, telegram, division, role, aliases FROM contacts WHERE phone = $1 LIMIT 1",
                    norm
                )
                if row:
                    return dict(row)
    except Exception as e:
        logger.warning(f"DB find_contact_by_phone error: {e}")

    for c in _load_contacts_from_file():
        if normalize_phone(c.get("phone", "")) == norm:
            return c
    return None


async def find_contact_by_push_name(push_name: str) -> Optional[Dict[str, Any]]:
    if not push_name:
        return None
    pn_clean = push_name.strip().lower()

    try:
        from app.services.database import get_db_pool
        pool = await get_db_pool()
        if pool:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT id, name, nickname, phone, telegram, division, role, aliases
                    FROM contacts
                    WHERE LOWER(name) = $1
                       OR LOWER(nickname) = $1
                       OR $1 = ANY(SELECT LOWER(unnest(aliases)))
                    LIMIT 1
                    """,
                    pn_clean
                )
                if row:
                    return dict(row)
    except Exception as e:
        logger.warning(f"DB find_contact_by_push_name error: {e}")

    contacts = _load_contacts_from_file()
    for c in contacts:
        if c.get("name", "").strip().lower() == pn_clean or c.get("nickname", "").strip().lower() == pn_clean:
            return c
        aliases = [a.lower() for a in c.get("aliases", [])]
        if pn_clean in aliases:
            return c
    return None


def find_name_by_phone(phone: str) -> Optional[str]:
    c = find_contact_by_phone_sync(phone)
    return c.get("name") if c else None


def find_phone_by_name(name_query: str) -> Optional[str]:
    if not name_query:
        return None
    q = name_query.strip().lower()
    for c in _load_contacts_from_file():
        if c.get("name", "").strip().lower() == q or c.get("nickname", "").strip().lower() == q:
            return c.get("phone")
        aliases = [a.lower() for a in c.get("aliases", [])]
        if q in aliases:
            return c.get("phone")
    return None


def find_contact_by_phone_sync(phone: str) -> Optional[Dict[str, Any]]:
    if not phone:
        return None
    norm = normalize_phone(phone)
    for c in _load_contacts_from_file():
        if normalize_phone(c.get("phone", "")) == norm:
            return c
    return None


def find_contact_by_push_name_sync(push_name: str) -> Optional[Dict[str, Any]]:
    if not push_name:
        return None
    pn_clean = push_name.strip().lower()
    for c in _load_contacts_from_file():
        if c.get("name", "").strip().lower() == pn_clean or c.get("nickname", "").strip().lower() == pn_clean:
            return c
        aliases = [a.lower() for a in c.get("aliases", [])]
        if pn_clean in aliases:
            return c
    return None


def get_display_name(identifier: str) -> str:
    name = find_name_by_phone(identifier)
    if name:
        return name
    c = find_contact_by_push_name_sync(identifier)
    if c:
        return c.get("nickname") or c.get("name")
    return identifier


def get_full_name(identifier: str) -> str:
    name = find_name_by_phone(identifier)
    if name:
        return name
    c = find_contact_by_push_name_sync(identifier)
    if c:
        return c.get("name")
    return identifier


async def add_or_update_contact(
    name: Optional[str],
    phone: str,
    role: Optional[str] = None,
    division: Optional[str] = None,
    nickname: Optional[str] = None,
    telegram: Optional[str] = None
) -> Dict[str, Any]:
    norm_phone = normalize_phone(phone)
    t = telegram.strip().lstrip("@").lower() if telegram else None
    nick = nickname if (nickname is not None and nickname != "") else name

    # 1. Update/insert in DB if connected
    try:
        from app.services.database import get_db_pool
        pool = await get_db_pool()
        if pool:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    INSERT INTO contacts (name, nickname, phone, telegram, division, role, aliases)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT (phone) DO UPDATE SET
                        name = COALESCE($1, contacts.name),
                        nickname = COALESCE($2, contacts.nickname),
                        telegram = $4,
                        division = COALESCE($5, contacts.division),
                        role = COALESCE($6, contacts.role),
                        updated_at = CURRENT_TIMESTAMP
                    RETURNING id, name, nickname, phone, telegram, division, role, aliases
                    """,
                    name or norm_phone, nick, norm_phone, t, division, role, [nick.lower()] if nick else []
                )
                res = dict(row)
                # Keep file in sync as backup
                _sync_contact_to_file(res)
                from app.services.identity import clear_identity_cache
                clear_identity_cache()
                return res
    except Exception as e:
        logger.warning(f"DB add_or_update_contact error: {e}")

    # Fallback to file-based
    res = _add_or_update_contact_file(name, norm_phone, role, division, nickname, telegram)
    return res


def _sync_contact_to_file(c_dict: Dict[str, Any]):
    try:
        contacts = _load_contacts_from_file()
        norm_phone = c_dict.get("phone")
        updated = False
        for idx, c in enumerate(contacts):
            if normalize_phone(c.get("phone", "")) == norm_phone:
                contacts[idx].update(c_dict)
                updated = True
                break
        if not updated:
            contacts.append(c_dict)
        _save_contacts_to_file(contacts)
    except Exception:
        pass


def _add_or_update_contact_file(name: Optional[str], phone: str, role: Optional[str] = None, division: Optional[str] = None, nickname: Optional[str] = None, telegram: Optional[str] = None) -> Dict[str, Any]:
    contacts = _load_contacts_from_file()
    norm_phone = normalize_phone(phone)
    updated = False
    clear_telegram = False
    new_contact = {"phone": norm_phone}
    if name:
        new_contact["name"] = name
    if role:
        new_contact["role"] = role
    if division:
        new_contact["division"] = division
    if nickname is not None and nickname != "":
        new_contact["nickname"] = nickname
    if telegram is not None:
        t = telegram.strip().lstrip("@").lower()
        if t:
            new_contact["telegram"] = t
        else:
            clear_telegram = True

    for idx, c in enumerate(contacts):
        if normalize_phone(c.get("phone", "")) == norm_phone:
            if clear_telegram:
                c.pop("telegram", None)
            contacts[idx].update(new_contact)
            updated = True
            new_contact = contacts[idx]
            break

    if not updated:
        contacts.append(new_contact)

    _save_contacts_to_file(contacts)
    return new_contact


async def delete_contact(phone: str) -> bool:
    norm_phone = normalize_phone(phone)
    try:
        from app.services.database import get_db_pool
        pool = await get_db_pool()
        if pool:
            async with pool.acquire() as conn:
                res = await conn.execute("DELETE FROM contacts WHERE phone = $1", norm_phone)
                # res is like 'DELETE 1'
                deleted = res.endswith("1")
                if deleted:
                    _delete_contact_file(norm_phone)
                    from app.services.identity import clear_identity_cache
                    clear_identity_cache()
                    return True
    except Exception as e:
        logger.warning(f"DB delete_contact error: {e}")

    return _delete_contact_file(norm_phone)


def _delete_contact_file(phone: str) -> bool:
    contacts = _load_contacts_from_file()
    norm_phone = normalize_phone(phone)
    initial_len = len(contacts)
    filtered = [c for c in contacts if normalize_phone(c.get("phone", "")) != norm_phone]
    if len(filtered) < initial_len:
        _save_contacts_to_file(filtered)
        return True
    return False
