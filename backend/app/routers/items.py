from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import String, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.deps import current_user
from app.models import (
    Acquisition,
    CatalogRef,
    Disposal,
    Item,
    ItemBanknote,
    ItemCoin,
    ItemImage,
    User,
)
from app.schemas import ItemCreate, ItemListRow, ItemOut, ItemPage, ItemUpdate
from app.services import build_title, collect_warnings, compute_completeness
from app.storage import purge_item_dir

router = APIRouter(prefix="/api/items", tags=["items"], dependencies=[Depends(current_user)])

SORTABLE = {
    "updated_at": Item.updated_at,
    "created_at": Item.created_at,
    "title": Item.title,
    "year": Item.year,
    "country": Item.map_country_code,
    "completeness": Item.completeness,
}


def _loaded(db: Session, item_id: uuid.UUID) -> Item:
    item = db.execute(
        select(Item)
        .where(Item.id == item_id)
        .options(
            selectinload(Item.coin),
            selectinload(Item.banknote),
            selectinload(Item.images),
            selectinload(Item.catalog_refs),
            selectinload(Item.acquisition),
            selectinload(Item.disposal),
        )
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "item not found")
    return item


def _apply_side_tables(db: Session, item: Item, payload: ItemCreate | ItemUpdate) -> None:
    if payload.coin is not None:
        target = item.coin or ItemCoin(item_id=item.id)
        for field, value in payload.coin.model_dump(exclude_unset=True).items():
            setattr(target, field, value)
        item.coin = target
    if payload.banknote is not None:
        target = item.banknote or ItemBanknote(item_id=item.id)
        for field, value in payload.banknote.model_dump(exclude_unset=True).items():
            setattr(target, field, value)
        item.banknote = target
    if payload.acquisition is not None:
        target = item.acquisition or Acquisition(item_id=item.id)
        for field, value in payload.acquisition.model_dump(exclude_unset=True).items():
            setattr(target, field, value)
        item.acquisition = target
    if payload.disposal is not None:
        target = item.disposal or Disposal(item_id=item.id)
        for field, value in payload.disposal.model_dump(exclude_unset=True).items():
            setattr(target, field, value)
        item.disposal = target
    if payload.catalog_refs:
        db.query(CatalogRef).filter(CatalogRef.item_id == item.id).delete()
        seen: set[tuple[str, str]] = set()
        for ref in payload.catalog_refs:
            key = (ref.catalog, ref.number)
            if key in seen:
                continue
            seen.add(key)
            db.add(CatalogRef(item_id=item.id, catalog=ref.catalog, number=ref.number))


def _finalise(db: Session, item: Item) -> Item:
    db.flush()
    db.refresh(item)
    if not item.map_country_code and item.country_code:
        item.map_country_code = item.country_code
    if not item.title:
        item.title = build_title(item)
    item.completeness = compute_completeness(item)
    db.commit()
    return _loaded(db, item.id)


def _to_out(item: Item) -> dict[str, Any]:
    data = ItemOut.model_validate(item).model_dump()
    data["warnings"] = collect_warnings(item)
    return data


@router.get("", response_model=ItemPage)
def list_items(
    db: Session = Depends(get_db),
    q: str | None = None,
    kind: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    country: str | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    tag: str | None = None,
    sort: str = "updated_at",
    order: str = "desc",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> ItemPage:
    stmt = select(Item)

    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Item.title.ilike(pattern),
                Item.issuing_entity.ilike(pattern),
                Item.notes.ilike(pattern),
                Item.subject.ilike(pattern),
                Item.series.ilike(pattern),
                Item.denomination_text.ilike(pattern),
            )
        )
    if kind:
        stmt = stmt.where(Item.kind == kind)
    if status_filter:
        stmt = stmt.where(Item.status == status_filter)
    if country:
        if country.lower() == "none":
            stmt = stmt.where(Item.map_country_code.is_(None))
        else:
            stmt = stmt.where(Item.map_country_code == country.upper())
    if year_from is not None:
        stmt = stmt.where(Item.year >= year_from)
    if year_to is not None:
        stmt = stmt.where(Item.year <= year_to)
    if tag:
        if db.get_bind().dialect.name == "postgresql":
            stmt = stmt.where(Item.tags.any(tag))
        else:
            stmt = stmt.where(func.cast(Item.tags, String).like(f'%"{tag}"%'))

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    column = SORTABLE.get(sort, Item.updated_at)
    stmt = stmt.order_by(column.desc() if order == "desc" else column.asc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)

    items = db.execute(stmt.options(selectinload(Item.images))).scalars().all()

    rows = []
    for item in items:
        thumb = next((i for i in item.images if i.status == "ready"), None)
        row = ItemListRow.model_validate(item)
        row.thumb_image_id = thumb.id if thumb else None
        rows.append(row)

    return ItemPage(total=total, page=page, page_size=page_size, rows=rows)


@router.post("", response_model=ItemOut, status_code=status.HTTP_201_CREATED)
def create_item(payload: ItemCreate, db: Session = Depends(get_db)) -> dict[str, Any]:
    base = payload.model_dump(
        exclude={"coin", "banknote", "acquisition", "disposal", "catalog_refs"},
        exclude_unset=False,
    )
    base["title"] = base.get("title") or ""
    item = Item(**base)
    db.add(item)
    db.flush()
    _apply_side_tables(db, item, payload)
    return _to_out(_finalise(db, item))


@router.get("/{item_id}", response_model=ItemOut)
def get_item(item_id: uuid.UUID, db: Session = Depends(get_db)) -> dict[str, Any]:
    return _to_out(_loaded(db, item_id))


@router.patch("/{item_id}", response_model=ItemOut)
def update_item(item_id: uuid.UUID, payload: ItemUpdate, db: Session = Depends(get_db)) -> dict[str, Any]:
    item = _loaded(db, item_id)
    base = payload.model_dump(
        exclude={"coin", "banknote", "acquisition", "disposal", "catalog_refs"},
        exclude_unset=True,
    )
    for field, value in base.items():
        setattr(item, field, value)
    _apply_side_tables(db, item, payload)
    return _to_out(_finalise(db, item))


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_item(item_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    item = _loaded(db, item_id)
    db.delete(item)
    db.commit()
    # Only after the rows are gone, so a failed commit cannot orphan the DB from its files.
    purge_item_dir(item_id)


@router.get("/{item_id}/similar", response_model=list[ItemListRow])
def similar_items(item_id: uuid.UUID, db: Session = Depends(get_db)) -> list[ItemListRow]:
    """Soft duplicate hint: same country plus pick number or catalogue-ish identity."""
    item = _loaded(db, item_id)
    stmt = select(Item).where(Item.id != item.id).options(selectinload(Item.images))

    if item.kind == "banknote" and item.banknote and item.banknote.pick_number:
        stmt = stmt.join(ItemBanknote).where(
            ItemBanknote.pick_number == item.banknote.pick_number,
            Item.map_country_code == item.map_country_code,
        )
    else:
        stmt = stmt.where(
            Item.map_country_code == item.map_country_code,
            Item.year == item.year,
            Item.denomination_value == item.denomination_value,
        )

    return [ItemListRow.model_validate(row) for row in db.execute(stmt.limit(10)).scalars().all()]


@router.get("/{item_id}/images/count", response_model=dict)
def image_count(item_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(current_user)) -> dict:
    count = db.scalar(select(func.count()).select_from(ItemImage).where(ItemImage.item_id == item_id))
    return {"count": count or 0}
