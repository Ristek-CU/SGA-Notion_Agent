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
    # Setup WAHA Webhook URL secara otomatis saat startup
    try:
        import httpx
        waha_url = settings.waha_api_url.rstrip("/")
        headers = {"X-Api-Key": settings.waha_api_key, "Content-Type": "application/json"}
        target_webhook = f"{settings.backend_public_url.rstrip('/')}/webhook/{settings.waha_instance_name}"
        payload = {
            "config": {
                "webhooks": [
                    {
                        "url": target_webhook,
                        "events": ["message", "message.any"]
                    }
                ]
            }
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.patch(f"{waha_url}/api/sessions/{settings.waha_instance_name}", headers=headers, json=payload)
    except Exception:
        pass
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
