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
    res = await _waha_request("GET", f"/api/session/{_session_name()}/status")
    return {"data": res, "error": None, "message": "Instance status retrieved"}


@router.get("/wa/qr")
async def get_wa_qr(current_user: str = Depends(verify_token)):
    # Status berisi qr/lastKnownQrCode saat sesi dalam kondisi SCAN_QR_CODE
    res = await _waha_request("GET", f"/api/session/{_session_name()}/status")
    return {"data": res, "error": None, "message": "QR code retrieved"}


@router.post("/wa/scan")
async def scan_wa(current_user: str = Depends(verify_token)):
    res = await _waha_request("POST", f"/api/session/{_session_name()}/start")
    return {"data": res, "error": None, "message": "Scan requested"}


@router.post("/wa/disconnect")
async def disconnect_wa(current_user: str = Depends(verify_token)):
    res = await _waha_request("POST", f"/api/session/{_session_name()}/logout?logout=true")
    return {"data": res, "error": None, "message": "Disconnected"}


@router.post("/wa/refresh")
async def refresh_wa(current_user: str = Depends(verify_token)):
    # WaHa tidak punya /restart; restart == start ulang sesi
    res = await _waha_request("POST", f"/api/session/{_session_name()}/start")
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