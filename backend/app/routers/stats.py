from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import current_user
from app.models import Acquisition, Country, Item, ItemImage
from app.schemas import CollectionStats, MapCountryStat, MapStats

router = APIRouter(prefix="/api/stats", tags=["stats"], dependencies=[Depends(current_user)])

# Territories that are not sovereign UN members; excluded from the coverage denominator.
NON_SOVEREIGN = {
    "AI", "AQ", "AS", "AW", "AX", "BL", "BM", "BQ", "BV", "CC", "CK", "CW", "CX", "EH",
    "FK", "FO", "GF", "GG", "GI", "GL", "GP", "GS", "GU", "HK", "HM", "IM", "IO", "JE",
    "KY", "MF", "MO", "MP", "MQ", "MS", "NC", "NF", "NU", "PF", "PM", "PN", "PR", "RE",
    "SH", "SJ", "SX", "TC", "TF", "TK", "TW", "UM", "VG", "VI", "WF", "YT", "PS", "VA",
}


@router.get("/map", response_model=MapStats)
def map_stats(db: Session = Depends(get_db)) -> MapStats:
    rows = db.execute(
        select(Item.map_country_code, Item.kind, func.count(Item.id))
        .where(Item.map_country_code.is_not(None), Item.status != "wish")
        .group_by(Item.map_country_code, Item.kind)
    ).all()

    countries = {c.code2: c for c in db.execute(select(Country)).scalars().all()}
    tally: dict[str, MapCountryStat] = {}

    for code, kind, count in rows:
        country = countries.get(code)
        if country is None:
            continue
        stat = tally.setdefault(
            code,
            MapCountryStat(
                code2=country.code2,
                numeric3=country.numeric3,
                name=country.name,
                continent=country.continent,
            ),
        )
        if kind == "coin":
            stat.coins += count
        elif kind == "banknote":
            stat.banknotes += count
        else:
            stat.other += count
        stat.total += count

    by_continent: dict[str, int] = {}
    for stat in tally.values():
        by_continent[stat.continent or "Unknown"] = by_continent.get(stat.continent or "Unknown", 0) + 1

    sovereign_total = sum(1 for code in countries if code not in NON_SOVEREIGN)
    covered = sum(1 for code in tally if code not in NON_SOVEREIGN)

    return MapStats(
        countries=sorted(tally.values(), key=lambda s: s.total, reverse=True),
        covered=covered,
        sovereign_total=sovereign_total,
        by_continent=dict(sorted(by_continent.items())),
    )


@router.get("/summary", response_model=CollectionStats)
def summary(db: Session = Depends(get_db)) -> CollectionStats:
    owned = Item.status != "wish"

    items = db.scalar(select(func.count()).select_from(Item).where(owned)) or 0
    pieces = db.scalar(select(func.coalesce(func.sum(Item.quantity), 0)).where(owned)) or 0
    coins = db.scalar(select(func.count()).select_from(Item).where(owned, Item.kind == "coin")) or 0
    notes = db.scalar(select(func.count()).select_from(Item).where(owned, Item.kind == "banknote")) or 0
    countries = (
        db.scalar(
            select(func.count(func.distinct(Item.map_country_code))).where(
                owned, Item.map_country_code.is_not(None)
            )
        )
        or 0
    )
    images = db.scalar(select(func.count()).select_from(ItemImage)) or 0
    year_min = db.scalar(select(func.min(Item.year)).where(owned))
    year_max = db.scalar(select(func.max(Item.year)).where(owned))
    avg = db.scalar(select(func.avg(Item.completeness)).where(owned)) or 0

    spend_rows = db.execute(
        select(Acquisition.currency, func.sum(Acquisition.price))
        .where(Acquisition.price.is_not(None))
        .group_by(Acquisition.currency)
    ).all()
    spend = {(cur or "?"): Decimal(total or 0) for cur, total in spend_rows}

    return CollectionStats(
        items=items,
        pieces=int(pieces),
        coins=coins,
        banknotes=notes,
        countries=countries,
        images=images,
        year_min=year_min,
        year_max=year_max,
        spend_by_currency=spend,
        average_completeness=round(float(avg), 1),
    )
