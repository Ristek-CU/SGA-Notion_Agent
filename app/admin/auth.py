import json
import logging
import secrets
import time
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from app.config import settings
from app.services.session import session_manager
from app.wa.sender import send_whatsapp_message
from app.telegram.bot import send_telegram_message

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Admin Auth"])

security = HTTPBearer()

# In-memory auth override for runtime password change if needed, fallback to settings
_current_admin_password = settings.admin_password


class LoginRequest(BaseModel):
    username: str
    password: str


class VerifyOtpRequest(BaseModel):
    session_id: str
    otp: str


class ResendOtpRequest(BaseModel):
    session_id: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


def create_jwt_token(username: str) -> str:
    import jwt
    payload = {
        "sub": username,
        "iat": int(time.time()),
        "exp": int(time.time()) + 86400 * 7,  # 7 days
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    import jwt
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        username: str = payload.get("sub")
        if username != settings.admin_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )
        return username
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


def _otp_key(session_id: str) -> str:
    return f"admin:otp:{session_id}"


def generate_otp() -> str:
    # 6 digit cryptographically secure random number
    return f"{secrets.randbelow(900000) + 100000}"


async def send_otp_notifications(otp_code: str):
    message = (
        "🔐 *Kode OTP Login Dashboard Roro*\n\n"
        f"Kode OTP Anda: *{otp_code}*\n\n"
        "Kode ini berlaku selama 5 menit. Jangan bagikan kode ini kepada siapapun demi keamanan."
    )
    delivery_status = {"whatsapp": False, "telegram": False}

    # 1. Kirim ke WhatsApp Salman
    wa_target = settings.otp_target_wa
    if wa_target:
        try:
            res_wa = await send_whatsapp_message(wa_target, message)
            delivery_status["whatsapp"] = True
            logger.info(f"[OTP] Sent OTP to WhatsApp {wa_target}: {res_wa}")
        except Exception as e:
            logger.error(f"[OTP] Failed to send OTP to WhatsApp {wa_target}: {e}")

    # 2. Kirim ke Telegram Salman
    # Prioritaskan target spesifik, atau lookup otomatis telegram_chat_id dari contacts
    tg_target = settings.otp_target_tg
    if not tg_target or tg_target == "195340229":
        # Fallback dynamic lookup
        try:
            from app.services.contacts import get_telegram_chat_id
            found_id = await get_telegram_chat_id("pangestuu19")
            if found_id:
                tg_target = found_id
        except Exception as lookup_err:
            logger.warning(f"[OTP] Dynamic lookup telegram_chat_id failed: {lookup_err}")

    if tg_target:
        try:
            res_tg = await send_telegram_message(tg_target, message)
            delivery_status["telegram"] = True
            logger.info(f"[OTP] Sent OTP to Telegram {tg_target}: {res_tg}")
        except Exception as e:
            logger.error(f"[OTP] Failed to send OTP to Telegram {tg_target}: {e}")

    return delivery_status


@router.post("/login")
async def login(req: LoginRequest):
    global _current_admin_password
    if req.username != settings.admin_user or req.password != _current_admin_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Username atau password salah",
        )

    # Jika OTP dimatikan secara eksplisit di environment (misal untuk testing lokal tanpa redis/notif), langsung beri token
    if not settings.otp_enabled:
        token = create_jwt_token(req.username)
        return {
            "data": {
                "token": token,
                "user": {"username": req.username},
            },
            "error": None,
            "message": "Login successful",
        }

    session_id = uuid.uuid4().hex
    otp_code = generate_otp()
    ttl = settings.otp_ttl_seconds

    # Simpan di Redis
    otp_data = {
        "username": req.username,
        "otp": otp_code,
        "attempts": 0,
        "created_at": time.time(),
    }
    r = await session_manager.get_redis()
    await r.set(_otp_key(session_id), json.dumps(otp_data), ex=ttl)

    # Kirim OTP ke WA & Telegram Salman
    await send_otp_notifications(otp_code)

    return {
        "status": "otp_required",
        "session_id": session_id,
        "expires_in": ttl,
        "message": "Kode OTP telah dikirim ke WhatsApp & Telegram Salman",
        "data": {
            "status": "otp_required",
            "session_id": session_id,
            "expires_in": ttl,
        },
        "error": None,
    }


@router.post("/login/verify-otp")
async def verify_otp(req: VerifyOtpRequest):
    r = await session_manager.get_redis()
    key = _otp_key(req.session_id)
    raw = await r.get(key)
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sesi OTP telah kadaluarsa atau tidak valid. Silakan login kembali.",
        )

    try:
        otp_data = json.loads(raw)
    except Exception:
        await r.delete(key)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Format data OTP rusak. Silakan login kembali.",
        )

    # Cek attempt count (brute force protection)
    attempts = otp_data.get("attempts", 0) + 1
    otp_data["attempts"] = attempts

    if attempts > settings.otp_max_attempts:
        await r.delete(key)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Batas percobaan OTP terlampaui. Silakan minta kode OTP baru.",
        )

    # Validasi kode OTP
    expected_otp = str(otp_data.get("otp", "")).strip()
    submitted_otp = str(req.otp).strip()

    if submitted_otp != expected_otp:
        # Update remaining ttl & attempt count
        ttl = await r.ttl(key)
        if ttl > 0:
            await r.set(key, json.dumps(otp_data), ex=ttl)
        remaining = settings.otp_max_attempts - attempts
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Kode OTP salah. Sisa percobaan: {remaining}",
        )

    # OTP Valid: hapus dari Redis dan buat JWT token
    await r.delete(key)
    username = otp_data.get("username", settings.admin_user)
    token = create_jwt_token(username)

    return {
        "status": "success",
        "token": token,
        "user": username,
        "data": {
            "token": token,
            "user": {"username": username},
        },
        "error": None,
        "message": "Login successful",
    }


@router.post("/login/resend-otp")
async def resend_otp(req: ResendOtpRequest):
    r = await session_manager.get_redis()
    key = _otp_key(req.session_id)
    raw = await r.get(key)
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sesi OTP tidak ditemukan atau telah kadaluarsa.",
        )

    try:
        otp_data = json.loads(raw)
    except Exception:
        await r.delete(key)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Format data OTP rusak. Silakan login kembali.",
        )

    # Generate fresh OTP code and reset attempts
    new_otp = generate_otp()
    otp_data["otp"] = new_otp
    otp_data["attempts"] = 0
    otp_data["created_at"] = time.time()
    ttl = settings.otp_ttl_seconds

    await r.set(key, json.dumps(otp_data), ex=ttl)

    # Dispatch fresh OTP
    await send_otp_notifications(new_otp)

    return {
        "status": "resent",
        "session_id": req.session_id,
        "expires_in": ttl,
        "message": "Kode OTP baru telah dikirim ke WhatsApp & Telegram Salman",
        "data": {
            "session_id": req.session_id,
            "expires_in": ttl,
        },
        "error": None,
    }


@router.post("/change-password")
def change_password(
    req: ChangePasswordRequest,
    current_user: str = Depends(verify_token),
):
    global _current_admin_password
    if req.current_password != _current_admin_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password lama tidak sesuai",
        )
    _current_admin_password = req.new_password
    return {
        "data": {"status": "updated"},
        "error": None,
        "message": "Password berhasil diubah",
    }
