"""Persistent app state (guard config + audit logs) di Redis.

Semua state yang sebelumnya in-memory dipindah ke Redis agar bertahan
restart/redeploy. Audit dibatasi 500 entri terakhir (list terpotong).
"""
import json
import time
from typing import Any, Dict, List

from app.services.session import session_manager

GUARD_KEY = "sga:guard:config"
AUDIT_KEY = "sga:audit:logs"
AUDIT_MAX = 500
DEFAULT_GUARD = {"enabled": True, "strict_mode": True}


async def get_guard_state() -> Dict[str, Any]:
    r = await session_manager.get_redis()
    raw = await r.get(GUARD_KEY)
    if not raw:
        return dict(DEFAULT_GUARD)
    try:
        return {**DEFAULT_GUARD, **json.loads(raw)}
    except Exception:
        return dict(DEFAULT_GUARD)


async def update_guard_state(**updates) -> Dict[str, Any]:
    state = await get_guard_state()
    state.update({k: v for k, v in updates.items() if v is not None})
    r = await session_manager.get_redis()
    await r.set(GUARD_KEY, json.dumps(state))
    return state


async def record_audit_log(user: str, action: str, details: Dict[str, Any]):
    entry = {
        "timestamp": time.time(),
        "user": user,
        "action": action,
        "details": details,
    }
    r = await session_manager.get_redis()
    await r.lpush(AUDIT_KEY, json.dumps(entry))
    await r.ltrim(AUDIT_KEY, 0, AUDIT_MAX - 1)


async def get_audit_logs(limit: int = AUDIT_MAX) -> List[Dict[str, Any]]:
    r = await session_manager.get_redis()
    raws = await r.lrange(AUDIT_KEY, 0, limit - 1)
    out = []
    for raw in raws:
        try:
            out.append(json.loads(raw))
        except Exception:
            continue
    return out
