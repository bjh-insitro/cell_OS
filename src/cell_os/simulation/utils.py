"""
Simulation Utilities.
"""

class MockInventory:
    """
    Mock inventory for simulation purposes.
    Returns default prices for items.
    """
    def get_price(self, item_id: str) -> float:
        # Return some default prices
        prices = {
            "flask_t75": 5.0,
            "flask_t175": 10.0,
            "media_bottle": 50.0,
            "pbs_bottle": 20.0,
            "trypsin_bottle": 40.0,
            "cryovial": 1.0,
            "pipette_10ml": 0.5,
            "tip_1000ul": 0.1
        }
        return prices.get(item_id, 1.0)
