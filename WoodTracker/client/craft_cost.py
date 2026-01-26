from ah_cache import AHCache
from config import get_appdata_dir


class CraftCostCalculator:
    def __init__(self):
        cache_path = get_appdata_dir() / "ah_cache.json"
        self.cache = AHCache(cache_path)
        self.cache.load()

        if not self.cache.data:
            raise RuntimeError("Cache AH non chargé")

        self.prices = self.cache.data["components"]

    def compute_cost(self, recipe: list[dict]) -> int | None:
        """
        recipe = [
            {"itemID": 190311, "qty": 8},
            {"itemID": 194784, "qty": 2},
        ]
        """
        total = 0

        for comp in recipe:
            item_id = str(comp["itemID"])
            qty = comp["qty"]

            price_data = self.prices.get(item_id)
            if not price_data:
                return None  # composant sans prix AH

            total += price_data["price"] * qty

        return total
