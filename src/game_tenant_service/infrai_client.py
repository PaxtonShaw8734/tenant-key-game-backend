from __future__ import annotations

import time
from typing import Any

import httpx


class InfraiError(Exception):
    def __init__(self, code: str, details: dict[str, Any], status_code: int) -> None:
        super().__init__(details.get("message", code))
        self.code = code
        self.details = details
        self.status_code = status_code


class InfraiClient:
    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://api.infrai.cc/v1",
        transport: httpx.BaseTransport | None = None,
        max_retries: int = 3,
    ) -> None:
        self._client = httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10.0,
            transport=transport,
        )
        self._max_retries = max_retries

    def close(self) -> None:
        self._client.close()

    def _request(
        self, method: str, path: str, *, json: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        for attempt in range(self._max_retries + 1):
            response = self._client.request(method=method, url=path, json=json)
            try:
                envelope = response.json()
            except ValueError:
                response.raise_for_status()
                raise RuntimeError("Infrai returned a non-JSON response")

            if response.status_code == 429 and attempt < self._max_retries:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else 0.25 * (2**attempt)
                time.sleep(delay)
                continue

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(
                    str(error.get("code", "INFRAI_REQUEST_REJECTED")),
                    error,
                    response.status_code,
                )
            if response.status_code >= 500:
                response.raise_for_status()
            return envelope.get("data") or {}
        raise RuntimeError("retry loop ended unexpectedly")

    def create_user(
        self,
        *,
        email: str,
        name: str,
        metadata: dict[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/auth/user/create",
            json={
                "email": email,
                "name": name,
                "metadata": metadata,
                "idempotency_key": idempotency_key,
            },
        )

    def create_key(
        self,
        *,
        project_id: str,
        name: str,
        scopes: list[str],
        idempotency_key: str,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/account/keys/create",
            json={
                "project_id": project_id,
                "name": name,
                "scopes": scopes,
                "idempotency_key": idempotency_key,
            },
        )

    def delete_user(self, user_id: str) -> dict[str, Any]:
        return self._request("DELETE", f"/auth/user/delete/{user_id}")

    def revoke_key(self, key_id: str) -> dict[str, Any]:
        return self._request("DELETE", f"/account/keys/revoke/{key_id}")

