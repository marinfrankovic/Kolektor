from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import current_user
from app.models import Country, HistoricalEntity, Item
from app.schemas import CountryOut, HistoricalEntityOut

router = APIRouter(prefix="/api/reference", tags=["reference"], dependencies=[Depends(current_user)])


@router.get("/countries", response_model=list[CountryOut])
def countries(used: bool = False, db: Session = Depends(get_db)) -> list[Country]:
    stmt = select(Country).order_by(Country.name)
    if used:
        owned = select(Item.map_country_code).where(Item.map_country_code.is_not(None))
        stmt = stmt.where(Country.code2.in_(owned))
    return list(db.execute(stmt).scalars().all())


@router.get("/historical-entities", response_model=list[HistoricalEntityOut])
def historical_entities(db: Session = Depends(get_db)) -> list[HistoricalEntity]:
    return list(
        db.execute(select(HistoricalEntity).order_by(HistoricalEntity.name)).scalars().all()
    )
