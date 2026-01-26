from datetime import datetime, timezone

from ah_cache import AHCache
from ah_blizzard_fetcher import BlizzardAHFetcher
from config import get_appdata_dir


def refresh_ah_blizzard(
    client_id: str,
    client_secret: str,
    realm_slug: str = "dalaran",
):
    # --------------------------
    # Init cache
    # --------------------------
    cache_path = get_appdata_dir() / "ah_cache.json"
    cache = AHCache(cache_path, ttl_seconds=1800)

    cache.load()
    if cache.is_valid():
        print("🧠 Cache AH valide — refresh ignoré")
        return cache.data

    print("🌐 Refresh AH Blizzard…")

    # --------------------------
    # Fetch Blizzard AH
    # --------------------------
    fetcher = BlizzardAHFetcher(
        client_id=client_id,
        client_secret=client_secret,
    )

    fetcher.authenticate()
    connected_realm_id = fetcher.get_connected_realm_id(realm_slug)

    prices = fetcher.fetch_min_buyouts(connected_realm_id)

    print(f"📦 Items AH récupérés : {len(prices)}")

    # --------------------------
    # Format pour cache
    # --------------------------
    now = (
        datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )

    components = {
        str(item_id): {
            "price": price,
            "source": "blizzard",
            "updated_at": now,
        }
        for item_id, price in prices.items()
    }

    decors = {}  # géré plus tard (par nom)

    # --------------------------
    # Save cache
    # --------------------------
    cache.save(
        components=components,
        decors=decors,
    )

    print("✅ Cache AH mis à jour")

    return cache.data
