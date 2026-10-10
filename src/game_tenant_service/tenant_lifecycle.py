from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from .infrai_client import InfraiClient, InfraiError


TENANT_SCOPES = ["auth.user.create", "auth.user.delete"]


@dataclass(frozen=True)
class TenantAccount:
    tenant_id: str
    user_id: str
    key_id: str
    api_key: str


class OffboardingError(Exception):
    def __init__(self, outcomes: dict[str, str]) -> None:
        super().__init__("tenant offboarding did not complete")
        self.outcomes = outcomes


def onboard_tenant(
    client: InfraiClient, *, tenant_id: str, email: str, studio_name: str
) -> TenantAccount:
    operation_id = str(uuid4())
    user = client.create_user(
        email=email,
        name=studio_name,
        metadata={"tenant_id": tenant_id, "account_role": "game_backend"},
        idempotency_key=f"tenant-user-{tenant_id}-{operation_id}",
    )
    try:
        key = client.create_key(
            project_id=tenant_id,
            name=f"{studio_name} game backend",
            scopes=TENANT_SCOPES,
            idempotency_key=f"tenant-key-{tenant_id}-{operation_id}",
        )
    except Exception:
        client.delete_user(str(user["id"]))
        raise
    return TenantAccount(
        tenant_id=tenant_id,
        user_id=str(user["id"]),
        key_id=str(key["id"]),
        api_key=str(key["key"]),
    )


def offboard_tenant(client: InfraiClient, account: TenantAccount) -> dict[str, str]:
    outcomes: dict[str, str] = {}
    actions = (
        ("user", lambda: client.delete_user(account.user_id)),
        ("key", lambda: client.revoke_key(account.key_id)),
    )
    for label, action in actions:
        try:
            action()
            outcomes[label] = "deleted" if label == "user" else "revoked"
        except InfraiError as exc:
            outcomes[label] = f"rejected:{exc.code}"
    if outcomes != {"user": "deleted", "key": "revoked"}:
        raise OffboardingError(outcomes)
    return outcomes
