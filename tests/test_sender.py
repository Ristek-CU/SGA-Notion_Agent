import pytest
from app.wa.sender import lookup_lid_cache, set_lid_cache


def test_lid_cache_operations():
    set_lid_cache("123456@lid", "628123456789")
    assert lookup_lid_cache("123456@lid") == "628123456789"
