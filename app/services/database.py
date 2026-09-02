import os
import json
import logging
from typing import Optional, List, Dict, Any
import asyncpg
from app.config import settings

logger = logging.getLogger(__name__)

_pool: Optional[asyncpg.Pool] = None


async def get_db_pool() -> Optional[asyncpg.Pool]:
    global _pool
    if _pool is None:
        try:
            db_url = settings.database_url
            # Fix URL format if needed
            if db_url.startswith("postgres://"):
                db_url = db_url.replace("postgres://", "postgresql://", 1)
            
            _pool = await asyncpg.create_pool(
                dsn=db_url,
                min_size=1,
                max_size=10,
                command_timeout=15,
            )
            await init_db_schema()
        except Exception as e:
            logger.warning(f"Could not connect to PostgreSQL ({e}), operating in fallback mode")
            return None
    return _pool


async def init_db_schema():
    global _pool
    if not _pool:
        return
    
    schema_sql = """
    CREATE TABLE IF NOT EXISTS contacts (
        id SERIAL PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        nickname VARCHAR(100),
        phone VARCHAR(50) UNIQUE NOT NULL,
        telegram VARCHAR(100),
        division VARCHAR(100),
        role VARCHAR(100),
        aliases TEXT[] DEFAULT '{}',
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_contacts_phone ON contacts (phone);
    CREATE INDEX IF NOT EXISTS idx_contacts_telegram ON contacts (telegram);
    """
    async with _pool.acquire() as conn:
        await conn.execute(schema_sql)
        
        # Check if table is empty to auto-seed from config/contacts.json
        count = await conn.fetchval("SELECT COUNT(*) FROM contacts")
        if count == 0:
            await seed_initial_contacts(conn)


async def seed_initial_contacts(conn: asyncpg.Connection):
    from app.services.contacts import get_contacts_file_path
    path = get_contacts_file_path()
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            contacts = json.load(f)
        for c in contacts:
            name = c.get("name")
            phone = c.get("phone")
            if not name or not phone:
                continue
            nickname = c.get("nickname") or name
            telegram = c.get("telegram")
            division = c.get("division")
            role = c.get("role")
            aliases = c.get("aliases") or []
            
            await conn.execute(
                """
                INSERT INTO contacts (name, nickname, phone, telegram, division, role, aliases)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (phone) DO UPDATE SET
                    name = EXCLUDED.name,
                    nickname = EXCLUDED.nickname,
                    telegram = EXCLUDED.telegram,
                    division = EXCLUDED.division,
                    role = EXCLUDED.role,
                    aliases = EXCLUDED.aliases,
                    updated_at = CURRENT_TIMESTAMP
                """,
                name, nickname, phone, telegram, division, role, aliases
            )
        logger.info(f"Seeded {len(contacts)} contacts into PostgreSQL")
    except Exception as e:
        logger.error(f"Failed seeding initial contacts: {e}")
