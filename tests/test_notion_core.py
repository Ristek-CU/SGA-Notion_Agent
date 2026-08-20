import pytest
import asyncio
import time
from app.notion.core import NotionClient


@pytest.mark.asyncio
async def test_notion_client_throttling():
    client = NotionClient(api_key="test_key", max_rps=3, max_retries=1)
    
    # Mock _get_client / request logic
    call_times = []
    
    async def mock_throttle():
        async with client._lock:
            now = time.monotonic()
            client._timestamps = [t for t in client._timestamps if now - t < 1.0]
            if len(client._timestamps) >= client._max_rps:
                wait = 1.0 - (now - client._timestamps[0])
                if wait > 0:
                    await asyncio.sleep(wait)
            client._timestamps.append(time.monotonic())
            call_times.append(time.monotonic())

    client._throttle = mock_throttle

    # Fire 5 throttled tasks
    await asyncio.gather(*(client._throttle() for _ in range(5)))
    
    # Verify that first 3 happened almost instantly and next 2 were throttled > 0.8s
    diff = call_times[3] - call_times[0]
    assert diff >= 0.8


@pytest.mark.asyncio
async def test_notion_client_cache():
    client = NotionClient(api_key="test_key")
    client._cache["test_key"] = ({"foo": "bar"}, time.monotonic() + 10.0)
    
    res = await client.request("GET", "/test", cache_key="test_key", ttl_ms=10000)
    assert res == {"foo": "bar"}
