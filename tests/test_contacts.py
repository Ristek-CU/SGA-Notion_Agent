import pytest
from app.services.contacts import (
    normalize_phone,
    find_contact_by_push_name,
    find_contact_by_push_name_sync,
    find_phone_by_name,
    find_name_by_phone,
    get_display_name,
    get_full_name,
)


def test_normalize_phone():
    assert normalize_phone("08123456789") == "628123456789"
    assert normalize_phone("+628123456789") == "628123456789"
    assert normalize_phone("628123456789") == "628123456789"


@pytest.mark.asyncio
async def test_contact_lookups():
    # Contacts loaded from config/contacts.json
    assert find_phone_by_name("salman") == "6285175019086"
    assert find_name_by_phone("085175019086") == "Muhammad Salman Firdaus"
    assert get_display_name("6288211416866") == "Aldridge Mika Gunawan"
    c = await find_contact_by_push_name("salman")
    assert c is not None
    assert c["name"] == "Muhammad Salman Firdaus"
