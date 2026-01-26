import requests
from datetime import datetime, timezone

BASE_URL = "https://api.nexushub.co/wow/v1"
TIMEOUT = 10

class NexusHubFetcher:
    def __init__(self, region="EU", realm="Dalaran"):
        self.region = region
        self.realm = realm

    def fetch_item_price(self, item_id: int) -> dict | None:
        url = f"{BASE_URL}/items/{self.region}/{self.realm}/{item_id}"

        try:
            r = requests.get(url, timeout=TIMEOUT)
            r.raise_for_status()
            data = r.json()

            price = data.get("stats", {}).get("minBuyout")
            if not price:
                return None

            return {
                "price": int(price),
                "source": "nexushub",
                "updated_at": datetime.now(timezone.utc)
                    .isoformat()
                    .replace("+00:00", "Z"),
            }

        except requests.RequestException as e:
            return None

def fetch_components_prices(item_ids: list[int]) -> dict:
    fetcher = NexusHubFetcher()
    result = {}

    for item_id in item_ids:
        data = fetcher.fetch_item_price(item_id)
        if data:
            result[str(item_id)] = data

    return result
