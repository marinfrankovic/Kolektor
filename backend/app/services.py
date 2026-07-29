"""Derived values: display title, completeness score and soft validation warnings."""

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


def collect_warnings(item: Item) -> list[str]:
    """Advisory only. Nothing here blocks a save."""
    warnings: list[str] = []

    if not item.country_code and not item.issuing_entity:
        warnings.append("missing_country")
    if item.denomination_value is None and not item.denomination_text:
        warnings.append("missing_denomination")
    if not item.year and not item.year_text:
        warnings.append("missing_year")
    if not item.images:
        warnings.append("no_images")

    if item.status == "sold":
        disposal = item.disposal
        if not disposal or (not disposal.date and disposal.price is None):
            warnings.append("sold_without_disposal")

    if item.kind == "coin":
        coin = item.coin
        if not coin or (coin.weight_g is None and coin.diameter_mm is None):
            warnings.append("coin_without_measurements")
    elif item.kind == "banknote":
        note = item.banknote
        if not note or (not note.pick_number and not note.serial_number):
            warnings.append("banknote_without_pick_or_serial")

    return warnings
