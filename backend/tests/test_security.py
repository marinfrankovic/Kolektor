"""Security-focused tests: hashing, session tokens, path traversal, headers, authz."""

from __future__ import annotations

import uuid

import pytest

from app.security import (
    constant_time_equals,
    hash_password,
    hash_session_token,
    needs_rehash,
    new_session_token,
    verify_password,
)
from app.storage import resolve, sniff_mime


class TestPasswordHashing:
    def test_hash_is_argon2id_and_not_the_plaintext(self):
        digest = hash_password("CorrectHorseBattery1")
        assert digest.startswith("$argon2id$")
        assert "CorrectHorseBattery1" not in digest

    def test_same_password_hashes_differently_each_time(self):
        assert hash_password("CorrectHorseBattery1") != hash_password("CorrectHorseBattery1")

    def test_verify_accepts_correct_password(self):
        assert verify_password(hash_password("CorrectHorseBattery1"), "CorrectHorseBattery1")

    def test_verify_rejects_wrong_password(self):
        assert not verify_password(hash_password("CorrectHorseBattery1"), "wrong")

    def test_verify_rejects_garbage_hash_without_raising(self):
        assert verify_password("not-a-hash", "anything") is False
        assert verify_password("", "anything") is False

    def test_needs_rehash_is_true_for_invalid_hash(self):
        assert needs_rehash("not-a-hash") is True

    def test_needs_rehash_is_false_for_fresh_hash(self):
        assert needs_rehash(hash_password("CorrectHorseBattery1")) is False


class TestSessionTokens:
    def test_tokens_are_long_and_unique(self):
        tokens = {new_session_token() for _ in range(200)}
        assert len(tokens) == 200
        assert all(len(t) >= 43 for t in tokens)

    def test_token_hash_is_keyed_and_stable(self):
        token = new_session_token()
        assert hash_session_token(token, "k1") == hash_session_token(token, "k1")
        assert hash_session_token(token, "k1") != hash_session_token(token, "k2")

    def test_token_hash_does_not_leak_the_token(self):
        token = new_session_token()
        assert token not in hash_session_token(token, "secret")

    def test_constant_time_equals(self):
        assert constant_time_equals("abc", "abc")
        assert not constant_time_equals("abc", "abd")


class TestMediaPathSafety:
    @pytest.mark.parametrize(
        "evil",
        [
            "../../etc/passwd",
            "../../../etc/shadow",
            "a/../../../../etc/passwd",
            "/etc/passwd",
            "..\\..\\windows\\system32\\config\\sam",
        ],
    )
    def test_traversal_attempts_are_rejected(self, db, evil):  # noqa: ARG002
        with pytest.raises(ValueError, match="escapes media root"):
            resolve(evil)

    def test_normal_relative_path_is_allowed(self, db):  # noqa: ARG002
        assert resolve("ab/cd/file.jpg").name == "file.jpg"


class TestMagicByteSniffing:
    def test_detects_real_types(self):
        assert sniff_mime(b"\xff\xd8\xff\xe0rest") == "image/jpeg"
        assert sniff_mime(b"\x89PNG\r\n\x1a\nrest") == "image/png"
        assert sniff_mime(b"RIFF____WEBPVP8 ") == "image/webp"

    def test_rejects_scripts_and_archives(self):
        assert sniff_mime(b"<?php system($_GET['c']); ?>") is None
        assert sniff_mime(b"#!/bin/sh\nrm -rf /") is None
        assert sniff_mime(b"PK\x03\x04") is None
        assert sniff_mime(b"") is None


class TestAuthorisation:
    ENDPOINTS = [
        ("get", "/api/items"),
        ("post", "/api/items"),
        ("get", "/api/stats/summary"),
        ("get", "/api/stats/map"),
        ("get", "/api/reference/countries"),
        ("get", "/api/reference/historical-entities"),
        ("get", "/api/auth/me"),
    ]

    @pytest.mark.parametrize(("method", "path"), ENDPOINTS)
    def test_protected_endpoints_reject_anonymous(self, client, method, path):
        response = client.request(method.upper(), path)
        assert response.status_code == 401

    def test_item_detail_rejects_anonymous(self, client):
        response = client.get(f"/api/items/{uuid.uuid4()}")
        assert response.status_code == 401

    def test_forged_session_cookie_is_rejected(self, client):
        client.cookies.set("kolektor_session", "totally-made-up-token")
        assert client.get("/api/auth/me").status_code == 401

    def test_health_and_config_stay_public(self, client):
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/config").status_code == 200


class TestSecurityHeaders:
    def test_hardening_headers_are_present(self, client):
        headers = client.get("/api/health").headers
        assert headers["X-Content-Type-Options"] == "nosniff"
        assert headers["X-Frame-Options"] == "DENY"
        assert headers["Referrer-Policy"] == "no-referrer"
        assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
        assert "default-src 'self'" in headers["Content-Security-Policy"]

    def test_no_hsts_when_tls_is_not_terminated(self, client):
        # The app must stay usable on a plain-HTTP LAN with no domain and no proxy.
        assert "Strict-Transport-Security" not in client.get("/api/health").headers

    def test_session_cookie_is_httponly(self, client):
        response = client.post(
            "/api/auth/login",
            json={"email": "tester@example.com", "password": "TestPassword123"},
        )
        assert response.status_code == 200
        set_cookie = response.headers["set-cookie"]
        assert "HttpOnly" in set_cookie
        assert "SameSite=lax" in set_cookie.replace("samesite", "SameSite")
