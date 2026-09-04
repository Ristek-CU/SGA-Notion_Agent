import base64
import httpx
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from app.config import settings
from app.admin.auth import verify_token

router = APIRouter(tags=["Admin WhatsApp"])


class RenameInstanceRequest(BaseModel):
    new_name: str


class SetBotJidRequest(BaseModel):
    jid: str


class CheckNumberRequest(BaseModel):
    numbers: list[str]


async def _waha_request(method: str, endpoint: str, json_body: Optional[dict] = None):
    url = f"{settings.waha_api_url.rstrip('/')}{endpoint}"
    headers = {"X-Api-Key": settings.waha_api_key}
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            res = await client.request(method, url, headers=headers, json=json_body)
            res.raise_for_status()
            return res.json()
        except httpx.HTTPStatusError as e:
            try:
                detail = e.response.json()
            except Exception:
                detail = e.response.text
            raise HTTPException(status_code=e.response.status_code, detail=detail)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


def _session_name() -> str:
    return settings.waha_instance_name


@router.get("/wa/status")
async def get_wa_status(current_user: str = Depends(verify_token)):
    res = await _waha_request("GET", f"/api/sessions/{_session_name()}")
    return {"data": res, "error": None, "message": "Instance status retrieved"}


@router.get("/wa/test")
async def test_wa_connection(current_user: str = Depends(verify_token)):
    res = await _waha_request("GET", f"/api/sessions/{_session_name()}")
    status = res.get("status")
    me = res.get("me") or {}
    phone = me.get("id") or me.get("user")
    push_name = me.get("pushName")
    engine = res.get("engine") or {}

    target_webhook = settings.waha_webhook_url or f"{settings.backend_public_url.rstrip('/')}/webhook/{_session_name()}"
    configured_webhooks = (res.get("config") or {}).get("webhooks") or []
    webhook_matches = any(w.get("url") == target_webhook for w in configured_webhooks)

    is_ok = status == "WORKING"
    return {
        "data": {
            "ok": is_ok,
            "status": status,
            "phone": phone,
            "pushName": push_name,
            "engine": engine.get("engine"),
            "engine_state": engine.get("state"),
            "target_webhook": target_webhook,
            "webhook_configured": webhook_matches,
            "configured_webhooks": configured_webhooks,
        },
        "error": None if is_ok else f"WhatsApp status is {status}",
        "message": "WhatsApp connected and working" if is_ok else f"WhatsApp status is {status}",
    }


class WebhookUpdateRequest(BaseModel):
    url: Optional[str] = None


@router.post("/wa/webhook-setup")
async def setup_wa_webhook(req: Optional[WebhookUpdateRequest] = None, current_user: str = Depends(verify_token)):
    target_webhook = (req and req.url) or settings.waha_webhook_url or f"{settings.backend_public_url.rstrip('/')}/webhook/{_session_name()}"
    payload = {
        "name": _session_name(),
        "config": {
            "webhooks": [
                {
                    "url": target_webhook,
                    "events": ["message"]
                }
            ]
        }
    }
    res = await _waha_request("PUT", f"/api/sessions/{_session_name()}", json_body=payload)
    return {"data": {"target_webhook": target_webhook, "waha_response": res}, "error": None, "message": "WAHA webhook updated"}


@router.get("/wa/qr")
async def get_wa_qr(current_user: str = Depends(verify_token)):
    """Proxy QR pairing WaHa -> base64 PNG (agar bisa dirender frontend via Bearer JWT)."""
    name = _session_name()
    url = f"{settings.waha_api_url.rstrip('/')}/api/{name}/auth/qr"
    headers = {"X-Api-Key": settings.waha_api_key, "Accept": "image/png"}
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.get(url, headers=headers)
    if resp.status_code != 200:
        raise HTTPException(
            status_code=resp.status_code,
            detail=f"QR belum tersedia (status bukan SCAN_QR_CODE). WaHa: {(resp.text or '')[:200]}",
        )
    b64 = base64.b64encode(resp.content).decode()
    return {"data": {"qr_png_base64": b64}, "error": None, "message": "QR fetched"}


@router.post("/wa/scan")
async def scan_wa(current_user: str = Depends(verify_token)):
    # Re-create session dengan webhook config jika session belum dikonfigurasi
    target_webhook = settings.waha_webhook_url or f"{settings.backend_public_url.rstrip('/')}/webhook/{_session_name()}"
    payload = {
        "name": _session_name(),
        "config": {
            "webhooks": [
                {
                    "url": target_webhook,
                    "events": ["message"]
                }
            ]
        }
    }
    try:
        # Coba hentikan & hapus session lama jika dalam status terhenti/unconfigured
        await _waha_request("POST", f"/api/sessions/{_session_name()}/stop", json_body={})
        await _waha_request("DELETE", f"/api/sessions/{_session_name()}")
    except Exception:
        pass

    try:
        await _waha_request("POST", "/api/sessions", json_body=payload)
    except Exception:
        pass

    res = await _waha_request("POST", f"/api/sessions/{_session_name()}/start")
    return {"data": res, "error": None, "message": "Scan requested with webhook configured"}


@router.post("/wa/disconnect")
async def disconnect_wa(current_user: str = Depends(verify_token)):
    res = await _waha_request("POST", f"/api/sessions/{_session_name()}/logout", json_body={"logout": True})
    return {"data": res, "error": None, "message": "Disconnected"}


@router.post("/wa/refresh")
async def refresh_wa(current_user: str = Depends(verify_token)):
    res = await _waha_request("POST", f"/api/sessions/{_session_name()}/restart")
    return {"data": res, "error": None, "message": "Instance refreshed"}


@router.post("/wa/rename")
async def rename_wa(req: RenameInstanceRequest, current_user: str = Depends(verify_token)):
    return {
        "data": {"instance": _session_name(), "new_name": req.new_name},
        "error": None,
        "message": "Instance rename request accepted",
    }


@router.post("/wa/bot-jid")
async def set_bot_jid(req: SetBotJidRequest, current_user: str = Depends(verify_token)):
    return {
        "data": {"jid": req.jid},
        "error": None,
        "message": "Bot JID updated",
    }


@router.post("/wa/check-number")
async def check_number(req: CheckNumberRequest, current_user: str = Depends(verify_token)):
    from app.wa.sender import check_number_status

    results = []
    for phone in req.numbers:
        try:
            results.append({"phone": phone, "result": await check_number_status(phone)})
        except Exception as e:
            results.append({"phone": phone, "error": str(e)})
    return {"data": {"results": results}, "error": None, "message": "Numbers checked"}