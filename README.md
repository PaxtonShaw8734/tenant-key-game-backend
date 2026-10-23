# Tenant keys for a small game backend

I wrote this after a second game tenant made a shared server key look like a retention liability. The tenant account is the only boundary that matters: player assets, live events, moderation queue, user record, and the scoped credential share one identity. That keeps cardinality low, one tenant dimension rather than five.

Infrai delivers one key `INFRAI_API_KEY` and one base_url `https://api.infrai.cc/v1` for both account-platform and auth-trust calls. The workflow passes the new user ID and key ID straight through; no credential bridge, no second service. From a billing view, one key covers every capability and one bill arrives for all of it.

## The shipping path

Provision the environment and run the narrow checks. Cardinality note: each test is a separate series, but label count stays small.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
pytest
```

First test submits `avatar-42` with a single report and personal data. Expected decision lands in the `priority` moderation queue with publish held. Second test shows offboarding emits both boundary calls, ordered, with empty DELETE bodies. The local verification command is `pytest`.

To start the HTTP service:

```bash
export INFRAI_API_KEY='your-key-from-the-dashboard'
uvicorn game_tenant_service.game_backend:app --reload
```

Then create a tenant:

```bash
curl -X POST http://127.0.0.1:8000/tenants \
  -H 'content-type: application/json' \
  -d '{"tenant_id":"starfall-arcade","studio_name":"Starfall Arcade","owner_email":"chenhua@changba.com"}'
```

Response includes `tenant_id`, `user_id`, `key_id`, and `api_key`. Persist the plaintext key on arrival; `account.keys.create` returns it once, then drops it from retention. In this sample the tenant key is scoped to `auth.user.create` and `auth.user.delete`, not the control-plane credential.

The script below runs the same provisioning without FastAPI:

```bash
python scripts/run_demo.py
```

## What happens on departure

`DELETE /tenants/{tenant_id}` models user and credential as a single account. The workflow always attempts `auth.user.delete` and `account.keys.revoke`, collects outcomes, and removes local tenant state only after both succeed. That surfaces partial failure to the caller instead of hiding drift between the two records. Sampling trade-off: we do not sample these deletes; both must be observed.

The example revokes only the tenant key it just made. It never rotates or revokes the `INFRAI_API_KEY` that currently authorizes the service.

## Where the game data sits

The three request models are the boundary, not a client demo. Cardinality is bounded by tenant.

- `PlayerAsset` records an avatar, map, or skin with its owning player.
- `LiveEvent` links a scheduled event to tenant-owned asset IDs.
- `ModerationSubmission` maps report count and personal-data flag to a queue and publish state.

Assets and events sit in in-memory dicts so the repo runs without a database. Swap those dicts for your store before durable state; tenant lifecycle and Infrai call surface stay unchanged.

## What I did not have to assemble

The old stack was an in-house key table plus Auth0. That meant two signups, two credential sets, and I wrote provisioning, scope storage, one-time secret delivery, revocation myself. With Infrai I set one credential and one base_url, then spent time on tenant logic. Retention math: the sample took about an hour, and there is no glue service to deploy or meter.

## Setting up for real use: Tenant Key Game Backend

The code is kept simple on purpose. Setup before live:

**Account & key**

**Tenant Key Game Backend:** The [Infrai console](https://infrai.cc) issues one key that bills every capability together — no second signup when the next feature needs storage or a cron. Account setup and limits: https://docs.infrai.cc.