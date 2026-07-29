"""Test environment is configured before any app module is imported so the SQLite
test database and throwaway media root are picked up by app.config."""

from __future__ import annotations

import io
import os
import shutil
import tempfile
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

TEST_ROOT = Path(tempfile.mkdtemp(prefix="kolektor-tests-"))
TEST_EMAIL = "tester@example.com"
TEST_PASSWORD = "TestPassword123"

os.environ["KOLEKTOR_DATABASE_URL"] = f"sqlite+pysqlite:///{(TEST_ROOT / 'test.db').as_posix()}"
os.environ["KOLEKTOR_MEDIA_ROOT"] = str(TEST_ROOT / "media")
os.environ["KOLEKTOR_STATIC_ROOT"] = str(TEST_ROOT / "static-does-not-exist")
os.environ["KOLEKTOR_SECRET_KEY"] = "unit-test-secret-key-not-for-production"
os.environ["KOLEKTOR_INITIAL_USER_EMAIL"] = TEST_EMAIL
os.environ["KOLEKTOR_INITIAL_USER_PASSWORD"] = TEST_PASSWORD
os.environ["KOLEKTOR_ENABLE_OCR"] = "false"
os.environ["KOLEKTOR_ENABLE_REMBG"] = "false"
os.environ["KOLEKTOR_COOKIE_SECURE"] = "false"
os.environ["KOLEKTOR_BEHIND_PROXY"] = "false"

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import event  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402
from app.seed import seed_all  # noqa: E402


@event.listens_for(engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, _record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def pytest_sessionfinish(session, exitstatus):  # noqa: ARG001
    engine.dispose()
    shutil.rmtree(TEST_ROOT, ignore_errors=True)


def _reset_schema() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    media = Path(os.environ["KOLEKTOR_MEDIA_ROOT"])
    shutil.rmtree(media, ignore_errors=True)
    media.mkdir(parents=True, exist_ok=True)


@pytest.fixture
def db():
    _reset_schema()
    with SessionLocal() as session:
        seed_all(session)
    with SessionLocal() as session:
        yield session
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db):  # noqa: ARG001
    with TestClient(app, base_url="http://testserver") as test_client:
        yield test_client


@pytest.fixture
def auth_client(client):
    response = client.post(
        "/api/auth/login", json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200, response.text
    return client


@pytest.fixture
def unconfigured_client():
    """A brand-new instance with no pre-provisioned credentials, i.e. the first-run state."""
    settings = get_settings()
    original = (settings.initial_user_email, settings.initial_user_password)
    settings.initial_user_email = ""
    settings.initial_user_password = ""
    _reset_schema()
    try:
        with TestClient(app, base_url="http://testserver") as test_client:
            yield test_client
    finally:
        settings.initial_user_email, settings.initial_user_password = original
        Base.metadata.drop_all(bind=engine)


# --- synthetic image helpers -------------------------------------------------


def coin_photo(size: int = 700) -> np.ndarray:
    """Dark background with a bright off-centre disc, i.e. a stylised coin photo."""
    import cv2

    canvas = np.full((size, size, 3), 40, dtype=np.uint8)
    centre = (size // 2, size // 2)
    radius = int(size * 0.32)
    cv2.circle(canvas, centre, radius, (200, 195, 170), -1)
    cv2.circle(canvas, centre, int(radius * 0.85), (170, 165, 140), 3)
    cv2.putText(canvas, "5", (centre[0] - 30, centre[1] + 25), cv2.FONT_HERSHEY_SIMPLEX, 2.0, (60, 60, 60), 6)
    return canvas


def banknote_photo(width: int = 900, height: int = 600) -> np.ndarray:
    import cv2

    canvas = np.full((height, width, 3), 30, dtype=np.uint8)
    cv2.rectangle(canvas, (90, 130), (width - 90, height - 130), (215, 210, 200), -1)
    cv2.rectangle(canvas, (110, 150), (width - 110, height - 150), (150, 145, 135), 3)
    return canvas


def encode_jpeg(array: np.ndarray) -> bytes:
    buffer = io.BytesIO()
    Image.fromarray(array[:, :, ::-1]).save(buffer, format="JPEG", quality=92)
    return buffer.getvalue()


@pytest.fixture
def coin_jpeg() -> bytes:
    return encode_jpeg(coin_photo())


@pytest.fixture
def banknote_jpeg() -> bytes:
    return encode_jpeg(banknote_photo())
