from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db
from app.deps import client_ip, current_user, issue_session, revoke_session
from app.models import LoginAttempt, SessionToken, User
from app.schemas import (
    AuthModeChange,
    LoginRequest,
    PasswordChange,
    SetupRequest,
    SetupStatus,
    UserOut,
    UserUpdate,
)
from app.security import (
    MIN_PASSWORD_LENGTH,
    hash_password,
    needs_rehash,
    new_random_secret,
    verify_password,
)
from app.seed import get_config

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Spelled out because Starlette renamed its constant and deprecated the old name.
HTTP_422 = 422

# A dummy verify on unknown accounts keeps failed-login timing flat.
_DUMMY_HASH = hash_password("kolektor-timing-equaliser")

OPEN_MODE_PLACEHOLDER_EMAIL = "local@kolektor.local"


def _rate_limited(db: Session, ip: str, settings: Settings) -> bool:
    since = datetime.now(UTC) - timedelta(seconds=settings.login_window_seconds)
    failures = db.scalar(
        select(func.count())
        .select_from(LoginAttempt)
        .where(LoginAttempt.ip == ip, LoginAttempt.at >= since, LoginAttempt.ok.is_(False))
    )
    return bool(failures and failures >= settings.login_max_attempts)


@router.get("/setup", response_model=SetupStatus)
def setup_status(db: Session = Depends(get_db), settings: Settings = Depends(get_settings)) -> SetupStatus:
    config = get_config(db)
    return SetupStatus(
        setup_required=not config.setup_completed,
        auth_mode=config.auth_mode,
        default_language=settings.default_language,
    )


@router.post("/setup", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def complete_setup(
    payload: SetupRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    """First-run choice: protect the app with a password, or run with no login at all."""
    config = get_config(db)
    if config.setup_completed:
        raise HTTPException(status.HTTP_409_CONFLICT, "setup already completed")

    if payload.auth_mode == "password":
        if not payload.email or not payload.password:
            raise HTTPException(
                HTTP_422, "email and password are required in password mode"
            )
        email = payload.email.strip().lower()
        password_hash = hash_password(payload.password)
    else:
        email = OPEN_MODE_PLACEHOLDER_EMAIL
        # Unusable by design: open mode has no login form to submit it to.
        password_hash = hash_password(new_random_secret())

    user = db.execute(select(User).limit(1)).scalar_one_or_none()
    if user is None:
        user = User(email=email, password_hash=password_hash, language=payload.language)
        db.add(user)
    else:
        user.email = email
        user.password_hash = password_hash
        user.language = payload.language

    config.auth_mode = payload.auth_mode
    config.setup_completed = True
    db.commit()
    db.refresh(user)

    if payload.auth_mode == "password":
        issue_session(db, user, request, response, settings)
    return user


@router.post("/mode", response_model=SetupStatus)
def change_auth_mode(
    payload: AuthModeChange,
    request: Request,
    response: Response,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> SetupStatus:
    config = get_config(db)

    if payload.auth_mode == "password":
        if not payload.email or not payload.password:
            raise HTTPException(
                HTTP_422, "email and password are required in password mode"
            )
        if len(payload.password) < MIN_PASSWORD_LENGTH:
            raise HTTPException(
                HTTP_422,
                f"password must be at least {MIN_PASSWORD_LENGTH} characters",
            )
        user.email = payload.email.strip().lower()
        user.password_hash = hash_password(payload.password)
    else:
        user.email = OPEN_MODE_PLACEHOLDER_EMAIL
        user.password_hash = hash_password(new_random_secret())

    config.auth_mode = payload.auth_mode
    db.execute(delete(SessionToken).where(SessionToken.user_id == user.id))
    db.commit()

    if payload.auth_mode == "password":
        issue_session(db, user, request, response, settings)
    else:
        response.delete_cookie("kolektor_session", path="/")

    return SetupStatus(
        setup_required=False, auth_mode=config.auth_mode, default_language=settings.default_language
    )


@router.post("/login", response_model=UserOut)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    config = get_config(db)
    if not config.setup_completed:
        raise HTTPException(status.HTTP_409_CONFLICT, "setup_required")
    if config.auth_mode == "open":
        raise HTTPException(status.HTTP_409_CONFLICT, "this instance runs without login")

    ip = client_ip(request, settings)
    if _rate_limited(db, ip, settings):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "too many attempts, try again later")

    user = db.execute(
        select(User).where(func.lower(User.email) == payload.email.lower())
    ).scalar_one_or_none()

    ok = verify_password(user.password_hash, payload.password) if user else verify_password(
        _DUMMY_HASH, payload.password
    )

    db.add(LoginAttempt(ip=ip, ok=bool(ok and user)))
    db.commit()

    if not ok or user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")

    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(payload.password)
    user.last_login_at = datetime.now(UTC)
    db.commit()

    issue_session(db, user, request, response, settings)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> None:
    revoke_session(db, request, response, settings)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)) -> User:
    return user


@router.patch("/me", response_model=UserOut)
def update_me(
    payload: UserUpdate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> User:
    if payload.display_name is not None:
        user.display_name = payload.display_name
    if payload.language is not None:
        user.language = payload.language
    db.commit()
    return user


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def change_password(
    payload: PasswordChange,
    request: Request,
    response: Response,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> None:
    if not verify_password(user.password_hash, payload.current_password):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "current password is wrong")
    if len(payload.new_password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(
            HTTP_422,
            f"password must be at least {MIN_PASSWORD_LENGTH} characters",
        )
    if payload.new_password == payload.current_password:
        raise HTTPException(HTTP_422, "new password must differ")

    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = False
    db.execute(delete(SessionToken).where(SessionToken.user_id == user.id))
    db.commit()

    issue_session(db, user, request, response, settings)
