from fastapi import APIRouter
from app.admin.auth import router as auth_router
from app.admin.wa import router as wa_router
from app.admin.notion import router as notion_router
from app.admin.notify import router as notify_router
from app.admin.platforms import router as platforms_router

admin_router = APIRouter(prefix="/admin")

admin_router.include_router(auth_router)
admin_router.include_router(wa_router)
admin_router.include_router(notion_router)
admin_router.include_router(notify_router)
admin_router.include_router(platforms_router)
