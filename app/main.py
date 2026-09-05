from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.config import settings
from app.webhook.handler import router as webhook_router
from app.telegram.bot import router as telegram_router
from app.admin.api import admin_router
from app.notion.core import NotionClient
from app.services.session import session_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB pool and schema at startup
    try:
        from app.services.database import get_db_pool
        await get_db_pool()
    except Exception as e:
        print(f"[STARTUP DB INIT ERROR] {e}")

    # Start dual priority queue manager
    from app.services.queue import queue_manager
    queue_manager.start()

    # Setup WAHA Webhook URL secara otomatis saat startup
    try:
        import httpx
        waha_url = settings.waha_api_url.rstrip("/")
        headers = {"X-Api-Key": settings.waha_api_key, "Content-Type": "application/json"}
        target_webhook = settings.waha_webhook_url or f"{settings.backend_public_url.rstrip('/')}/webhook/{settings.waha_instance_name}"
        payload = {
            "name": settings.waha_instance_name,
            "config": {
                "webhooks": [
                    {
                        "url": target_webhook,
                        "events": ["message"]
                    }
                ]
            }
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.put(f"{waha_url}/api/sessions/{settings.waha_instance_name}", headers=headers, json=payload)
            print(f"[STARTUP WAHA PUT] target={target_webhook} status={resp.status_code} body={resp.text[:200]}")
    except Exception as e:
        print(f"[STARTUP WAHA PUT ERROR] {e}")
    yield
    # Cleanup tasks
    await session_manager.close()


app = FastAPI(
    title="Notion Agent SGA API",
    version="0.1.0",
    lifespan=lifespan,
)

# Include Routers
app.include_router(webhook_router)
app.include_router(telegram_router)
app.include_router(admin_router)


@app.get("/health")
def health_check():
    return {"status": "ok", "environment": settings.node_env}


@app.get("/")
def root():
    return {"name": "Notion Agent SGA Backend", "status": "running"}
