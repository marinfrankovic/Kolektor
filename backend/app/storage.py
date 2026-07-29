"""Media path helpers. All item media lives under MEDIA_ROOT and every path that comes
back from the DB is re-validated against that root before it is opened or served."""

from __future__ import annotations

import hashlib
import shutil
import uuid
from pathlib import Path

from app.config import get_settings

ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif", "image/tiff"}
ALLOWED_SUFFIX = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".tif", ".tiff"}

_MAGIC = (
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"II*\x00", "image/tiff"),
    (b"MM\x00*", "image/tiff"),
)


def media_root() -> Path:
    root = Path(get_settings().media_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def sniff_mime(data: bytes) -> str | None:
    for magic, mime in _MAGIC:
        if data.startswith(magic):
            return mime
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[4:8] == b"ftyp" and data[8:12] in (b"heic", b"heix", b"hevc", b"mif1", b"msf1"):
        return "image/heic"
    return None


def item_dir(item_id: uuid.UUID) -> Path:
    key = str(item_id)
    path = media_root() / key[:2] / key
    path.mkdir(parents=True, exist_ok=True)
    return path


def relative(path: Path) -> str:
    return path.resolve().relative_to(media_root()).as_posix()


def purge_item_dir(item_id: uuid.UUID) -> None:
    """Drop every file an item owns once the item itself is gone."""
    key = str(item_id)
    root = media_root()
    path = (root / key[:2] / key).resolve()
    if not path.is_relative_to(root) or not path.is_dir():
        return
    shutil.rmtree(path, ignore_errors=True)
    parent = path.parent
    if parent != root and parent.is_dir() and not any(parent.iterdir()):
        parent.rmdir()


def resolve(rel_path: str) -> Path:
    """Reject anything that escapes MEDIA_ROOT, including via .. or absolute paths."""
    root = media_root()
    candidate = (root / rel_path).resolve()
    if not candidate.is_relative_to(root):
        raise ValueError("path escapes media root")
    return candidate


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
