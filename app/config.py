from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    node_env: str = "development"
    port: int = 3000
    anthropic_api_key: str = "dummy_key"
    anthropic_base_url: str = "https://api.z.ai/api/anthropic"
    ai_model: str = "claude-sonnet-4-20250514"
    notion_api_key: str = "dummy_key"
    notion_database_id: str = "dummy_db_id"
    notion_master_backlog_id: Optional[str] = None
    notion_master_projects_id: Optional[str] = None
    notion_divisions_id: Optional[str] = None
    notion_members_id: Optional[str] = None
    notion_version: str = "2022-06-28"
    waha_api_url: str = "http://orc-waha-0qmqey:3000"
    waha_api_key: str = "waha-notion-agent-2026"
    waha_instance_name: str = "wa-bot"
    redis_url: str = "redis://orc-redis-hk08zj:6379"
    database_url: str = "postgresql://postgre:***@sganotionagent-postgres-1hklkb:5432/SGA-Notion_Agent"
    lid_phone_map: str = "62397553336471@lid=6285175019086,62397553336471=6285175019086"
    cache_ttl_backlog_ms: int = 120_000
    cache_ttl_projects_ms: int = 300_000
    cache_ttl_members_ms: int = 600_000
    cache_ttl_relations_ms: int = 600_000
    notion_rate_limit_rps: int = 3
    notion_max_retries: int = 3
    admin_user: str = "admin"
    admin_password: str = "admin123"
    jwt_secret: str = "supersecretjwtkey"
    backend_public_url: str = "https://notion-api.sudobrew.dev"
    waha_webhook_url: Optional[str] = "http://sga-notion-agent-selrus:3000/webhook/wa-bot"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


settings = Settings()
