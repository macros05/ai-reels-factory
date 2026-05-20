"""JWT-based authentication for the API.

Single-password access — `APP_PASSWORD` is compared in constant time against the
submitted password. On success the API mints a JWT (HS256, signed with
`JWT_SECRET`, 7-day expiry) that the frontend stores in localStorage and sends
back either via `Authorization: Bearer …` or `?token=…` (the latter so plain
`<video src>` tags can load JWT-gated media).
"""

from __future__ import annotations

import hmac
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from src.config import settings


class LoginRequest(BaseModel):
    password: str


class LoginResponse(BaseModel):
    token: str
    expires_at: datetime


_bearer = HTTPBearer(auto_error=False)


def create_token() -> tuple[str, datetime]:
    now = datetime.now(UTC)
    expires_at = now + timedelta(days=settings.jwt_expire_days)
    payload: dict[str, Any] = {
        "sub": "owner",
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, expires_at


def verify_password(submitted: str) -> bool:
    expected = settings.app_password
    if not expected:
        return False
    return hmac.compare_digest(submitted.encode("utf-8"), expected.encode("utf-8"))


def _decode(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"invalid or expired token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def _extract_token(
    request: Request,
    creds: HTTPAuthorizationCredentials | None,
) -> str | None:
    if creds is not None and creds.scheme.lower() == "bearer" and creds.credentials:
        return creds.credentials
    qp = request.query_params.get("token")
    if qp:
        return qp
    return None


async def get_current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict[str, Any]:
    token = _extract_token(request, creds)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing authorization token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _decode(token)
