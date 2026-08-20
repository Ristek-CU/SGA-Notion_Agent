from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.config import settings
from app.webhook.handler import router as webhook_router
from app.admin.api import admin_router
from app.notion.core import NotionClient
from app.services.session import session_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup tasks
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
app.include_router(admin_router)


@app.get("/health")
def health_check():
    return {"status": "ok", "environment": settings.node_env}


@app.get("/")
def root():
    return {"name": "Notion Agent SGA Backend", "status": "running"}
