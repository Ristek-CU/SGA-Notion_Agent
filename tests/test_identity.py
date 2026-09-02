import pytest
from app.services.identity import resolve_identity


def test_resolve_identity_known():
    res = resolve_identity("6285175019086", push_name="Salman")
    assert res["is_known"] is True
    assert res["name"] == "Muhammad Salman Firdaus"
    assert res["division"] == "Research and Technology"


def test_resolve_identity_unknown():
    res = resolve_identity("628999999999", push_name="Stranger")
    assert res["is_known"] is False
    assert res["name"] == "Stranger"
    assert res["phone"] == "628999999999"
