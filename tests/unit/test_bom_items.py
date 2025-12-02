import pytest

from cell_os.inventory import Inventory, Resource, BOMItem


def build_inventory():
    resources = {
        "media": Resource(
            resource_id="media",
            name="Growth Media",
            vendor="Acme",
            catalog_number="GM-001",
            pack_size=1000,
            pack_unit="mL",
            pack_price_usd=120.0,
            logical_unit="mL",
            unit_price_usd=0.12,
            category="media",
            stock_level=500,
        ),
        "pipette_tip": Resource(
            resource_id="pipette_tip",
            name="200uL Tips",
            vendor="Acme",
            catalog_number="PT-200",
            pack_size=960,
            pack_unit="ea",
            pack_price_usd=25.0,
            logical_unit="ea",
            unit_price_usd=25.0 / 960,
            category="consumable",
            stock_level=960,
        ),
    }
    return Inventory(resources=resources)


def test_compute_bom_cost_and_availability():
    inventory = build_inventory()
    bom = [BOMItem("media", 10.0), BOMItem("pipette_tip", 20)]

    cost = inventory.compute_bom_cost(bom)
    assert cost == pytest.approx((10.0 * 0.12) + (20 * (25.0 / 960)))

    availability = inventory.check_availability(bom)
    assert availability["media"] is True
    assert availability["pipette_tip"] is True


def test_snapshot_includes_resource_state():
    inventory = build_inventory()
    snapshot = inventory.snapshot()
    assert "media" in snapshot
    assert snapshot["media"]["stock_level"] == 500
    assert snapshot["media"]["name"] == "Growth Media"
