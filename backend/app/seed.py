from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.data.countries import COUNTRIES, HISTORICAL_ENTITIES
from app.models import Country, HistoricalEntity, InstanceConfig, User
from app.security import hash_password

log = logging.getLogger(__name__)


def get_config(db: Session) -> InstanceConfig:
    config = db.get(InstanceConfig, 1)
    if config is None:
        config = InstanceConfig(id=1, auth_mode="password", setup_completed=False)
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


def seed_countries(db: Session) -> int:
    existing = {c.code2 for c in db.execute(select(Country)).scalars().all()}
    added = 0
    for code2, code3, numeric3, name, continent in COUNTRIES:
        if code2 in existing:
            continue
        db.add(Country(code2=code2, code3=code3, numeric3=numeric3, name=name, continent=continent))
        added += 1
    db.commit()
    return added


def seed_historical_entities(db: Session) -> int:
    existing = {e.name for e in db.execute(select(HistoricalEntity)).scalars().all()}
    added = 0
    for name, successor, from_year, to_year, note in HISTORICAL_ENTITIES:
        if name in existing:
            continue
        db.add(
            HistoricalEntity(
                name=name,
                successor_code2=successor,
                from_year=from_year,
                to_year=to_year,
                note=note,
            )
        )
        added += 1
    db.commit()
    return added


def seed_initial_user(db: Session) -> User | None:
    """Optional pre-provisioning. Without env credentials the app shows its first-run
    screen instead, where the user picks password protection or no login at all."""
    settings = get_settings()
    if db.scalar(select(func.count()).select_from(User)):
        return None
    if not settings.initial_user_email or not settings.initial_user_password:
        return None

    user = User(
        email=settings.initial_user_email.strip().lower(),
        password_hash=hash_password(settings.initial_user_password),
        language=settings.default_language,
    )
    db.add(user)

    config = get_config(db)
    config.auth_mode = "password"
    config.setup_completed = True

    db.commit()
    db.refresh(user)
    log.info("pre-provisioned user %s, first-run setup skipped", user.email)
    return user


def seed_all(db: Session) -> None:
    seed_countries(db)
    seed_historical_entities(db)
    get_config(db)
    seed_initial_user(db)
