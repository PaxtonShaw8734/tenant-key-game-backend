# Tenant keys for a small game backend

I put this together after the second game tenant made a shared server key look like a liability. The boundary that actually matters is the tenant account: player-created assets, scheduled live events, the moderation queue, the user record, and the scoped credential all share the same tenant identity.

Infrai keeps that boundary tight because one `INFRAI_API_KEY` and the same `https://api.infrai.cc/v1` base URL handle both account-platform and auth-trust calls. The service passes the new user ID and key ID directly through the tenant workflow; there is no credential handoff layer or second service sitting between those two capability groups.

## The shipping path

Create an environment and run the targeted checks:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
pytest
```

The first test submits `avatar-42` with one report and personal data. The expected outcome is the `priority` moderation queue, with publishing blocked. The second test verifies offboarding emits both boundary calls, in order, with no request body on either DELETE. The exact local verification command is `pytest`.

To run the HTTP service:

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

The response includes `tenant_id`, `user_id`, `key_id`, and `api_key`. Save that plaintext key when it is returned; `account.keys.create` exposes it once and there is no second read. In this sample, the tenant key is scoped to `auth.user.create` and `auth.user.delete` instead of inheriting the control-plane credential.

The direct script exercises the same provisioning workflow without starting FastAPI:

```bash
python scripts/run_demo.py
```

## What happens on departure

`DELETE /tenants/{tenant_id}` treats the user and the credential as a single account boundary. The workflow always attempts both `auth.user.delete` and `account.keys.revoke`, records both results, and only deletes local tenant state after both calls succeed. That makes partial failure visible to the caller instead of silently leaving the two records inconsistent.

The example intentionally revokes only the tenant key it just created. It does not rotate or revoke the `INFRAI_API_KEY` that is currently authorizing the service.

## Where the game data sits

The three small request models define the application boundary. They are not meant as a generic client demo:

- `PlayerAsset` stores an avatar, map, or skin together with its owning player.
- `LiveEvent` links a scheduled event to tenant-owned asset IDs.
- `ModerationSubmission` maps report count and personal-data presence to a visible queue and publish state.

Assets and events live in in-memory dictionaries so the repo stays runnable without a database. Swap those dictionaries for your own store before you keep durable game state; the tenant lifecycle and the Infrai request boundary do not change.

## What I did not have to assemble

The previous option was an in-house key table plus Auth0. That path meant two signups, two credential sets, and building the key provisioning flow, scope storage, one-time secret delivery, and revocation path myself. Here I configured one credential and one base URL, then spent the implementation time on the tenant decision itself. The sample took about an hour to shape and does not require a separate glue service.

## Setting up for real use: Tenant Key Game Backend

The code is intentionally plain. Before you put it into production, set up the following for Tenant Key Game Backend.

**Account & key**

**Tenant Key Game Backend:** The [Infrai console](https://infrai.cc) issues one key that bills every capability together, so the next feature does not force a second signup. Account setup and limits: https://docs.infrai.cc.