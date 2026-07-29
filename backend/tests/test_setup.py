"""First-run experience: choose password protection or no login, and switch later."""

from __future__ import annotations


class TestFirstRunStatus:
    def test_fresh_instance_reports_setup_required(self, unconfigured_client):
        body = unconfigured_client.get("/api/auth/setup").json()
        assert body["setup_required"] is True
        assert body["languages"] == ["en", "hr"]

    def test_status_endpoint_is_public(self, unconfigured_client):
        assert unconfigured_client.get("/api/auth/setup").status_code == 200

    def test_api_is_locked_until_setup_is_done(self, unconfigured_client):
        response = unconfigured_client.get("/api/items")
        assert response.status_code == 409
        assert response.json()["detail"] == "setup_required"

    def test_preprovisioned_instance_skips_setup(self, client):
        body = client.get("/api/auth/setup").json()
        assert body["setup_required"] is False
        assert body["auth_mode"] == "password"


class TestSetupWithPassword:
    def test_creates_the_account_and_logs_in(self, unconfigured_client):
        response = unconfigured_client.post(
            "/api/auth/setup",
            json={
                "auth_mode": "password",
                "email": "owner@example.com",
                "password": "FirstRunPassword1",
                "language": "hr",
            },
        )
        assert response.status_code == 201
        assert response.json()["email"] == "owner@example.com"
        assert response.json()["language"] == "hr"
        assert unconfigured_client.get("/api/auth/me").status_code == 200

    def test_password_mode_requires_credentials(self, unconfigured_client):
        response = unconfigured_client.post("/api/auth/setup", json={"auth_mode": "password"})
        assert response.status_code == 422

    def test_short_password_is_rejected(self, unconfigured_client):
        response = unconfigured_client.post(
            "/api/auth/setup",
            json={"auth_mode": "password", "email": "owner@example.com", "password": "short"},
        )
        assert response.status_code == 422

    def test_setup_cannot_be_replayed(self, unconfigured_client):
        payload = {
            "auth_mode": "password",
            "email": "owner@example.com",
            "password": "FirstRunPassword1",
        }
        assert unconfigured_client.post("/api/auth/setup", json=payload).status_code == 201
        assert unconfigured_client.post("/api/auth/setup", json=payload).status_code == 409

    def test_setup_cannot_be_replayed_by_an_anonymous_caller(self, client):
        client.cookies.clear()
        response = client.post(
            "/api/auth/setup",
            json={"auth_mode": "password", "email": "attacker@example.com", "password": "Takeover12345"},
        )
        assert response.status_code == 409
        assert client.post(
            "/api/auth/login", json={"email": "attacker@example.com", "password": "Takeover12345"}
        ).status_code == 401


class TestSetupWithoutLogin:
    def test_open_mode_needs_no_credentials(self, unconfigured_client):
        response = unconfigured_client.post("/api/auth/setup", json={"auth_mode": "open"})
        assert response.status_code == 201

    def test_open_mode_grants_access_without_a_cookie(self, unconfigured_client):
        unconfigured_client.post("/api/auth/setup", json={"auth_mode": "open"})
        unconfigured_client.cookies.clear()
        assert unconfigured_client.get("/api/items").status_code == 200
        assert unconfigured_client.get("/api/auth/me").status_code == 200

    def test_login_is_unavailable_in_open_mode(self, unconfigured_client):
        unconfigured_client.post("/api/auth/setup", json={"auth_mode": "open"})
        response = unconfigured_client.post(
            "/api/auth/login", json={"email": "someone@example.com", "password": "anything123"}
        )
        assert response.status_code == 409

    def test_language_choice_is_kept_in_open_mode(self, unconfigured_client):
        unconfigured_client.post("/api/auth/setup", json={"auth_mode": "open", "language": "hr"})
        assert unconfigured_client.get("/api/auth/me").json()["language"] == "hr"


class TestSwitchingModeLater:
    def test_password_instance_can_drop_to_open(self, auth_client):
        response = auth_client.post("/api/auth/mode", json={"auth_mode": "open"})
        assert response.status_code == 200
        assert response.json()["auth_mode"] == "open"

        auth_client.cookies.clear()
        assert auth_client.get("/api/items").status_code == 200

    def test_open_instance_can_be_locked_down_again(self, unconfigured_client):
        unconfigured_client.post("/api/auth/setup", json={"auth_mode": "open"})
        response = unconfigured_client.post(
            "/api/auth/mode",
            json={"auth_mode": "password", "email": "owner@example.com", "password": "LockItDown12"},
        )
        assert response.status_code == 200
        assert response.json()["auth_mode"] == "password"

        unconfigured_client.cookies.clear()
        assert unconfigured_client.get("/api/items").status_code == 401
        assert unconfigured_client.post(
            "/api/auth/login", json={"email": "owner@example.com", "password": "LockItDown12"}
        ).status_code == 200

    def test_locking_down_requires_credentials(self, auth_client):
        assert auth_client.post("/api/auth/mode", json={"auth_mode": "password"}).status_code == 422

    def test_locking_down_rejects_a_weak_password(self, auth_client):
        response = auth_client.post(
            "/api/auth/mode",
            json={"auth_mode": "password", "email": "owner@example.com", "password": "weak"},
        )
        assert response.status_code == 422

    def test_anonymous_caller_cannot_change_the_mode(self, client):
        client.cookies.clear()
        assert client.post("/api/auth/mode", json={"auth_mode": "open"}).status_code == 401

    def test_collection_survives_a_mode_change(self, auth_client):
        auth_client.post("/api/items", json={"kind": "coin", "country_code": "HR"})
        auth_client.post("/api/auth/mode", json={"auth_mode": "open"})
        auth_client.cookies.clear()
        assert auth_client.get("/api/items").json()["total"] == 1
