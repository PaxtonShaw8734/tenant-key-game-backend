from __future__ import annotations

import os
from dataclasses import asdict
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .infrai_client import InfraiClient, InfraiError
from .tenant_lifecycle import OffboardingError, TenantAccount, offboard_tenant, onboard_tenant


class TenantSignup(BaseModel):
    tenant_id: str = Field(min_length=2)
    studio_name: str = Field(min_length=2)
    owner_email: str


class PlayerAsset(BaseModel):
    tenant_id: str
    asset_id: str
    player_id: str
    kind: Literal["avatar", "map", "skin"]
    content_uri: str


class LiveEvent(BaseModel):
    tenant_id: str
    event_id: str
    title: str
    starts_at: str
    asset_ids: list[str] = Field(default_factory=list)


class ModerationSubmission(BaseModel):
    tenant_id: str
    asset_id: str
    reports: int = Field(ge=0)
    contains_personal_data: bool = False


class ModerationDecision(BaseModel):
    asset_id: str
    queue: Literal["standard", "priority"]
    publish_state: Literal["held", "visible"]


def decide_moderation(item: ModerationSubmission) -> ModerationDecision:
    priority = item.contains_personal_data or item.reports >= 3
    return ModerationDecision(
        asset_id=item.asset_id,
        queue="priority" if priority else "standard",
        publish_state="held" if priority else "visible",
    )


def create_app(client: InfraiClient | None = None) -> FastAPI:
    app = FastAPI(title="Tenant key game backend")
    accounts: dict[str, TenantAccount] = {}
    assets: dict[str, PlayerAsset] = {}
    events: dict[str, LiveEvent] = {}

    def infrai() -> InfraiClient:
        if client is not None:
            return client
        api_key = os.environ.get("INFRAI_API_KEY")
        if not api_key:
            raise HTTPException(status_code=503, detail="INFRAI_API_KEY is required")
        return InfraiClient(api_key)

    @app.post("/tenants", status_code=201)
    def create_tenant(request: TenantSignup) -> dict[str, str]:
        try:
            account = onboard_tenant(
                infrai(),
                tenant_id=request.tenant_id,
                email=request.owner_email,
                studio_name=request.studio_name,
            )
        except InfraiError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.details) from exc
        accounts[request.tenant_id] = account
        return {key: str(value) for key, value in asdict(account).items()}

    @app.delete("/tenants/{tenant_id}")
    def delete_tenant(tenant_id: str) -> dict[str, str]:
        account = accounts.get(tenant_id)
        if account is None:
            raise HTTPException(status_code=404, detail="tenant not found")
        try:
            result = offboard_tenant(infrai(), account)
        except OffboardingError as exc:
            raise HTTPException(status_code=409, detail=exc.outcomes) from exc
        del accounts[tenant_id]
        return result

    @app.post("/assets", status_code=201)
    def add_asset(asset: PlayerAsset) -> PlayerAsset:
        assets[f"{asset.tenant_id}:{asset.asset_id}"] = asset
        return asset

    @app.post("/live-events", status_code=201)
    def schedule_event(event: LiveEvent) -> LiveEvent:
        events[f"{event.tenant_id}:{event.event_id}"] = event
        return event

    @app.post("/moderation/queue")
    def queue_asset(item: ModerationSubmission) -> ModerationDecision:
        return decide_moderation(item)

    return app


app = create_app()

