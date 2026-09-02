import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.platform_config import PlatformConfig, save_platform_config, load_platform_config, get_platform_token

@pytest.mark.asyncio
async def test_platform_config_db_flow():
    mock_conn = AsyncMock()
    mock_conn.fetchrow.return_value = None
    
    mock_pool = MagicMock()
    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = mock_conn
    mock_pool.acquire.return_value = mock_cm

    with patch("app.services.database.get_db_pool", return_value=mock_pool), \
         patch("app.services.session.session_manager.get_redis") as mock_redis:

        redis_mock = AsyncMock()
        redis_mock.get.return_value = None
        mock_redis.return_value = redis_mock

        # Test initial empty load
        cfg = await load_platform_config("telegram")
        assert cfg is None

        # Test saving config
        new_cfg = PlatformConfig(enabled=True, bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11")
        await save_platform_config("telegram", new_cfg)
        assert mock_conn.execute.called

        # Mock fetchrow returning saved record
        mock_conn.fetchrow.return_value = {
            "enabled": True,
            "bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            "config_data": "{}"
        }

        loaded_cfg = await load_platform_config("telegram")
        assert loaded_cfg is not None
        assert loaded_cfg.enabled is True
        assert loaded_cfg.bot_token == "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"

        token = await get_platform_token("telegram")
        assert token == "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
