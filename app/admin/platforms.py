from typing import Any, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from app.config import settings
from app.admin.auth import verify_token
from app.services.platform_config import (
    PlatformConfig,
    load_platform_config,
    save_platform_config,
    mask_token,
)

router = APIRouter(prefix="/platforms", tags=["Admin Platforms"])

PLATFORM = "telegram"


class PlatformUpdate(BaseModel):
    enabled: bool = False
    bot_token: str = ""


def _mask(cfg: Optional[PlatformConfig]) -> dict:
    c = cfg or PlatformConfig()
    return {"enabled": c.enabled, "bot_token": mask_token(c.bot_token)}


@router.get("/telegram")
async def get_platform(current_user: str = Depends(verify_token)):
    cfg = await load_platform_config(PLATFORM)
    return {"data": _mask(cfg), "error": None, "message": "ok"}


@router.put("/telegram")
async def put_platform(body: PlatformUpdate, current_user: str = Depends(verify_token)):
    cfg = await load_platform_config(PLATFORM) or PlatformConfig()
    if body.bot_token and not mask_token(cfg.bot_token) == body.bot_token:
        cfg.bot_token = body.bot_token.strip()
    cfg.enabled = body.enabled
    await save_platform_config(PLATFORM, cfg)
    return {"data": _mask(cfg), "error": None, "message": "Platform config saved"}


async def _tg(token: str, method: str, payload: Optional[dict] = None):
    import httpx

    async with httpx.AsyncClient(timeout=15.0) as http:
        resp = await http.post(f"https://api.telegram.org/bot{token}/{method}", json=payload or {})
        try:
            data = resp.json()
        except Exception:
            raise HTTPException(status_code=502, detail=resp.text)
        if not data.get("ok"):
            raise HTTPException(status_code=502, detail=data.get("description", "Telegram API error"))
        return data.get("result", {})


@router.get("/telegram/test")
async def test_platform(current_user: str = Depends(verify_token)):
    cfg = await load_platform_config(PLATFORM)
    if not cfg or not cfg.bot_token:
        raise HTTPException(status_code=400, detail="bot_token belum dikonfigurasi")
    result = await _tg(cfg.bot_token, "getMe")
    return {"data": {"bot": result}, "error": None, "message": "getMe OK"}


@router.post("/telegram/webhook-setup")
async def webhook_setup(current_user: str = Depends(verify_token)):
    cfg = await load_platform_config(PLATFORM)
    if not cfg or not cfg.bot_token:
        raise HTTPException(status_code=400, detail="bot_token belum dikonfigurasi")
    base = settings.backend_public_url.rstrip("/")
    url = f"{base}/webhook/telegram/{cfg.bot_token}"
    result = await _tg(cfg.bot_token, "setWebhook", {"url": url})
    return {"data": {"webhook_url": url, "result": result}, "error": None, "message": "setWebhook OK"}
