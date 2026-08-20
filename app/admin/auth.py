import jwt
import time
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from app.config import settings

router = APIRouter(tags=["Admin Auth"])

security = HTTPBearer()

# In-memory auth override for runtime password change if needed, fallback to settings
_current_admin_password = settings.admin_password


class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


def create_jwt_token(username: str) -> str:
    payload = {
        "sub": username,
        "iat": int(time.time()),
        "exp": int(time.time()) + 86400 * 7,  # 7 days
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
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


@router.post("/login")
def login(req: LoginRequest):
    global _current_admin_password
    if req.username == settings.admin_user and req.password == _current_admin_password:
        token = create_jwt_token(req.username)
        return {
            "data": {
                "token": token,
                "user": {"username": req.username},
            },
            "error": None,
            "message": "Login successful",
        }
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Username atau password salah",
    )


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
