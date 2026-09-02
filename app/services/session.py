import json
from typing import Dict, Any, List, Optional
import redis.asyncio as redis
from pydantic import BaseModel, Field
from app.config import settings


class SessionData(BaseModel):
    phone: str
    messages: List[Dict[str, str]] = Field(default_factory=list)
    last_activity: float = 0.0
    pending_ticket: Optional[Dict[str, Any]] = None


class SessionManager:
    def __init__(self, redis_url: Optional[str] = None):
        self.url = redis_url or settings.redis_url
        self._redis: Optional[redis.Redis] = None

    async def get_redis(self) -> redis.Redis:
        if self._redis is None:
            self._redis = redis.from_url(self.url, decode_responses=True)
        return self._redis

    async def close(self):
        if self._redis:
            await self._redis.aclose()
            self._redis = None

    def _key(self, phone: str) -> str:
        return f"session:{phone}"

    async def get_session(self, phone: str) -> Optional[SessionData]:
        r = await self.get_redis()
        raw = await r.get(self._key(phone))
        if not raw:
            return None
        try:
            data = json.loads(raw)
            return SessionData(**data)
        except Exception:
            return None

    async def save_session(self, session: SessionData, ttl_seconds: int = 1800):
        r = await self.get_redis()
        key = self._key(session.phone)
        raw = session.model_dump_json()
        await r.set(key, raw, ex=ttl_seconds)

    async def get_or_create_session(self, phone: str) -> SessionData:
        s = await self.get_session(phone)
        if not s:
            import time
            s = SessionData(phone=phone, last_activity=time.time())
            await self.save_session(s)
        return s

    async def save_user_message(self, phone: str, text: str):
        import time
        s = await self.get_or_create_session(phone)
        s.messages.append({"role": "user", "content": text})
        if len(s.messages) > 10:
            s.messages = s.messages[-10:]
        s.last_activity = time.time()
        await self.save_session(s)

    async def save_assistant_response(self, phone: str, text: str):
        import time
        s = await self.get_or_create_session(phone)
        s.messages.append({"role": "assistant", "content": text})
        if len(s.messages) > 10:
            s.messages = s.messages[-10:]
        s.last_activity = time.time()
        await self.save_session(s)

    async def clear_session(self, phone: str):
        r = await self.get_redis()
        await r.delete(self._key(phone))

    AI_CONFIG_KEY = "sga:ai:config"

    async def get_ai_config(self) -> Dict[str, Any]:
        default = {
            "anthropic_base_url": settings.anthropic_base_url,
            "anthropic_api_key": settings.anthropic_api_key,
            "ai_model": settings.ai_model,
        }
        try:
            r = await self.get_redis()
            raw = await r.get(self.AI_CONFIG_KEY)
            if not raw:
                return default
            return {**default, **json.loads(raw)}
        except Exception:
            return default

    async def update_ai_config(self, **updates) -> Dict[str, Any]:
        cfg = await self.get_ai_config()
        for k, v in updates.items():
            if v is not None:
                cfg[k] = v
        r = await self.get_redis()
        await r.set(self.AI_CONFIG_KEY, json.dumps(cfg))
        return cfg


session_manager = SessionManager()
