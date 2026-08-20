import pytest
from app.services.contacts import (
    normalize_phone,
    find_contact_by_push_name,
    find_phone_by_name,
    find_name_by_phone,
    get_display_name,
    get_full_name,
)


def test_normalize_phone():
    assert normalize_phone("08123456789") == "628123456789"
    assert normalize_phone("+628123456789") == "628123456789"
    assert normalize_phone("628123456789") == "628123456789"


def test_contact_lookups():
    # Contacts loaded from config/contacts.json
    assert find_phone_by_name("salman") == "628123456789"
    assert find_name_by_phone("08123456789") == "Salman"
    assert get_display_name("628987654321") == "Budi Santoso"
    c = find_contact_by_push_name("sam")
    assert c is not None
    assert c["name"] == "Salman"
