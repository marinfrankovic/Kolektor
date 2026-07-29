from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import current_user
from app.models import Country, HistoricalEntity
from app.schemas import CountryOut, HistoricalEntityOut

router = APIRouter(prefix="/api/reference", tags=["reference"], dependencies=[Depends(current_user)])


@router.get("/countries", response_model=list[CountryOut])
def countries(db: Session = Depends(get_db)) -> list[Country]:
    return list(db.execute(select(Country).order_by(Country.name)).scalars().all())


@router.get("/historical-entities", response_model=list[HistoricalEntityOut])
def historical_entities(db: Session = Depends(get_db)) -> list[HistoricalEntity]:
    return list(
        db.execute(select(HistoricalEntity).order_by(HistoricalEntity.name)).scalars().all()
    )
