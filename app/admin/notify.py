import os
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.admin.auth import verify_token
from app.services.session import session_manager
from app.services.store import (
    record_audit_log,
    get_guard_state,
    update_guard_state,
    get_audit_logs,
)
from app.services.notify import notify_pic
from app.wa.sender import send_direct_message
from app.config import settings

from app.services.queue import queue_manager

router = APIRouter(tags=["Admin Notify & System"])


class BroadcastRequest(BaseModel):
    message: str
    division: Optional[str] = "all"
    platform: Optional[str] = "all"
    delay_seconds: Optional[float] = 5.0
    recipients: Optional[List[str]] = None  # optional recipients override


class BroadcastCancelRequest(BaseModel):
    job_id: Optional[str] = None


class GuardConfigUpdate(BaseModel):
    enabled: Optional[bool] = None
    strict_mode: Optional[bool] = None


@router.post("/broadcast")
async def trigger_broadcast(req: BroadcastRequest, current_user: str = Depends(verify_token)):
    job = await queue_manager.enqueue_broadcast(
        message=req.message,
        division=req.division or "all",
        platform=req.platform or "all",
        delay_seconds=req.delay_seconds if req.delay_seconds is not None else 5.0,
        recipients_override=req.recipients,
    )
    await record_audit_log(
        current_user,
        "TRIGGER_BROADCAST",
        {
            "job_id": job["id"],
            "division": req.division,
            "platform": req.platform,
            "total": job["total"],
        },
    )
    return {
        "data": job,
        "error": None,
        "message": "Broadcast queued",
    }


@router.post("/broadcast/cancel")
async def cancel_broadcast(req: Optional[BroadcastCancelRequest] = None, current_user: str = Depends(verify_token)):
    target_id = req.job_id if req else None
    cancelled = queue_manager.cancel_broadcast(target_id)
    await record_audit_log(current_user, "CANCEL_BROADCAST", {"job_id": target_id, "cancelled": cancelled})
    return {
        "data": {"cancelled": cancelled},
        "error": None,
        "message": "Broadcast cancelled" if cancelled else "No active broadcast job found",
    }


@router.get("/broadcast/queues")
@router.get("/queues/status")
async def get_queue_status(current_user: str = Depends(verify_token)):
    return {
        "data": queue_manager.get_status(),
        "error": None,
        "message": "Queue status fetched",
    }


@router.get("/sessions")
async def get_sessions(current_user: str = Depends(verify_token)):
    """List session percakapan bot (per user, ringkas)."""
    import json as _json
    r = await session_manager.get_redis()
    keys = await r.keys("session:*")
    sessions = []
    for k in sorted(keys):
        raw = await r.get(k)
        if not raw:
            continue
        try:
            d = _json.loads(raw)
        except Exception:
            continue
        msgs = d.get("messages") or []
        last = d.get("last_activity") or 0
        sessions.append({
            "phone": (k.split(":", 1)[1] if ":" in k else k),
            "msg_count": len(msgs),
            "last_msg": (msgs[-1].get("content", "")[:120] if msgs else ""),
            "last_activity": last,
            "pending_ticket": bool(d.get("pending_ticket")),
            "ttl": await r.ttl(k),
        })
    sessions.sort(key=lambda s: s["last_activity"], reverse=True)
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

    await record_audit_log(current_user, "RESET_SESSIONS", {"phone": phone, "cleared_count": count})
    return {
        "data": {"cleared": count},
        "error": None,
        "message": "Sessions reset completed",
    }


@router.get("/guard/config")
async def get_guard_config(current_user: str = Depends(verify_token)):
    state = await get_guard_state()
    return {"data": state, "error": None, "message": "Guard config retrieved"}


@router.post("/guard/config")
async def update_guard_config(req: GuardConfigUpdate, current_user: str = Depends(verify_token)):
    state = await update_guard_state(enabled=req.enabled, strict_mode=req.strict_mode)
    await record_audit_log(current_user, "UPDATE_GUARD_CONFIG", state)
    return {"data": state, "error": None, "message": "Guard config updated"}


class AIConfigUpdate(BaseModel):
    anthropic_base_url: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    ai_model: Optional[str] = None


@router.get("/ai/config")
async def get_ai_config_endpoint(current_user: str = Depends(verify_token)):
    cfg = await session_manager.get_ai_config()
    # Mask API key in response
    masked = dict(cfg)
    key = masked.get("anthropic_api_key") or ""
    if len(key) > 8:
        masked["anthropic_api_key"] = key[:4] + "..." + key[-4:]
    return {"data": masked, "error": None, "message": "AI config retrieved"}


@router.post("/ai/config")
async def update_ai_config_endpoint(req: AIConfigUpdate, current_user: str = Depends(verify_token)):
    updates = req.model_dump(exclude_unset=True)
    cfg = await session_manager.update_ai_config(**updates)
    await record_audit_log(current_user, "UPDATE_AI_CONFIG", {"updated_keys": list(updates.keys())})
    masked = dict(cfg)
    key = masked.get("anthropic_api_key") or ""
    if len(key) > 8:
        masked["anthropic_api_key"] = key[:4] + "..." + key[-4:]
    return {"data": masked, "error": None, "message": "AI config updated"}


@router.get("/system/env")
def get_system_env(current_user: str = Depends(verify_token)):
    env_info = {
        "NODE_ENV": settings.node_env,
        "PORT": settings.port,
        "WAHA_API_URL": settings.waha_api_url,
        "WAHA_INSTANCE_NAME": settings.waha_instance_name,
        "REDIS_URL": settings.redis_url,
        "NOTION_DATABASE_ID": settings.notion_database_id,
        "NOTION_MASTER_BACKLOG_ID": settings.notion_master_backlog_id,
    }
    return {"data": env_info, "error": None, "message": "Environment info retrieved"}


@router.get("/system/audit-logs")
async def get_system_audit_logs(current_user: str = Depends(verify_token)):
    logs = await get_audit_logs()
    return {"data": logs, "error": None, "message": "Audit logs retrieved"}
