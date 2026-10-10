from __future__ import annotations

import json

import httpx

from game_tenant_service.game_backend import ModerationSubmission, decide_moderation
from game_tenant_service.infrai_client import InfraiClient, InfraiError
from game_tenant_service.tenant_lifecycle import TenantAccount, offboard_tenant, onboard_tenant


def test_reported_personal_asset_enters_priority_queue() -> None:
    decision = decide_moderation(
        ModerationSubmission(
            tenant_id="starfall",
            asset_id="avatar-42",
            reports=1,
            contains_personal_data=True,
        )
    )
    assert decision.queue == "priority"
    assert decision.publish_state == "held"


def test_offboarding_deletes_user_and_revokes_key() -> None:
    calls: list[tuple[str, str, bytes]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path, request.content))
        return httpx.Response(200, json={"ok": True, "data": {}, "error": None, "metadata": {}})

    client = InfraiClient("test-key", transport=httpx.MockTransport(handler))
    result = offboard_tenant(
        client,
        TenantAccount("starfall", "user-7", "key-9", "one-time-secret"),
    )

    assert result == {"user": "deleted", "key": "revoked"}
    assert [(method, path) for method, path, _ in calls] == [
        ("DELETE", "/v1/auth/user/delete/user-7"),
        ("DELETE", "/v1/account/keys/revoke/key-9"),
    ]
    assert all(body in (b"", json.dumps(None).encode()) for _, _, body in calls)
    client.close()


def test_onboarding_deletes_user_when_key_creation_fails() -> None:
    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.url.path.endswith("/auth/user/create"):
            return httpx.Response(200, json={"ok": True, "data": {"id": "user-7"}})
        if request.url.path.endswith("/account/keys/create"):
            return httpx.Response(
                400,
                json={"ok": False, "error": {"code": "KEY_REJECTED"}},
            )
        return httpx.Response(200, json={"ok": True, "data": {}})

    client = InfraiClient("test-key", transport=httpx.MockTransport(handler))
    try:
        try:
            onboard_tenant(
                client,
                tenant_id="starfall",
                email="chenhua@changba.com",
                studio_name="Starfall Arcade",
            )
        except InfraiError as exc:
            assert exc.code == "KEY_REJECTED"
        else:
            raise AssertionError("expected key creation to fail")
    finally:
        client.close()

    assert calls == [
        ("POST", "/v1/auth/user/create"),
        ("POST", "/v1/account/keys/create"),
        ("DELETE", "/v1/auth/user/delete/user-7"),
    ]
