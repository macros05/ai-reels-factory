"""Auth + /api/* protection tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from src.api.auth import create_token
from src.config import settings


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(settings, "app_password", "test-password")
    monkeypatch.setattr(settings, "jwt_secret", "test-jwt-secret-very-long")

    import src.api.main as api_main

    api_main._RUN_STATE.clear()
    api_main.limiter.reset()
    return TestClient(api_main.app)


# ---------------------------------------------------------------------------
# login
# ---------------------------------------------------------------------------


def test_login_with_correct_password_returns_token(client: TestClient) -> None:
    r = client.post("/api/auth/login", json={"password": "test-password"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "token" in body and body["token"]
    assert "expires_at" in body


def test_login_with_wrong_password_returns_401(client: TestClient) -> None:
    r = client.post("/api/auth/login", json={"password": "nope"})
    assert r.status_code == 401


def test_login_rate_limited_after_five_attempts(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    for _ in range(5):
        client.post("/api/auth/login", json={"password": "nope"})
    r = client.post("/api/auth/login", json={"password": "nope"})
    assert r.status_code == 429


# ---------------------------------------------------------------------------
# /api/auth/me
# ---------------------------------------------------------------------------


def test_me_returns_200_with_valid_token(client: TestClient) -> None:
    token, _ = create_token()
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["sub"] == "owner"


def test_me_returns_401_without_token(client: TestClient) -> None:
    r = client.get("/api/auth/me")
    assert r.status_code == 401


def test_me_returns_401_with_invalid_token(client: TestClient) -> None:
    r = client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert r.status_code == 401


def test_me_returns_401_with_expired_token(client: TestClient) -> None:
    expired = jwt.encode(
        {
            "sub": "owner",
            "iat": int((datetime.now(UTC) - timedelta(days=30)).timestamp()),
            "exp": int((datetime.now(UTC) - timedelta(days=1)).timestamp()),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# protected endpoints
# ---------------------------------------------------------------------------


def test_api_runs_requires_auth(client: TestClient) -> None:
    r = client.get("/api/runs")
    assert r.status_code == 401


def test_api_runs_returns_list_with_token(client: TestClient) -> None:
    token, _ = create_token()
    r = client.get("/api/runs", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert "runs" in r.json()


def test_api_providers_returns_full_catalog(client: TestClient) -> None:
    token, _ = create_token()
    r = client.get("/api/providers", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    ids = {p["id"] for p in body["available"]}
    assert ids == {"veo", "kling", "seedance", "cinematic_studio_v2"}


# ---------------------------------------------------------------------------
# /api/output/* — JWT-gated file serving (header or ?token=…)
# ---------------------------------------------------------------------------


def test_output_requires_auth(
    client: TestClient, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "output_dir", tmp_path)
    run_dir = tmp_path / "20260101-000000"
    run_dir.mkdir()
    (run_dir / "video.mp4").write_bytes(b"mp4")

    r = client.get("/api/output/20260101-000000/video.mp4")
    assert r.status_code == 401


def test_output_via_bearer_header(
    client: TestClient, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "output_dir", tmp_path)
    run_dir = tmp_path / "20260101-000000"
    run_dir.mkdir()
    (run_dir / "video.mp4").write_bytes(b"mp4")

    token, _ = create_token()
    r = client.get(
        "/api/output/20260101-000000/video.mp4",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.content == b"mp4"


def test_output_via_query_param_token(
    client: TestClient, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`<video src='…?token=…'>` use case."""
    monkeypatch.setattr(settings, "output_dir", tmp_path)
    run_dir = tmp_path / "20260101-000000"
    run_dir.mkdir()
    (run_dir / "video.mp4").write_bytes(b"mp4")

    token, _ = create_token()
    r = client.get(f"/api/output/20260101-000000/video.mp4?token={token}")
    assert r.status_code == 200


def test_output_rejects_unlisted_filenames(client: TestClient) -> None:
    token, _ = create_token()
    r = client.get(
        "/api/output/20260101-000000/secret.env",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 404


def test_output_rejects_path_traversal(
    client: TestClient, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "output_dir", tmp_path)
    token, _ = create_token()
    r = client.get(
        "/api/output/..%2F..%2Fetc/video.mp4",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code in {400, 404}


# ---------------------------------------------------------------------------
# /api/runs/{id} flow
# ---------------------------------------------------------------------------


def test_run_detail_returns_404_for_unknown(client: TestClient) -> None:
    token, _ = create_token()
    r = client.get("/api/runs/nonexistent", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 404


def test_run_detail_serves_caption_text(
    client: TestClient, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.models import RunResult, RunStatus

    monkeypatch.setattr(settings, "output_dir", tmp_path)
    run_id = "20260101-000000"
    run_dir = tmp_path / run_id
    run_dir.mkdir()
    result = RunResult(
        run_id=run_id,
        topic="t",
        status=RunStatus.DONE,
        output_dir=run_dir,
        provider="seedance",
    )
    (run_dir / "result.json").write_text(result.model_dump_json(), encoding="utf-8")
    (run_dir / "caption.txt").write_text("hola #reels", encoding="utf-8")

    token, _ = create_token()
    r = client.get(f"/api/runs/{run_id}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["caption"] == "hola #reels"
    assert body["provider"] == "seedance"
    assert body["cost_credits"] == 50


# unused import suppression
_ = json
