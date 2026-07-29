from __future__ import annotations

import pytest

from app.fetching import FetchError, check_url
from app.worker import run_once
from tests.conftest import coin_photo, encode_jpeg


class TestUrlGuard:
    @pytest.mark.parametrize(
        "url",
        [
            "file:///etc/passwd",
            "ftp://example.com/coin.jpg",
            "gopher://example.com/coin.jpg",
            "javascript:alert(1)",
        ],
    )
    def test_only_http_is_allowed(self, url):
        with pytest.raises(FetchError):
            check_url(url)

    @pytest.mark.parametrize(
        "url",
        [
            "http://127.0.0.1/coin.jpg",
            "http://localhost:8000/coin.jpg",
            "http://192.168.1.10/coin.jpg",
            "http://10.0.0.5/coin.jpg",
            "http://169.254.169.254/latest/meta-data/",
            "http://[::1]/coin.jpg",
        ],
    )
    def test_private_and_local_addresses_are_refused(self, url):
        with pytest.raises(FetchError):
            check_url(url)

    def test_a_url_without_a_host_is_refused(self):
        with pytest.raises(FetchError):
            check_url("http:///coin.jpg")


def _item(client, kind: str = "coin") -> str:
    return client.post("/api/items", json={"kind": kind, "country_code": "HR"}).json()["id"]


class TestImportFromUrl:
    def test_a_linked_photo_is_stored_and_queued(self, auth_client, db, monkeypatch):
        monkeypatch.setattr(
            "app.routers.images.fetch_image", lambda url, limit: encode_jpeg(coin_photo())
        )
        response = auth_client.post(
            "/api/images/from-url",
            json={"item_id": _item(auth_client), "role": "obverse", "url": "https://example.com/c.jpg"},
        )
        assert response.status_code == 201, response.text
        assert response.json()["status"] == "pending"

        run_once(db)
        image_id = response.json()["id"]
        assert auth_client.get(f"/api/images/{image_id}/thumb").status_code == 200

    def test_a_download_problem_is_reported_to_the_user(self, auth_client, monkeypatch):
        def boom(url, limit):
            raise FetchError("the image is larger than the upload limit")

        monkeypatch.setattr("app.routers.images.fetch_image", boom)
        response = auth_client.post(
            "/api/images/from-url",
            json={"item_id": _item(auth_client), "url": "https://example.com/c.jpg"},
        )
        assert response.status_code == 422
        assert "larger" in response.json()["detail"]

    def test_a_link_to_something_that_is_not_an_image_is_rejected(self, auth_client, monkeypatch):
        monkeypatch.setattr("app.routers.images.fetch_image", lambda url, limit: b"<html>hello</html>")
        response = auth_client.post(
            "/api/images/from-url",
            json={"item_id": _item(auth_client), "url": "https://example.com/page"},
        )
        assert response.status_code == 415

    def test_a_local_address_never_reaches_the_network(self, auth_client):
        response = auth_client.post(
            "/api/images/from-url",
            json={"item_id": _item(auth_client), "url": "http://127.0.0.1:8000/coin.jpg"},
        )
        assert response.status_code == 422
        assert "private" in response.json()["detail"]

    def test_an_unknown_role_is_rejected(self, auth_client):
        response = auth_client.post(
            "/api/images/from-url",
            json={"item_id": _item(auth_client), "role": "sideways", "url": "https://example.com/c.jpg"},
        )
        assert response.status_code == 422

    def test_an_unknown_item_is_rejected(self, auth_client):
        response = auth_client.post(
            "/api/images/from-url",
            json={
                "item_id": "11111111-1111-1111-1111-111111111111",
                "url": "https://example.com/c.jpg",
            },
        )
        assert response.status_code == 404

    def test_importing_needs_a_session(self, auth_client):
        item_id = _item(auth_client)
        auth_client.cookies.clear()
        response = auth_client.post(
            "/api/images/from-url",
            json={"item_id": item_id, "url": "https://example.com/c.jpg"},
        )
        assert response.status_code == 401
