"""Polls the job table. A DB-backed queue keeps the stack to three containers with no broker."""

from __future__ import annotations

import logging
import signal
import time
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal
from app.imaging.pipeline import process_image
from app.models import Item, ItemImage, Job
from app.services import compute_completeness
from app.storage import item_dir, relative, resolve

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s worker %(message)s")
log = logging.getLogger("kolektor.worker")

_running = True


def _stop(*_args: object) -> None:
    global _running
    _running = False
    log.info("shutdown requested")


def claim_job(db: Session) -> Job | None:
    """SKIP LOCKED lets several workers share the queue without stepping on each other."""
    stmt = (
        select(Job)
        .where(Job.status == "queued")
        .order_by(Job.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    job = db.execute(stmt).scalar_one_or_none()
    if job is None:
        return None
    job.status = "running"
    job.attempts += 1
    job.started_at = datetime.now(UTC)
    db.commit()
    return job


def handle_process_image(db: Session, payload: dict) -> None:
    image = db.get(ItemImage, uuid.UUID(payload["image_id"]))
    if image is None:
        log.warning("image %s vanished before processing", payload.get("image_id"))
        return

    item = db.get(Item, image.item_id)
    kind = item.kind if item else "coin"

    image.status = "processing"
    db.commit()

    result = process_image(
        resolve(image.original_path),
        item_dir(image.item_id),
        str(image.id),
        kind,
        autocrop=payload.get("autocrop"),
        autoenhance=payload.get("autoenhance"),
        manual_transform=payload.get("manual_transform"),
    )

    image.display_path = relative(result["display_path"])
    image.preview_path = relative(result["preview_path"])
    image.thumb_path = relative(result["thumb_path"])
    image.width = result["width"]
    image.height = result["height"]
    image.phash = result["phash"]
    image.detection = result["detection"]
    image.transform = result["transform"]
    image.status = "ready"
    image.error = None
    image.processed_at = datetime.now(UTC)

    if item is not None:
        db.refresh(item)
        item.completeness = compute_completeness(item)

    db.commit()
    log.info("processed image %s (%s)", image.id, result["detection"]["method"])


HANDLERS = {"process_image": handle_process_image}


def run_once(db: Session) -> bool:
    job = claim_job(db)
    if job is None:
        return False

    handler = HANDLERS.get(job.kind)
    if handler is None:
        # Retrying will never make an unknown kind known.
        job.status = "failed"
        job.error = f"unknown job kind {job.kind}"
        job.finished_at = datetime.now(UTC)
        db.commit()
        return True

    try:
        handler(db, job.payload or {})
        job.status = "done"
        job.error = None
    except Exception as exc:  # keep the worker alive whatever a single job does
        db.rollback()
        log.exception("job %s failed", job.id)
        settings = get_settings()
        job.error = f"{type(exc).__name__}: {exc}"[:2000]
        job.status = "queued" if job.attempts < settings.worker_max_attempts else "failed"
        if job.status == "failed" and job.kind == "process_image":
            image = db.get(ItemImage, uuid.UUID(job.payload["image_id"]))
            if image is not None:
                image.status = "failed"
                image.error = job.error
    finally:
        job.finished_at = datetime.now(UTC)
        db.commit()
    return True


def main() -> None:
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    interval = get_settings().worker_poll_seconds
    log.info("worker started, polling every %ss", interval)

    while _running:
        try:
            with SessionLocal() as db:
                worked = run_once(db)
        except Exception:
            log.exception("worker loop error")
            worked = False
        if not worked:
            time.sleep(interval)


if __name__ == "__main__":
    main()
