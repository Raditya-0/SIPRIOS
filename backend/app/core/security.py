from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from jose import JWTError, jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.config import settings

bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_token(data: dict, expires_minutes: Optional[int] = None) -> str:
    payload = data.copy()
    expire = datetime.utcnow() + timedelta(
        minutes=expires_minutes or settings.JWT_EXPIRE_MINUTES
    )
    payload["exp"] = expire
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
):
    if not credentials:
        return None
    try:
        return decode_token(credentials.credentials)
    except JWTError:
        return None


def require_auth(payload: Optional[dict] = Depends(get_current_user)):
    if not payload:
        raise HTTPException(status_code=401, detail="Token tidak valid atau sudah kadaluarsa.")
    return payload


def require_kepala_desa(payload: dict = Depends(require_auth)):
    if payload.get("role") != "kepala_desa":
        raise HTTPException(status_code=403, detail="Hanya Kepala Desa yang dapat mengakses fitur ini.")
    return payload


def require_admin(payload: dict = Depends(require_auth)):
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Hanya Admin yang dapat mengakses fitur ini.")
    return payload


def require_admin_or_kd(payload: dict = Depends(require_auth)):
    if payload.get("role") not in ("admin", "kepala_desa"):
        raise HTTPException(status_code=403, detail="Akses ditolak.")
    return payload