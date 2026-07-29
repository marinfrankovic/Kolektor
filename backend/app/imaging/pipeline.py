"""Original -> detect -> crop -> enhance -> derivatives. Originals are immutable; the
transform record is enough to regenerate every derivative later."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageOps

from app.config import get_settings
from app.imaging import detect as detect_mod
from app.imaging import enhance as enhance_mod

Image.MAX_IMAGE_PIXELS = 200_000_000


def load_oriented_bgr(path: Path, max_megapixels: int = 80) -> np.ndarray:
    """Load with EXIF orientation applied and all EXIF (including GPS) dropped."""
    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img)
        img = img.convert("RGB")
        if (img.width * img.height) > max_megapixels * 1_000_000:
            raise ValueError("image exceeds maximum pixel budget")
        array = np.asarray(img)
    return cv2.cvtColor(array, cv2.COLOR_RGB2BGR)


def phash(image: np.ndarray, hash_size: int = 8) -> str:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    resized = cv2.resize(gray, (32, 32), interpolation=cv2.INTER_AREA).astype(np.float32)
    dct = cv2.dct(resized)[:hash_size, :hash_size]
    flat = dct.flatten()[1:]
    bits = flat > np.median(flat)
    value = 0
    for bit in bits:
        value = (value << 1) | int(bit)
    return f"{value:016x}"


def hamming(a: str, b: str) -> int:
    if not a or not b or len(a) != len(b):
        return 64
    return bin(int(a, 16) ^ int(b, 16)).count("1")


def _fit(image: np.ndarray, max_px: int) -> np.ndarray:
    h, w = image.shape[:2]
    if max(h, w) <= max_px:
        return image
    scale = max_px / max(h, w)
    return cv2.resize(image, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)


def _write_jpeg(image: np.ndarray, path: Path, quality: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, buf = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        raise RuntimeError(f"failed to encode {path.name}")
    path.write_bytes(buf.tobytes())


def process_image(
    original_path: Path,
    out_dir: Path,
    stem: str,
    kind: str,
    *,
    autocrop: bool | None = None,
    autoenhance: bool | None = None,
    manual_transform: dict[str, Any] | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    autocrop = settings.autocrop if autocrop is None else autocrop
    autoenhance = settings.autoenhance if autoenhance is None else autoenhance

    source = load_oriented_bgr(original_path, settings.max_source_megapixels)
    transform: dict[str, Any] = {"source_size": [source.shape[1], source.shape[0]]}
    working = source

    if manual_transform and manual_transform.get("detection"):
        raw = manual_transform["detection"]
        detection = detect_mod.Detection(
            method="manual",
            confidence=1.0,
            shape=raw.get("shape", "none"),
            circle=tuple(raw["circle"]) if raw.get("circle") else None,
            quad=raw.get("quad"),
            box=tuple(raw["box"]) if raw.get("box") else None,
        )
        working = detect_mod.apply_detection(working, detection)
        transform["crop"] = detection.to_dict()
    elif autocrop:
        detection = detect_mod.detect(source, kind, allow_rembg=settings.enable_rembg)
        if detection.shape != "none" and detection.confidence >= 0.3:
            working = detect_mod.apply_detection(working, detection)
            transform["crop"] = detection.to_dict()
    else:
        detection = detect_mod.Detection("skipped", 0.0, "none")

    if autoenhance:
        working, applied = enhance_mod.auto_enhance(working, kind)
        transform["enhance"] = applied
    else:
        transform["enhance"] = {"blur_score": round(enhance_mod.measure_blur(working), 1)}

    display = _fit(working, max(settings.preview_max_px, 2000))
    preview = _fit(working, settings.preview_max_px)
    thumb = _fit(working, settings.thumb_max_px)

    display_path = out_dir / f"{stem}_display.jpg"
    preview_path = out_dir / f"{stem}_preview.jpg"
    thumb_path = out_dir / f"{stem}_thumb.jpg"
    _write_jpeg(display, display_path, settings.jpeg_quality)
    _write_jpeg(preview, preview_path, settings.jpeg_quality)
    _write_jpeg(thumb, thumb_path, 82)

    return {
        "detection": detection.to_dict(),
        "transform": transform,
        "display_path": display_path,
        "preview_path": preview_path,
        "thumb_path": thumb_path,
        "width": int(working.shape[1]),
        "height": int(working.shape[0]),
        "phash": phash(working),
    }
