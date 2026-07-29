from __future__ import annotations

from sqlalchemy import select

from app.models import SessionToken, User
from tests.conftest import TEST_EMAIL, TEST_PASSWORD


class TestLogin:
    def test_valid_credentials_return_user_and_cookie(self, client):
        response = client.post("/api/auth/login", json={"email": TEST_EMAIL, "password": TEST_PASSWORD})
        assert response.status_code == 200
        assert response.json()["email"] == TEST_EMAIL
        assert client.cookies.get("kolektor_session")

    def test_email_match_is_case_insensitive(self, client):
        response = client.post(
            "/api/auth/login", json={"email": TEST_EMAIL.upper(), "password": TEST_PASSWORD}
        )
        assert response.status_code == 200

    def test_wrong_password_is_rejected(self, client):
        response = client.post("/api/auth/login", json={"email": TEST_EMAIL, "password": "nope"})
        assert response.status_code == 401
        assert response.json()["detail"] == "invalid credentials"

    def test_unknown_user_gives_the_same_error(self, client):
        response = client.post("/api/auth/login", json={"email": "ghost@example.com", "password": "nope"})
        assert response.status_code == 401
        assert response.json()["detail"] == "invalid credentials"

    def test_malformed_email_is_rejected_by_validation(self, client):
        assert client.post("/api/auth/login", json={"email": "bad", "password": "x"}).status_code == 422

    def test_repeated_failures_are_rate_limited(self, client):
        for _ in range(8):
            client.post("/api/auth/login", json={"email": TEST_EMAIL, "password": "wrong"})
        blocked = client.post("/api/auth/login", json={"email": TEST_EMAIL, "password": TEST_PASSWORD})
        assert blocked.status_code == 429

    def test_sql_injection_in_email_does_not_authenticate(self, client):
        response = client.post(
            "/api/auth/login",
            json={"email": "tester@example.com' OR '1'='1", "password": "x"},
        )
        assert response.status_code in (401, 422)


class TestSession:
    def test_me_returns_current_user(self, auth_client):
        assert auth_client.get("/api/auth/me").json()["email"] == TEST_EMAIL

    def test_logout_revokes_the_session(self, auth_client, db):
        assert auth_client.post("/api/auth/logout").status_code == 204
        assert auth_client.get("/api/auth/me").status_code == 401
        assert db.execute(select(SessionToken)).scalars().first() is None

    def test_raw_token_is_not_stored_in_the_database(self, auth_client, db):
        raw = auth_client.cookies.get("kolektor_session")
        stored = db.execute(select(SessionToken)).scalars().all()
        assert stored
        assert all(row.token_hash != raw for row in stored)


class TestLanguagePreference:
    def test_default_language_is_english(self, auth_client):
        assert auth_client.get("/api/auth/me").json()["language"] == "en"

    def test_user_can_switch_to_croatian(self, auth_client):
        response = auth_client.patch("/api/auth/me", json={"language": "hr"})
        assert response.status_code == 200
        assert response.json()["language"] == "hr"
        assert auth_client.get("/api/auth/me").json()["language"] == "hr"

    def test_unsupported_language_is_rejected(self, auth_client):
        assert auth_client.patch("/api/auth/me", json={"language": "de"}).status_code == 422

    def test_config_advertises_both_languages(self, client):
        assert client.get("/api/config").json()["languages"] == ["en", "hr"]


class TestPasswordChange:
    def test_password_can_be_changed(self, auth_client, client):
        response = auth_client.post(
            "/api/auth/password",
            json={"current_password": TEST_PASSWORD, "new_password": "BrandNewPassword9"},
        )
        assert response.status_code == 204

        client.cookies.clear()
        assert client.post(
            "/api/auth/login", json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        ).status_code == 401
        assert client.post(
            "/api/auth/login", json={"email": TEST_EMAIL, "password": "BrandNewPassword9"}
        ).status_code == 200

    def test_wrong_current_password_is_refused(self, auth_client):
        response = auth_client.post(
            "/api/auth/password",
            json={"current_password": "wrong", "new_password": "BrandNewPassword9"},
        )
        assert response.status_code == 403

    def test_short_password_is_refused(self, auth_client):
        response = auth_client.post(
            "/api/auth/password", json={"current_password": TEST_PASSWORD, "new_password": "short"}
        )
        assert response.status_code == 422

    def test_reusing_the_same_password_is_refused(self, auth_client):
        response = auth_client.post(
            "/api/auth/password",
            json={"current_password": TEST_PASSWORD, "new_password": TEST_PASSWORD},
        )
        assert response.status_code == 422

    def test_other_sessions_are_invalidated(self, client, db):
        first = client.post("/api/auth/login", json={"email": TEST_EMAIL, "password": TEST_PASSWORD})
        assert first.status_code == 200
        stale_cookie = client.cookies.get("kolektor_session")

        client.post(
            "/api/auth/password",
            json={"current_password": TEST_PASSWORD, "new_password": "BrandNewPassword9"},
        )

        client.cookies.clear()
        client.cookies.set("kolektor_session", stale_cookie)
        assert client.get("/api/auth/me").status_code == 401
        assert db.execute(select(SessionToken)).scalars().first() is not None


class TestSingleUser:
    def test_only_one_account_exists_after_seeding(self, db):
        assert len(db.execute(select(User)).scalars().all()) == 1

    def test_seeding_twice_does_not_add_a_second_user(self, db):
        from app.seed import seed_initial_user

        assert seed_initial_user(db) is None
        assert len(db.execute(select(User)).scalars().all()) == 1

    def test_there_is_no_registration_endpoint(self, client):
        for path in ("/api/auth/register", "/api/auth/signup", "/api/users"):
            assert client.post(path, json={}).status_code in (404, 405)
