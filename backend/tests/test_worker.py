from __future__ import annotations

import uuid

from sqlalchemy import select

from app.models import Country, HistoricalEntity, InstanceConfig, ItemImage, Job, User
from app.seed import get_config, seed_all, seed_countries, seed_historical_entities
from app.worker import claim_job, run_once
from tests.conftest import TEST_EMAIL, coin_photo, encode_jpeg


class TestSeeding:
    def test_all_iso_countries_are_loaded(self, db):
        assert db.scalar(select(Country).where(Country.code2 == "HR")).name == "Croatia"
        assert len(db.execute(select(Country)).scalars().all()) == 249

    def test_historical_entities_are_loaded(self, db):
        entities = db.execute(select(HistoricalEntity)).scalars().all()
        assert len(entities) > 50

    def test_seeding_is_idempotent(self, db):
        before = len(db.execute(select(Country)).scalars().all())
        seed_countries(db)
        seed_historical_entities(db)
        assert len(db.execute(select(Country)).scalars().all()) == before

    def test_seed_all_can_run_twice(self, db):
        seed_all(db)
        assert len(db.execute(select(User)).scalars().all()) == 1

    def test_initial_user_uses_the_default_language(self, db):
        user = db.scalar(select(User).where(User.email == TEST_EMAIL))
        assert user.language == "en"

    def test_instance_config_is_a_singleton(self, db):
        get_config(db)
        get_config(db)
        assert len(db.execute(select(InstanceConfig)).scalars().all()) == 1

    def test_preprovisioning_marks_setup_complete(self, db):
        config = get_config(db)
        assert config.setup_completed is True
        assert config.auth_mode == "password"


def _upload(client, kind: str = "coin") -> str:
    item = client.post("/api/items", json={"kind": kind, "country_code": "HR"}).json()
    response = client.post(
        "/api/images",
        data={"item_id": item["id"], "role": "obverse"},
        files={"file": ("coin.jpg", encode_jpeg(coin_photo()), "image/jpeg")},
    )
    assert response.status_code == 201
    return response.json()["id"]


class TestJobQueue:
    def test_empty_queue_returns_false(self, db):
        assert run_once(db) is False

    def test_claiming_marks_the_job_running(self, db):
        db.add(Job(kind="process_image", payload={"image_id": "x"}))
        db.commit()
        job = claim_job(db)
        assert job is not None
        assert job.status == "running"
        assert job.attempts == 1

    def test_a_claimed_job_is_not_handed_out_twice(self, db):
        db.add(Job(kind="process_image", payload={"image_id": "x"}))
        db.commit()
        assert claim_job(db) is not None
        assert claim_job(db) is None

    def test_unknown_job_kind_fails_cleanly(self, db):
        db.add(Job(kind="teleport", payload={}))
        db.commit()
        run_once(db)
        assert db.execute(select(Job)).scalars().first().status == "failed"


class TestImageProcessing:
    def test_image_becomes_ready(self, auth_client, db):
        image_id = uuid.UUID(_upload(auth_client))
        assert run_once(db) is True

        db.expire_all()
        image = db.get(ItemImage, image_id)
        assert image.status == "ready"
        assert image.thumb_path and image.preview_path and image.display_path
        assert image.phash
        assert image.width > 0

    def test_detection_and_transform_are_recorded(self, auth_client, db):
        image_id = uuid.UUID(_upload(auth_client))
        run_once(db)
        db.expire_all()
        image = db.get(ItemImage, image_id)
        assert image.detection["shape"] == "circle"
        assert "crop" in image.transform

    def test_the_job_is_marked_done(self, auth_client, db):
        _upload(auth_client)
        run_once(db)
        assert db.execute(select(Job)).scalars().first().status == "done"

    def test_completeness_is_recomputed_after_processing(self, auth_client, db):
        item = auth_client.post("/api/items", json={"kind": "coin", "country_code": "HR"}).json()
        before = item["completeness"]
        auth_client.post(
            "/api/images",
            data={"item_id": item["id"], "role": "obverse"},
            files={"file": ("coin.jpg", encode_jpeg(coin_photo()), "image/jpeg")},
        )
        run_once(db)
        after = auth_client.get(f"/api/items/{item['id']}").json()["completeness"]
        assert after > before

    def test_a_broken_image_eventually_fails(self, auth_client, db):
        from app.config import get_settings
        from app.storage import resolve

        image_id = uuid.UUID(_upload(auth_client))
        image = db.get(ItemImage, image_id)
        resolve(image.original_path).write_bytes(b"\xff\xd8\xff\xe0 corrupted")
        db.expire_all()

        for _ in range(get_settings().worker_max_attempts + 1):
            run_once(db)

        db.expire_all()
        assert db.get(ItemImage, image_id).status == "failed"
        assert db.execute(select(Job)).scalars().first().status == "failed"

    def test_a_failing_job_is_retried_before_it_fails(self, auth_client, db):
        from app.storage import resolve

        image_id = uuid.UUID(_upload(auth_client))
        resolve(db.get(ItemImage, image_id).original_path).write_bytes(b"\xff\xd8\xff\xe0 corrupted")
        db.expire_all()

        run_once(db)
        db.expire_all()
        job = db.execute(select(Job)).scalars().first()
        assert job.status == "queued"
        assert job.attempts == 1

    def test_reprocess_regenerates_the_derivatives(self, auth_client, db):
        image_id = _upload(auth_client)
        run_once(db)
        db.expire_all()
        first = db.get(ItemImage, uuid.UUID(image_id)).phash

        auth_client.post(f"/api/images/{image_id}/reprocess", json={"autocrop": False})
        run_once(db)
        db.expire_all()

        image = db.get(ItemImage, uuid.UUID(image_id))
        assert image.status == "ready"
        assert image.phash != first
