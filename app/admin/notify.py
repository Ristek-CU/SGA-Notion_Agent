import os
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.admin.auth import verify_token
from app.services.session import session_manager
from app.services.notify import notify_pic
from app.wa.sender import send_direct_message
from app.config import settings

router = APIRouter(tags=["Admin Notify & System"])


class BroadcastRequest(BaseModel):
    message: str
    recipients: List[str]  # phone numbers or contact names


class GuardConfigUpdate(BaseModel):
    enabled: Optional[bool] = None
    strict_mode: Optional[bool] = None


# Dynamic runtime state for Guard toggle/config
guard_runtime_state = {
    "enabled": True,
    "strict_mode": True,
}

audit_logs_storage: List[Dict[str, Any]] = []


def record_audit_log(user: str, action: str, details: Dict[str, Any]):
    import time
    audit_logs_storage.append({
        "timestamp": time.time(),
        "user": user,
        "action": action,
        "details": details,
    })


@router.post("/broadcast")
async def trigger_broadcast(req: BroadcastRequest, current_user: str = Depends(verify_token)):
    success_count = 0
    failed: List[str] = []

    for item in req.recipients:
        try:
            await send_direct_message(item, req.message)
            success_count += 1
        except Exception:
            failed.append(item)

    record_audit_log(current_user, "TRIGGER_BROADCAST", {"recipients_count": len(req.recipients), "success": success_count})
    return {
        "data": {
            "total": len(req.recipients),
            "success": success_count,
            "failed": failed,
        },
        "error": None,
        "message": "Broadcast executed",
    }


@router.get("/sessions")
async def get_sessions(current_user: str = Depends(verify_token)):
    r = await session_manager.get_redis()
    keys = await r.keys("session:*")
    sessions = []
    for k in keys:
        raw = await r.get(k)
        if raw:
            sessions.append({"key": k, "data": raw})
    return {"data": sessions, "error": None, "message": "Sessions listed"}


@router.post("/sessions/reset")
async def reset_sessions(phone: Optional[str] = None, current_user: str = Depends(verify_token)):
    r = await session_manager.get_redis()
    if phone:
        await session_manager.clear_session(phone)
        count = 1
    else:
        keys = await r.keys("session:*")
        count = len(keys)
        if keys:
            await r.delete(*keys)

    record_audit_log(current_user, "RESET_SESSIONS", {"phone": phone, "cleared_count": count})
    return {
        "data": {"cleared": count},
        "error": None,
        "message": "Sessions reset completed",
    }


@router.get("/guard/config")
def get_guard_config(current_user: str = Depends(verify_token)):
    return {"data": guard_runtime_state, "error": None, "message": "Guard config retrieved"}


@router.post("/guard/config")
def update_guard_config(req: GuardConfigUpdate, current_user: str = Depends(verify_token)):
    if req.enabled is not None:
        guard_runtime_state["enabled"] = req.enabled
    if req.strict_mode is not None:
        guard_runtime_state["strict_mode"] = req.strict_mode

    record_audit_log(current_user, "UPDATE_GUARD_CONFIG", guard_runtime_state)
    return {"data": guard_runtime_state, "error": None, "message": "Guard config updated"}


@router.get("/system/env")
def get_system_env(current_user: str = Depends(verify_token)):
    env_info = {
        "NODE_ENV": settings.node_env,
        "PORT": settings.port,
        "EVOLUTION_API_URL": settings.evolution_api_url,
        "EVOLUTION_INSTANCE_NAME": settings.evolution_instance_name,
        "REDIS_URL": settings.redis_url,
        "NOTION_DATABASE_ID": settings.notion_database_id,
        "NOTION_MASTER_BACKLOG_ID": settings.notion_master_backlog_id,
    }
    return {"data": env_info, "error": None, "message": "Environment info retrieved"}


@router.get("/system/audit-logs")
def get_audit_logs(current_user: str = Depends(verify_token)):
    return {"data": audit_logs_storage, "error": None, "message": "Audit logs retrieved"}
