import json
import logging
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from app.services.session import session_manager
from app.services.database import get_db_pool

logger = logging.getLogger(__name__)


class PlatformConfig(BaseModel):
    enabled: bool = False
    bot_token: str = ""
    config_data: Dict[str, Any] = Field(default_factory=dict)


def _key(name: str) -> str:
    return f"sga:platform:{name}"


async def load_platform_config(name: str) -> Optional[PlatformConfig]:
    # 1. Try Redis Cache
    try:
        r = await session_manager.get_redis()
        raw = await r.get(_key(name))
        if raw:
            return PlatformConfig(**json.loads(raw))
    except Exception as e:
        logger.warning(f"Failed to read platform config '{name}' from Redis: {e}")

    # 2. Try DB (Single Source of Truth)
    try:
        pool = await get_db_pool()
        if pool:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT config FROM platform_configs WHERE key = $1", name
                )
                if row and row["config"]:
                    raw_cfg = row["config"]
                    if isinstance(raw_cfg, str):
                        data = json.loads(raw_cfg)
                    else:
                        data = dict(raw_cfg)
                    cfg = PlatformConfig(**data)
                    
                    # Update Redis cache
                    try:
                        r = await session_manager.get_redis()
                        await r.set(_key(name), cfg.model_dump_json())
                    except Exception as cache_err:
                        logger.warning(f"Failed to set Redis cache for platform config '{name}': {cache_err}")
                    
                    return cfg
    except Exception as e:
        logger.error(f"Failed to read platform config '{name}' from DB: {e}")

    return None


async def save_platform_config(name: str, cfg: PlatformConfig) -> None:
    cfg_json = cfg.model_dump_json()

    # 1. Write to PostgreSQL (Single Source of Truth)
    try:
        pool = await get_db_pool()
        if pool:
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO platform_configs (key, config, updated_at)
                    VALUES ($1, $2::jsonb, CURRENT_TIMESTAMP)
                    ON CONFLICT (key) DO UPDATE SET
                        config = EXCLUDED.config,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    name,
                    cfg_json,
                )
    except Exception as e:
        logger.error(f"Error saving platform config to DB for {name}: {e}")

    # 2. Write to Redis (Cache)
    try:
        r = await session_manager.get_redis()
        await r.set(_key(name), cfg_json)
    except Exception as e:
        logger.warning(f"Failed to save platform config '{name}' to Redis cache: {e}")


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
