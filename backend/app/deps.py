from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db
from app.models import SessionToken, User
from app.security import hash_session_token, new_session_token

SESSION_COOKIE = "kolektor_session"


def client_ip(request: Request, settings: Settings) -> str:
    if settings.behind_proxy:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def issue_session(db: Session, user: User, request: Request, response: Response, settings: Settings) -> None:
    token = new_session_token()
    expires = datetime.now(UTC) + timedelta(hours=settings.session_ttl_hours)
    db.add(
        SessionToken(
            token_hash=hash_session_token(token, settings.secret_key),
            user_id=user.id,
            expires_at=expires,
            user_agent=(request.headers.get("user-agent") or "")[:400],
        )
    )
    db.commit()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.session_ttl_hours * 3600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path="/",
    )


def revoke_session(db: Session, request: Request, response: Response, settings: Settings) -> None:
    raw = request.cookies.get(SESSION_COOKIE)
    if raw:
        db.query(SessionToken).filter(
            SessionToken.token_hash == hash_session_token(raw, settings.secret_key)
        ).delete()
        db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")


def current_user(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    from app.seed import get_config  # imported here to avoid a circular import at module load

    config = get_config(db)
    if not config.setup_completed:
        raise HTTPException(status.HTTP_409_CONFLICT, "setup_required")

    if config.auth_mode == "open":
        user = db.execute(select(User).limit(1)).scalar_one_or_none()
        if user is None:
            raise HTTPException(status.HTTP_409_CONFLICT, "setup_required")
        return user

    raw = request.cookies.get(SESSION_COOKIE)
    if not raw:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not authenticated")

    token_hash = hash_session_token(raw, settings.secret_key)
    row = db.execute(select(SessionToken).where(SessionToken.token_hash == token_hash)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid session")

    expires = row.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    if expires < datetime.now(UTC):
        db.delete(row)
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "session expired")

    user = db.get(User, row.user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user missing")
    return user
