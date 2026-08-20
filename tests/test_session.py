import pytest
from app.services.session import SessionManager, SessionData


@pytest.mark.asyncio
async def test_session_in_memory_fallback():
    # Test session data structure
    s = SessionData(phone="628123456789")
    assert s.phone == "628123456789"
    assert len(s.messages) == 0
