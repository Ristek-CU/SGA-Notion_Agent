import os
import json
import re
from typing import Optional, Dict, Any, List
from app.config import settings

def get_contacts_file_path() -> str:
    # Look for config/contacts.json relative to workspace root or current dir
    base_dir = os.getcwd()
    path = os.path.join(base_dir, "config", "contacts.json")
    if not os.path.exists(path):
        # Fallback relative to this file
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config", "contacts.json")
    return path

_contacts_cache: Optional[List[Dict[str, Any]]] = None
_last_mtime: float = 0.0


def normalize_phone(phone: str) -> str:
    cleaned = re.sub(r"\D", "", phone)
    if cleaned.startswith("0"):
        cleaned = "62" + cleaned[1:]
    elif not cleaned.startswith("62") and cleaned:
        cleaned = "62" + cleaned
    return cleaned


def load_contacts() -> List[Dict[str, Any]]:
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


def save_contacts(contacts: List[Dict[str, Any]]):
    global _contacts_cache, _last_mtime
    file_path = get_contacts_file_path()
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    temp_path = f"{file_path}.tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(contacts, f, indent=2, ensure_ascii=False)
    os.replace(temp_path, file_path)
    _contacts_cache = contacts
    _last_mtime = os.path.getmtime(file_path)


def get_all_contacts() -> List[Dict[str, Any]]:
    return load_contacts()


def find_contact_by_push_name(push_name: str) -> Optional[Dict[str, Any]]:
    if not push_name:
        return None
    contacts = load_contacts()
    pn_clean = push_name.strip().lower()
    for c in contacts:
        if c.get("name", "").strip().lower() == pn_clean or c.get("nickname", "").strip().lower() == pn_clean:
            return c
        aliases = [a.lower() for a in c.get("aliases", [])]
        if pn_clean in aliases:
            return c
    return None


def find_phone_by_name(name_query: str) -> Optional[str]:
    if not name_query:
        return None
    contacts = load_contacts()
    q = name_query.strip().lower()
    for c in contacts:
        if c.get("name", "").strip().lower() == q or c.get("nickname", "").strip().lower() == q:
            return c.get("phone")
        aliases = [a.lower() for a in c.get("aliases", [])]
        if q in aliases:
            return c.get("phone")
    return None


def find_name_by_phone(phone: str) -> Optional[str]:
    if not phone:
        return None
    norm = normalize_phone(phone)
    contacts = load_contacts()
    for c in contacts:
        if normalize_phone(c.get("phone", "")) == norm:
            return c.get("name")
    return None


def get_display_name(identifier: str) -> str:
    name = find_name_by_phone(identifier)
    if name:
        return name
    c = find_contact_by_push_name(identifier)
    if c:
        return c.get("nickname") or c.get("name")
    return identifier


def get_full_name(identifier: str) -> str:
    name = find_name_by_phone(identifier)
    if name:
        return name
    c = find_contact_by_push_name(identifier)
    if c:
        return c.get("name")
    return identifier


def add_or_update_contact(name: str, phone: str, role: Optional[str] = None, division: Optional[str] = None, nickname: Optional[str] = None, telegram: Optional[str] = None) -> Dict[str, Any]:
    contacts = load_contacts()
    norm_phone = normalize_phone(phone)
    updated = False
    new_contact = {"name": name, "phone": norm_phone}
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
            new_contact.pop("telegram", None)

    for idx, c in enumerate(contacts):
        if normalize_phone(c.get("phone", "")) == norm_phone:
            contacts[idx].update(new_contact)
            updated = True
            new_contact = contacts[idx]
            break

    if not updated:
        contacts.append(new_contact)

    save_contacts(contacts)
    return new_contact


def delete_contact(phone: str) -> bool:
    contacts = load_contacts()
    norm_phone = normalize_phone(phone)
    initial_len = len(contacts)
    filtered = [c for c in contacts if normalize_phone(c.get("phone", "")) != norm_phone]
    if len(filtered) < initial_len:
        save_contacts(filtered)
        return True
    return False
