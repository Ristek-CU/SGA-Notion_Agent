import json
import logging
from typing import Optional
from pydantic import BaseModel
from app.services.session import session_manager

logger = logging.getLogger(__name__)


class PlatformConfig(BaseModel):
    enabled: bool = False
    bot_token: str = ""
    config_data: dict = {}


def _key(name: str) -> str:
    return f"sga:platform:{name}"


async def load_platform_config(name: str) -> Optional[PlatformConfig]:
    # 1. Coba load dari PostgreSQL
    try:
        from app.services.database import get_db_pool
        pool = await get_db_pool()
        if pool:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT enabled, bot_token, config_data FROM platform_configs WHERE name = $1",
                    name,
                )
                if row:
                    cfg_dict = dict(row)
                    cfg_data = cfg_dict.get("config_data")
                    if isinstance(cfg_data, str):
                        try:
                            cfg_data = json.loads(cfg_data)
                        except Exception:
                            cfg_data = {}
                    elif not cfg_data:
                        cfg_data = {}
                    cfg = PlatformConfig(
                        enabled=row["enabled"],
                        bot_token=row["bot_token"] or "",
                        config_data=cfg_data,
                    )
                    # Cache / sync ke Redis
                    try:
                        r = await session_manager.get_redis()
                        await r.set(_key(name), cfg.model_dump_json())
                    except Exception:
                        pass
                    return cfg
    except Exception as e:
        logger.warning(f"Error loading platform config from DB for {name}: {e}")

    # 2. Fallback ke Redis
    try:
        r = await session_manager.get_redis()
        raw = await r.get(_key(name))
        if raw:
            return PlatformConfig(**json.loads(raw))
    except Exception as e:
        logger.warning(f"Error loading platform config from Redis for {name}: {e}")

    return None


async def save_platform_config(name: str, cfg: PlatformConfig) -> None:
    # 1. Simpan ke PostgreSQL (persisten permanen)
    try:
        from app.services.database import get_db_pool
        pool = await get_db_pool()
        if pool:
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO platform_configs (name, enabled, bot_token, config_data, updated_at)
                    VALUES ($1, $2, $3, $4, CURRENT_TIMESTAMP)
                    ON CONFLICT (name) DO UPDATE SET
                        enabled = EXCLUDED.enabled,
                        bot_token = EXCLUDED.bot_token,
                        config_data = EXCLUDED.config_data,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    name,
                    cfg.enabled,
                    cfg.bot_token,
                    json.dumps(cfg.config_data),
                )
    except Exception as e:
        logger.error(f"Error saving platform config to DB for {name}: {e}")

    # 2. Simpan / invalidate di Redis
    try:
        r = await session_manager.get_redis()
        await r.set(_key(name), cfg.model_dump_json())
    except Exception as e:
        logger.warning(f"Error saving platform config to Redis for {name}: {e}")


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
