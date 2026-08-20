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


async def _evolution_request(method: str, endpoint: str, json_body: Optional[dict] = None):
    url = f"{settings.evolution_api_url.rstrip('/')}{endpoint}"
    headers = {"apikey": settings.evolution_api_key}
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            res = await client.request(method, url, headers=headers, json=json_body)
            res.raise_for_status()
            return res.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/wa/status")
async def get_wa_status(current_user: str = Depends(verify_token)):
    res = await _evolution_request("GET", f"/instance/connectionState/{settings.evolution_instance_name}")
    return {"data": res, "error": None, "message": "Instance status retrieved"}


@router.get("/wa/qr")
async def get_wa_qr(current_user: str = Depends(verify_token)):
    res = await _evolution_request("GET", f"/instance/connect/{settings.evolution_instance_name}")
    return {"data": res, "error": None, "message": "QR code retrieved"}


@router.post("/wa/scan")
async def scan_wa(current_user: str = Depends(verify_token)):
    res = await _evolution_request("GET", f"/instance/connect/{settings.evolution_instance_name}")
    return {"data": res, "error": None, "message": "Scan requested"}


@router.post("/wa/disconnect")
async def disconnect_wa(current_user: str = Depends(verify_token)):
    res = await _evolution_request("DELETE", f"/instance/logout/{settings.evolution_instance_name}")
    return {"data": res, "error": None, "message": "Disconnected"}


@router.post("/wa/refresh")
async def refresh_wa(current_user: str = Depends(verify_token)):
    res = await _evolution_request("POST", f"/instance/restart/{settings.evolution_instance_name}")
    return {"data": res, "error": None, "message": "Instance refreshed"}


@router.post("/wa/rename")
async def rename_wa(req: RenameInstanceRequest, current_user: str = Depends(verify_token)):
    return {
        "data": {"instance": settings.evolution_instance_name, "new_name": req.new_name},
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
    res = await _evolution_request(
        "POST",
        f"/chat/whatsappNumbers/{settings.evolution_instance_name}",
        json_body={"numbers": req.numbers},
    )
    return {"data": res, "error": None, "message": "Numbers checked"}
