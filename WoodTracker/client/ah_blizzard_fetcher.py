import requests
from datetime import datetime, timezone


class BlizzardAHFetcher:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        region="eu",
        locale="fr_FR",
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.region = region
        self.locale = locale

        self.namespace_dynamic = f"dynamic-{region}"
        self.namespace_static = f"static-{region}"

        self.token = None

    # --------------------------
    # AUTH
    # --------------------------
    def authenticate(self):
        url = f"https://{self.region}.battle.net/oauth/token"

        r = requests.post(
            url,
            auth=(self.client_id, self.client_secret),
            data={"grant_type": "client_credentials"},
            timeout=10,
        )
        r.raise_for_status()
        self.token = r.json()["access_token"]

    def headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
        }

    # --------------------------
    # REALM → CONNECTED REALM
    # --------------------------
    def get_connected_realm_id(self, realm_slug: str) -> str:
        # 1) realm index
        index_url = f"https://{self.region}.api.blizzard.com/data/wow/realm/index"
        params = {
            "namespace": self.namespace_dynamic,
            "locale": self.locale,
        }

        r = requests.get(
            index_url,
            headers=self.headers(),
            params=params,
            timeout=10,
        )
        r.raise_for_status()
        realms = r.json()["realms"]

        realm = next(
            (r for r in realms if r.get("slug") == realm_slug),
            None,
        )
        if not realm:
            raise RuntimeError(f"Realm '{realm_slug}' introuvable")

        realm_id = realm["id"]

        # 2) realm detail
        detail_url = (
            f"https://{self.region}.api.blizzard.com/data/wow/realm/{realm_id}"
        )
        r = requests.get(
            detail_url,
            headers=self.headers(),
            params=params,
            timeout=10,
        )
        r.raise_for_status()

        href = r.json()["connected_realm"]["href"]

        return (
            href.split("/connected-realm/")[1]
            .split("?")[0]
        )

    # --------------------------
    # AUCTIONS → PRICES
    # --------------------------
    def fetch_min_buyouts(self, connected_realm_id: str) -> dict:
        url = (
            f"https://{self.region}.api.blizzard.com/data/wow/connected-realm/"
            f"{connected_realm_id}/auctions"
        )

        params = {
            "namespace": self.namespace_dynamic,
            "locale": self.locale,
        }

        r = requests.get(
            url,
            headers=self.headers(),
            params=params,
            timeout=30,
        )
        r.raise_for_status()

        auctions = r.json().get("auctions", [])

        min_buyouts: dict[int, int] = {}

        for a in auctions:
            item_id = a.get("item", {}).get("id")
            buyout = a.get("buyout")

            if not item_id or not buyout:
                continue

            current = min_buyouts.get(item_id)
            if current is None or buyout < current:
                min_buyouts[item_id] = buyout

        return min_buyouts
