import asyncio
import os
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.config import settings
from app.webhook.handler import router as webhook_router
from app.telegram.bot import router as telegram_router
from app.admin.api import admin_router
from app.notion.core import NotionClient
from app.services.session import session_manager

_sync_task: asyncio.Task | None = None


async def periodic_member_sync():
    """Background task untuk auto-sync berkala Notion Members DB ke PostgreSQL contacts setiap 15 menit."""
    # Delay sebentar saat pertama kali boot agar DB pool & startup selesai
    await asyncio.sleep(5)
    while True:
        try:
            from app.services.notion_sync import sync_notion_members_to_contacts
            print("[AUTO-SYNC] Running periodic Notion members sync...")
            res = await sync_notion_members_to_contacts()
            print(f"[AUTO-SYNC RESULT] success={res.get('success')} inserted={res.get('inserted')} updated={res.get('updated')}")
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[AUTO-SYNC ERROR] {e}")
        
        # Sleep 15 menit (900 detik)
        await asyncio.sleep(900)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _sync_task
    # Initialize DB pool and schema at startup
    try:
        from app.services.database import get_db_pool
        await get_db_pool()
    except Exception as e:
        print(f"[STARTUP DB INIT ERROR] {e}")

    # Jalankan initial sync Notion Members di background task saat startup
    _sync_task = asyncio.create_task(periodic_member_sync())

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
    if _sync_task and not _sync_task.done():
        _sync_task.cancel()
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

# Mount uploads directory for static file access (broadcast attachments, etc.)
upload_dir = Path("/app/uploads") if os.path.exists("/app") else Path("uploads")
upload_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(upload_dir)), name="uploads")


@app.get("/health")
def health_check():
    return {"status": "ok", "environment": settings.node_env}


@app.get("/")
def root():
    return {"name": "Notion Agent SGA Backend", "status": "running"}
