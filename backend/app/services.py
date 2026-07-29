"""Derived values: display title and completeness score."""

from __future__ import annotations

from decimal import Decimal

from app.models import Item

COMPLETENESS_WEIGHTS = {
    "images": 30,
    "identity": 30,
    "grade": 15,
    "acquisition": 15,
    "catalog": 10,
}


def _fmt_denomination(item: Item) -> str | None:
    if item.denomination_text:
        return item.denomination_text
    if item.denomination_value is None:
        return item.currency_unit
    value = item.denomination_value
    text = str(value.normalize()) if isinstance(value, Decimal) else str(value)
    if "E" in text or "e" in text:
        text = f"{value:f}".rstrip("0").rstrip(".")
    return f"{text} {item.currency_unit}".strip() if item.currency_unit else text


def build_title(item: Item) -> str:
    parts = [
        item.issuing_entity or item.country_code,
        _fmt_denomination(item),
        item.year_text or (str(item.year) if item.year else None),
    ]
    title = ", ".join(p for p in parts if p)
    return title or ("Untitled coin" if item.kind == "coin" else "Untitled item")


def compute_completeness(item: Item) -> int:
    score = 0

    images = [i for i in item.images if i.status != "failed"]
    if images:
        score += COMPLETENESS_WEIGHTS["images"] // 2
    if len(images) >= 2:
        score += COMPLETENESS_WEIGHTS["images"] - COMPLETENESS_WEIGHTS["images"] // 2

    identity_fields = [
        item.country_code or item.issuing_entity,
        item.denomination_value if item.denomination_value is not None else item.denomination_text,
        item.currency_unit,
        item.year or item.year_text,
    ]
    filled = sum(1 for f in identity_fields if f)
    score += round(COMPLETENESS_WEIGHTS["identity"] * filled / len(identity_fields))

    if item.grade_value:
        score += COMPLETENESS_WEIGHTS["grade"]

    acq = item.acquisition
    if acq and (acq.date or acq.price is not None):
        score += COMPLETENESS_WEIGHTS["acquisition"]

    if item.catalog_refs:
        score += COMPLETENESS_WEIGHTS["catalog"]

    return max(0, min(100, score))
