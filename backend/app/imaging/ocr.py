"""OCR-driven field suggestions. Suggestions are never written to an item automatically;
the UI shows them as ghost values the user accepts or rejects."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

import cv2
import numpy as np

CURRENCY_WORDS = {
    "euro": "euro",
    "eur": "euro",
    "cent": "cent",
    "cents": "cent",
    "lipa": "lipa",
    "kuna": "kuna",
    "kune": "kuna",
    "kn": "kuna",
    "dinar": "dinar",
    "dinara": "dinar",
    "para": "para",
    "dollar": "dollar",
    "dollars": "dollar",
    "cents.": "cent",
    "pound": "pound",
    "pence": "pence",
    "penny": "penny",
    "mark": "mark",
    "reichsmark": "reichsmark",
    "deutsche": "deutsche mark",
    "pfennig": "pfennig",
    "franc": "franc",
    "francs": "franc",
    "centimes": "centime",
    "lira": "lira",
    "lire": "lira",
    "peseta": "peseta",
    "escudo": "escudo",
    "rubel": "ruble",
    "rouble": "ruble",
    "ruble": "ruble",
    "kopek": "kopek",
    "kopeks": "kopek",
    "forint": "forint",
    "zloty": "zloty",
    "zlote": "zloty",
    "zlotych": "zloty",
    "koruna": "koruna",
    "koruny": "koruna",
    "korun": "koruna",
    "krone": "krone",
    "kronor": "krona",
    "schilling": "schilling",
    "groschen": "groschen",
    "yen": "yen",
    "yuan": "yuan",
    "rupee": "rupee",
    "rupees": "rupee",
    "lev": "lev",
    "leu": "leu",
    "lei": "leu",
    "tolar": "tolar",
    "denar": "denar",
}

COUNTRY_HINTS = {
    "republika hrvatska": "HR",
    "hrvatska": "HR",
    "croatia": "HR",
    "jugoslavija": "RS",
    "yugoslavia": "RS",
    "bundesrepublik deutschland": "DE",
    "deutschland": "DE",
    "deutsche": "DE",
    "germany": "DE",
    "osterreich": "AT",
    "austria": "AT",
    "republique francaise": "FR",
    "france": "FR",
    "italiana": "IT",
    "italia": "IT",
    "espana": "ES",
    "united states of america": "US",
    "united states": "US",
    "america": "US",
    "canada": "CA",
    "australia": "AU",
    "nederlanden": "NL",
    "nederland": "NL",
    "belgique": "BE",
    "belgie": "BE",
    "helvetia": "CH",
    "suomi": "FI",
    "sverige": "SE",
    "norge": "NO",
    "danmark": "DK",
    "magyar": "HU",
    "polska": "PL",
    "ceska": "CZ",
    "slovenija": "SI",
    "slovensko": "SK",
    "romania": "RO",
    "bulgaria": "BG",
    "srbija": "RS",
    "serbia": "RS",
    "bosna": "BA",
    "makedonija": "MK",
    "crna gora": "ME",
    "portugal": "PT",
    "eire": "IE",
    "ireland": "IE",
    "japan": "JP",
    "china": "CN",
    "india": "IN",
    "brasil": "BR",
    "mexico": "MX",
}

_YEAR_RE = re.compile(r"\b(1[5-9]\d{2}|20[0-4]\d)\b")
_DENOM_RE = re.compile(r"\b(\d{1,4}(?:[.,]\d{1,2})?)\b")
_SERIAL_RE = re.compile(r"\b([A-Z]{0,3}\s?\d{6,10}[A-Z]?)\b")
_LATIN_EXTRAS = str.maketrans({"\u0111": "d", "\u0110": "D", "\u0142": "l", "\u0141": "L", "\u00df": "ss"})


def fold_diacritics(text: str) -> str:
    stripped = unicodedata.normalize("NFKD", text.translate(_LATIN_EXTRAS))
    return "".join(ch for ch in stripped if not unicodedata.combining(ch))


def tesseract_available() -> bool:
    try:
        import pytesseract  # noqa: PLC0415

        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def _prep_for_ocr(image: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    h, w = gray.shape[:2]
    if max(h, w) < 1000:
        scale = 1000 / max(h, w)
        gray = cv2.resize(gray, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)
    gray = cv2.bilateralFilter(gray, 7, 50, 50)
    return cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 12)


def unwrap_coin(image: np.ndarray) -> np.ndarray:
    """Polar unwrap so a circular rim legend becomes a horizontal line of text."""
    h, w = image.shape[:2]
    centre = (w / 2, h / 2)
    radius = min(h, w) / 2
    flags = cv2.INTER_CUBIC | cv2.WARP_POLAR_LINEAR | cv2.WARP_FILL_OUTLIERS
    polar = cv2.warpPolar(image, (int(radius), int(2 * np.pi * radius)), centre, radius, flags)
    return cv2.rotate(polar, cv2.ROTATE_90_COUNTERCLOCKWISE)


def ocr_text(image: np.ndarray, languages: str = "eng") -> str:
    try:
        import pytesseract  # noqa: PLC0415
    except ImportError:
        return ""
    try:
        return pytesseract.image_to_string(_prep_for_ocr(image), lang=languages, config="--psm 6")
    except Exception:
        return ""


def _suggestion(field: str, value: Any, confidence: float, source: str) -> dict[str, Any]:
    return {
        "field": field,
        "value": value,
        "confidence": round(confidence, 2),
        "source": source,
    }


def parse_suggestions(text: str, kind: str) -> list[dict[str, Any]]:
    if not text:
        return []

    flat = " ".join(text.split())
    if not flat:
        return []
    lowered = flat.lower()
    normalised = fold_diacritics(lowered)
    out: list[dict[str, Any]] = []

    years = _YEAR_RE.findall(flat)
    if years:
        best = max(years, key=years.count)
        out.append(_suggestion("year", int(best), 0.75 if len(set(years)) == 1 else 0.55, "ocr"))

    for word, unit in CURRENCY_WORDS.items():
        if re.search(rf"\b{re.escape(word)}\b", normalised):
            out.append(_suggestion("currency_unit", unit, 0.6, "ocr"))
            break

    for phrase, code in COUNTRY_HINTS.items():
        if phrase in normalised:
            out.append(_suggestion("country_code", code, 0.7 if " " in phrase else 0.5, "ocr"))
            break

    numbers = [n for n in _DENOM_RE.findall(flat) if not _YEAR_RE.fullmatch(n)]
    if numbers:
        candidates = [n for n in numbers if len(n.replace(",", "").replace(".", "")) <= 4]
        if candidates:
            value = max(candidates, key=lambda n: (numbers.count(n), -len(n)))
            out.append(_suggestion("denomination_value", value.replace(",", "."), 0.45, "ocr"))

    if kind == "banknote":
        serials = _SERIAL_RE.findall(flat.upper())
        if serials:
            serial = max(serials, key=len).replace(" ", "")
            out.append(_suggestion("banknote.serial_number", serial, 0.5, "ocr"))

    return out


def suggest_fields(image: np.ndarray, kind: str, languages: str = "eng") -> tuple[list[dict[str, Any]], str]:
    text = ocr_text(image, languages)
    if kind == "coin":
        rim_text = ocr_text(unwrap_coin(image), languages)
        text = f"{text}\n{rim_text}"
    return parse_suggestions(text, kind), text.strip()
