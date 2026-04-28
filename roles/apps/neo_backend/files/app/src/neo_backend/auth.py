from __future__ import annotations

import hmac

from fastapi import HTTPException, Request, status

from .config import Settings


def _extract_token(request: Request) -> str:
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    header_password = request.headers.get("x-proxy-password", "")
    if header_password:
        return header_password.strip()
    return request.query_params.get("password", "").strip()


def require_proxy_auth(request: Request, settings: Settings) -> None:
    if not settings.proxy_password and settings.allow_empty_password:
        return

    provided = _extract_token(request)
    if not provided or not hmac.compare_digest(provided, settings.proxy_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Bearer"},
        )
