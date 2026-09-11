import pytest
import asyncio
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


def test_normalize_whatsapp_markdown():
    from app.wa.sender import normalize_whatsapp_markdown
    assert normalize_whatsapp_markdown("Halo **Kak Salman**!") == "Halo *Kak Salman*!"
    assert normalize_whatsapp_markdown("Tiket: ***Testing Roro***") == "Tiket: *_Testing Roro_*"
    assert normalize_whatsapp_markdown("Normal *bold* dan _italic_") == "Normal *bold* dan _italic_"
    assert normalize_whatsapp_markdown("") == ""


@pytest.mark.asyncio
async def test_sender_circuit_breaker_422_failure(monkeypatch):
    from app.wa.sender import send_whatsapp_message, WAHASessionNotWorkingError

    class DummyResponse422:
        status_code = 422
        text = "Session not working"

    class DummyClient:
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
        async def post(self, url, json=None, headers=None):
            return DummyResponse422()

    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: DummyClient())
    monkeypatch.setattr("app.wa.sender.wait_for_session_recovery", lambda *args, **kwargs: asyncio.sleep(0, result=False))

    with pytest.raises(WAHASessionNotWorkingError):
        await send_whatsapp_message("628123456789", "Halo test circuit breaker")


@pytest.mark.asyncio
async def test_sender_circuit_breaker_422_recovery(monkeypatch):
    from app.wa.sender import send_whatsapp_message

    call_count = 0
    class DummyResponse422:
        status_code = 422
        text = "Session not ready"
    class DummyResponse200:
        status_code = 200
        def json(self):
            return {"id": "msg_123", "status": "sent"}

    class DummyClient:
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
        async def post(self, url, json=None, headers=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return DummyResponse422()
            return DummyResponse200()

    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", lambda *args, **kwargs: DummyClient())
    monkeypatch.setattr("app.wa.sender.wait_for_session_recovery", lambda *args, **kwargs: asyncio.sleep(0, result=True))

    res = await send_whatsapp_message("628123456789", "Halo test recovery")
    assert res["id"] == "msg_123"
    assert call_count == 2



