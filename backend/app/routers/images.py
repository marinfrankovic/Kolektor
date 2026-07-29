from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db
from app.deps import current_user
from app.fetching import FetchError, fetch_image
from app.models import IMAGE_ROLES, Item, ItemImage, Job
from app.schemas import ImageImport, ImageOut
from app.storage import ALLOWED_SUFFIX, item_dir, relative, resolve, sha256_bytes, sniff_mime

router = APIRouter(prefix="/api/images", tags=["images"], dependencies=[Depends(current_user)])

VARIANTS = {"thumb": "thumb_path", "preview": "preview_path", "display": "display_path"}
SUFFIX_FOR_MIME = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/heic": ".heic",
    "image/tiff": ".tif",
}

# Spelled out because Starlette renamed its constant and deprecated the old name.
HTTP_422 = 422


def _get_image(db: Session, image_id: uuid.UUID) -> ItemImage:
    image = db.get(ItemImage, image_id)
    if image is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "image not found")
    return image


def _checked_item(db: Session, item_id: uuid.UUID, role: str) -> Item:
    item = db.get(Item, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "item not found")
    if role not in IMAGE_ROLES:
        raise HTTPException(HTTP_422, "unknown image role")
    return item


def _store(db: Session, item_id: uuid.UUID, role: str, data: bytes, suffix: str) -> ItemImage:
    mime = sniff_mime(data)
    if mime is None:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "file content is not an image")

    image_id = uuid.uuid4()
    original = item_dir(item_id) / f"{image_id}_original{suffix}"
    original.write_bytes(data)

    next_sort = db.scalar(
        select(ItemImage.sort).where(ItemImage.item_id == item_id).order_by(ItemImage.sort.desc()).limit(1)
    )

    image = ItemImage(
        id=image_id,
        item_id=item_id,
        role=role,
        sort=(next_sort or 0) + 1,
        status="pending",
        original_path=relative(original),
        mime=mime,
        bytes=len(data),
        sha256=sha256_bytes(data),
    )
    db.add(image)
    db.add(Job(kind="process_image", payload={"image_id": str(image_id)}))
    db.commit()
    db.refresh(image)
    return image


@router.post("", response_model=ImageOut, status_code=status.HTTP_201_CREATED)
async def upload_image(
    item_id: uuid.UUID = Form(...),
    role: str = Form("other"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ItemImage:
    _checked_item(db, item_id, role)

    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIX:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "unsupported file type")

    data = await file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "file too large")
    if not data:
        raise HTTPException(HTTP_422, "empty file")

    return _store(db, item_id, role, data, suffix)


@router.post("/from-url", response_model=ImageOut, status_code=status.HTTP_201_CREATED)
def import_image(
    payload: ImageImport,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ItemImage:
    """Pull a picture the user linked to instead of asking them to download it first."""
    _checked_item(db, payload.item_id, payload.role)

    try:
        data = fetch_image(payload.url, settings.max_upload_bytes)
    except FetchError as err:
        raise HTTPException(HTTP_422, str(err)) from None

    mime = sniff_mime(data)
    if mime is None:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "the link is not an image")

    return _store(db, payload.item_id, payload.role, data, SUFFIX_FOR_MIME[mime])


@router.get("/{image_id}/original")
def get_original(image_id: uuid.UUID, db: Session = Depends(get_db)) -> FileResponse:
    image = _get_image(db, image_id)
    try:
        path = resolve(image.original_path)
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid media path") from None
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "file missing")
    return FileResponse(path, headers={"Cache-Control": "private, max-age=86400"})


# Declared after /original so that the literal path wins over this catch-all.
@router.get("/{image_id}/{variant}")
def get_variant(
    image_id: uuid.UUID,
    variant: str,
    db: Session = Depends(get_db),
) -> FileResponse:
    if variant not in VARIANTS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "unknown variant")

    image = _get_image(db, image_id)
    rel = getattr(image, VARIANTS[variant]) or image.original_path
    try:
        path = resolve(rel)
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid media path") from None
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "file missing")

    return FileResponse(path, headers={"Cache-Control": "private, max-age=86400"})


@router.post("/{image_id}/reprocess", response_model=ImageOut)
def reprocess(
    image_id: uuid.UUID,
    payload: dict | None = None,
    db: Session = Depends(get_db),
) -> ItemImage:
    """Re-run the pipeline, optionally with a crop the user adjusted by hand."""
    image = _get_image(db, image_id)
    image.status = "pending"
    image.error = None
    job_payload: dict = {"image_id": str(image_id)}
    if payload:
        job_payload["manual_transform"] = payload.get("manual_transform")
        job_payload["autocrop"] = payload.get("autocrop")
        job_payload["autoenhance"] = payload.get("autoenhance")
    db.add(Job(kind="process_image", payload=job_payload))
    db.commit()
    db.refresh(image)
    return image


@router.patch("/{image_id}", response_model=ImageOut)
def update_image(image_id: uuid.UUID, payload: dict, db: Session = Depends(get_db)) -> ItemImage:
    image = _get_image(db, image_id)
    if "role" in payload:
        if payload["role"] not in IMAGE_ROLES:
            raise HTTPException(HTTP_422, "unknown image role")
        image.role = payload["role"]
    if "sort" in payload:
        image.sort = int(payload["sort"])
    db.commit()
    db.refresh(image)
    return image


@router.delete("/{image_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_image(image_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    image = _get_image(db, image_id)
    for rel in (image.original_path, image.display_path, image.preview_path, image.thumb_path):
        if not rel:
            continue
        try:
            path = resolve(rel)
        except ValueError:
            continue
        path.unlink(missing_ok=True)
    db.delete(image)
    db.commit()
