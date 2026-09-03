import pytest
import json

class DummyRedis:
    def __init__(self):
        self.store = {}

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value):
        self.store[key] = value


class DummyConnection:
    def __init__(self, db_store):
        self.db_store = db_store

    async def fetchrow(self, query, key):
        if key in self.db_store:
            return {"config": self.db_store[key]}
        return None

    async def execute(self, query, key, config_json):
        self.db_store[key] = config_json


class DummyAcquireContext:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


class DummyPool:
    def __init__(self, db_store):
        self.db_store = db_store

    def acquire(self):
        return DummyAcquireContext(DummyConnection(self.db_store))


@pytest.mark.asyncio
async def test_platform_config_db_flow(monkeypatch):
    dummy_redis = DummyRedis()
    db_store = {}
    dummy_pool = DummyPool(db_store)

    from app.services.session import session_manager
    async def fake_get_redis():
        return dummy_redis
    monkeypatch.setattr(session_manager, "get_redis", fake_get_redis)

    import app.services.platform_config as pc_mod
    async def fake_get_db_pool():
        return dummy_pool
    monkeypatch.setattr(pc_mod, "get_db_pool", fake_get_db_pool)

    # 1. Initially load non-existent config
    cfg = await pc_mod.load_platform_config("telegram")
    assert cfg is None

    # 2. Save config
    new_cfg = pc_mod.PlatformConfig(enabled=True, bot_token="1234567890:ABCdefGHIjklMNOpqrsTUVwxyz")
    await pc_mod.save_platform_config("telegram", new_cfg)

    # Verify written to DB store and Redis
    assert "telegram" in db_store
    assert pc_mod._key("telegram") in dummy_redis.store

    # 3. Load config from Redis cache
    loaded_cache = await pc_mod.load_platform_config("telegram")
    assert loaded_cache is not None
    assert loaded_cache.enabled is True
    assert loaded_cache.bot_token == "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz"

    # 4. Simulate Redis cache eviction / miss
    dummy_redis.store.clear()

    # Load config (should miss Redis, hit DB, and repopulate Redis)
    loaded_db = await pc_mod.load_platform_config("telegram")
    assert loaded_db is not None
    assert loaded_db.enabled is True
    assert loaded_db.bot_token == "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz"
    assert pc_mod._key("telegram") in dummy_redis.store

    # 5. Check get_platform_token
    token = await pc_mod.get_platform_token("telegram")
    assert token == "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz"
