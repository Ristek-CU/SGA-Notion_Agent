import json
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from app.services.session import session_manager


class PlatformConfig(BaseModel):
    enabled: bool = False
    bot_token: str = ""


def _key(name: str) -> str:
    return f"sga:platform:{name}"


async def load_platform_config(name: str) -> Optional[PlatformConfig]:
    r = await session_manager.get_redis()
    raw = await r.get(_key(name))
    if not raw:
        return None
    try:
        return PlatformConfig(**json.loads(raw))
    except Exception:
        return None


async def save_platform_config(name: str, cfg: PlatformConfig) -> None:
    r = await session_manager.get_redis()
    await r.set(_key(name), cfg.model_dump_json())

async def get_platform_token(name: str) -> Optional[str]:
    """Token aktif hanya jika platform enabled; None kalau tidak."""
    cfg = await load_platform_config(name)
    if not cfg or not cfg.enabled or not cfg.bot_token:
        return None
    return cfg.bot_token


def mask_token(token: str) -> str:
    if not token:
        return ""
    if len(token) <= 10:
        return "***"
    return f"{token[:6]}...{token[-4:]}"


__all__ = [
    "PlatformConfig",
    "load_platform_config",
    "save_platform_config",
    "get_platform_token",
    "mask_token",
]
