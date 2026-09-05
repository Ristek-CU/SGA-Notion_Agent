import pytest
from app.wa.sender import lookup_lid_cache, set_lid_cache, resolve_contact_phone_from_waha


def test_lid_cache_operations():
    set_lid_cache("123456@lid", "628123456789")
    assert lookup_lid_cache("123456@lid") == "628123456789"


@pytest.mark.asyncio
async def test_resolve_contact_phone_from_waha(monkeypatch):
    class DummyResponse:
        status_code = 200
        def json(self):
            return {"id": "6288289048433@c.us", "number": "41721513664717"}

    class DummyClient:
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
        async def get(self, url, headers=None):
            return DummyResponse()

    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: DummyClient())

    phone = await resolve_contact_phone_from_waha("41721513664717@lid")
    assert phone == "6288289048433"

