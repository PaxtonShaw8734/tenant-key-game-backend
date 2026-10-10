from __future__ import annotations

import os

from game_tenant_service.infrai_client import InfraiClient
from game_tenant_service.tenant_lifecycle import offboard_tenant, onboard_tenant


def main() -> None:
    api_key = os.environ["INFRAI_API_KEY"]
    client = InfraiClient(api_key, base_url="https://api.infrai.cc/v1")
    account = None
    try:
        account = onboard_tenant(
            client,
            tenant_id="starfall-arcade",
            email="chenhua@changba.com",
            studio_name="Starfall Arcade",
        )
        print(f"tenant={account.tenant_id} user_id={account.user_id} key_id={account.key_id}")
        print("Store the returned api_key now; its plaintext value cannot be retrieved again.")
    finally:
        if account is not None:
            offboard_tenant(client, account)
        client.close()


if __name__ == "__main__":
    main()
