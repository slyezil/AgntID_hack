from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from counteroffer_api.app import ApiSettings, TurnExecutionResult, create_app
from counteroffer_api.turn_store import TurnStore

ROOT = Path(__file__).parents[2]


def make_store(path: Path) -> TurnStore:
    store = TurnStore(path, ROOT / "contracts" / "application.schema.sql")
    store.migrate()
    return store


def make_settings(tmp_path: Path) -> ApiSettings:
    return ApiSettings(
        public_origin="http://127.0.0.1:8000",
        cookie_secure=False,
        application_db_path=tmp_path / "application.db",
        schema_path=ROOT / "contracts" / "application.schema.sql",
        worker_poll_seconds=0.01,
    )


def issue_invite(store: TurnStore, code: str, buyer_id: str) -> None:
    store.create_invite(
        code_hash=hashlib.sha256(code.encode()).hexdigest(),
        merchant_id="MERCHANT-01",
        buyer_id=buyer_id,
        expires_at=(datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
    )


def sign_in(client: TestClient, code: str) -> tuple[str, str]:
    response = client.post(
        "/api/session",
        headers={"Origin": "http://127.0.0.1:8000"},
        json={"code": code},
    )
    assert response.status_code == 200
    assert response.headers["set-cookie"].lower().find("httponly") >= 0
    assert "samesite=lax" in response.headers["set-cookie"].lower()
    return response.json()["csrf_token"], response.json()["buyer_id"]


@pytest.mark.contract
def test_invite_is_single_use_origin_checked_and_session_csrf_rotates(tmp_path):
    store = make_store(tmp_path / "application.db")
    issue_invite(store, "long-one-time-invite-code", "BUYER-A")
    app = create_app(make_settings(tmp_path), store=store)
    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        bad_origin = client.post(
            "/api/session",
            headers={"Origin": "https://attacker.example"},
            json={"code": "long-one-time-invite-code"},
        )
        assert bad_origin.status_code == 403

        old_csrf, buyer_id = sign_in(client, "long-one-time-invite-code")
        assert buyer_id == "BUYER-A"
        replay = client.post(
            "/api/session",
            headers={"Origin": "http://127.0.0.1:8000"},
            json={"code": "long-one-time-invite-code"},
        )
        assert replay.status_code == 401

        refreshed = client.get("/api/session")
        assert refreshed.status_code == 200
        new_csrf = refreshed.json()["csrf_token"]
        assert new_csrf != old_csrf
        stale_write = client.post(
            "/api/conversations",
            headers={
                "Origin": "http://127.0.0.1:8000",
                "X-CSRF-Token": old_csrf,
            },
        )
        assert stale_write.status_code == 403
        accepted = client.post(
            "/api/conversations",
            headers={
                "Origin": "http://127.0.0.1:8000",
                "X-CSRF-Token": new_csrf,
            },
        )
        assert accepted.status_code == 201


@pytest.mark.contract
def test_host_origin_and_buyer_scope_are_enforced(tmp_path):
    store = make_store(tmp_path / "application.db")
    issue_invite(store, "invite-code-for-buyer-a", "BUYER-A")
    issue_invite(store, "invite-code-for-buyer-b", "BUYER-B")
    app = create_app(make_settings(tmp_path), store=store)
    with TestClient(app, base_url="http://127.0.0.1:8000") as buyer_a:
        csrf_a, _ = sign_in(buyer_a, "invite-code-for-buyer-a")
        conversation = buyer_a.post(
            "/api/conversations",
            headers={
                "Origin": "http://127.0.0.1:8000",
                "X-CSRF-Token": csrf_a,
            },
        ).json()["conversation_id"]
        invalid_host = buyer_a.get("/healthz", headers={"Host": "attacker.example"})
        assert invalid_host.status_code == 400
        with TestClient(app, base_url="http://127.0.0.1:8000") as buyer_b:
            sign_in(buyer_b, "invite-code-for-buyer-b")
            hidden = buyer_b.get(f"/api/conversations/{conversation}")
            assert hidden.status_code == 404
            assert hidden.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.contract
def test_turn_submit_is_idempotent_and_sse_reconnect_replays_events(tmp_path):
    store = make_store(tmp_path / "application.db")
    issue_invite(store, "invite-code-for-buyer-a", "BUYER-A")

    # MOCK: injected test executor; this does not call Bedrock, AgntID, or Shopify.
    async def executor(context: dict[str, str]) -> TurnExecutionResult:
        assert context["buyer_id"] == "BUYER-A"
        await asyncio.sleep(0.02)
        return TurnExecutionResult(
            text="I found the supported packaging options.", active_task_id="task-ref"
        )

    app = create_app(make_settings(tmp_path), store=store, turn_executor=executor)
    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        csrf, _ = sign_in(client, "invite-code-for-buyer-a")
        conversation = client.post(
            "/api/conversations",
            headers={
                "Origin": "http://127.0.0.1:8000",
                "X-CSRF-Token": csrf,
            },
        ).json()["conversation_id"]
        headers = {"Origin": "http://127.0.0.1:8000", "X-CSRF-Token": csrf}
        body = {
            "client_request_id": "de305d54-75b4-431b-adb2-eb6b9e546014",
            "text": "Find carton sizes",
        }
        first = client.post(f"/api/conversations/{conversation}/turns", headers=headers, json=body)
        assert first.status_code == 202
        turn_id = first.json()["turn_id"]
        retry = client.post(f"/api/conversations/{conversation}/turns", headers=headers, json=body)
        assert retry.status_code == 202
        assert retry.json()["turn_id"] == turn_id
        conflict = client.post(
            f"/api/conversations/{conversation}/turns",
            headers=headers,
            json={
                "client_request_id": "de305d54-75b4-431b-adb2-eb6b9e546014",
                "text": "Different request",
            },
        )
        assert conflict.status_code == 409

        for _ in range(40):
            result = client.get(f"/api/turns/{turn_id}")
            if result.json()["status"] == "COMPLETED":
                break
            asyncio.run(asyncio.sleep(0.01))
        assert result.json()["status"] == "COMPLETED"
        stream = client.get(f"/api/turns/{turn_id}/events", headers={"Last-Event-ID": "1"})
        assert stream.status_code == 200
        assert "event: turn_started" in stream.text
        assert "event: assistant_delta" in stream.text
        assert "event: turn_completed" in stream.text


@pytest.mark.contract
def test_turns_fail_closed_without_agent_dependencies(tmp_path):
    store = make_store(tmp_path / "application.db")
    issue_invite(store, "invite-code-for-buyer-a", "BUYER-A")
    app = create_app(make_settings(tmp_path), store=store)
    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        csrf, _ = sign_in(client, "invite-code-for-buyer-a")
        conversation = client.post(
            "/api/conversations",
            headers={
                "Origin": "http://127.0.0.1:8000",
                "X-CSRF-Token": csrf,
            },
        ).json()["conversation_id"]
        response = client.post(
            f"/api/conversations/{conversation}/turns",
            headers={"Origin": "http://127.0.0.1:8000", "X-CSRF-Token": csrf},
            json={
                "client_request_id": "de305d54-75b4-431b-adb2-eb6b9e546014",
                "text": "Find cartons",
            },
        )
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "AGENT_UNAVAILABLE"


@pytest.mark.contract
def test_invalid_invites_are_rate_limited(tmp_path):
    app = create_app(make_settings(tmp_path), store=make_store(tmp_path / "application.db"))
    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        for _ in range(5):
            response = client.post(
                "/api/session",
                headers={"Origin": "http://127.0.0.1:8000"},
                json={"code": "this-is-a-long-invalid-invite"},
            )
            assert response.status_code == 401
        limited = client.post(
            "/api/session",
            headers={"Origin": "http://127.0.0.1:8000"},
            json={"code": "this-is-a-long-invalid-invite"},
        )
        assert limited.status_code == 429


@pytest.mark.contract
def test_built_web_assets_are_served_same_origin_when_present(tmp_path):
    web_dist = ROOT / "web" / "dist"
    if not web_dist.is_dir():
        pytest.skip("run npm run build before checking static web serving")
    app = create_app(make_settings(tmp_path), store=make_store(tmp_path / "application.db"))
    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "CounterOffer" in response.text
        assert "no-store" in response.headers["cache-control"]
