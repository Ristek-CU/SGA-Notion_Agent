import pytest
from unittest.mock import AsyncMock

class InMemoryRedis:
    def __init__(self):
        self.store = {}
        self.ttls = {}

    async def get(self, k):
        return self.store.get(k)

    async def set(self, k, v, ex=None, nx=False):
        if nx and k in self.store:
            return False
        self.store[k] = v
        if ex:
            self.ttls[k] = ex
        return True

    async def delete(self, k):
        self.store.pop(k, None)
        self.ttls.pop(k, None)

    async def ttl(self, k):
        return self.ttls.get(k, 300)


global_fake_redis = InMemoryRedis()


@pytest.fixture(autouse=True)
def mock_redis_global(monkeypatch):
    from app.services.session import session_manager
    global_fake_redis.store.clear()
    global_fake_redis.ttls.clear()
    session_manager._fake_redis = global_fake_redis
    monkeypatch.setattr(session_manager, "get_redis", AsyncMock(return_value=global_fake_redis))
    yield global_fake_redis
