from craft_cost import CraftCostCalculator


class DecorProfitCalculator:
    def __init__(self):
        self.cost_calc = CraftCostCalculator()

    def compute_po_per_wood(
        self,
        recipe: list[dict],
        sell_price: int | None,
        wood_required: int,
    ) -> int | None:
        """
        recipe = [
            {"itemID": 190311, "qty": 8},
            {"itemID": 194784, "qty": 2},
        ]
        sell_price = prix AH décor (int)
        wood_required = int
        """

        if not sell_price or wood_required <= 0:
            return None

        craft_cost = self.cost_calc.compute_cost(recipe)
        if craft_cost is None:
            return None

        profit = sell_price - craft_cost
        return int(profit / wood_required)
