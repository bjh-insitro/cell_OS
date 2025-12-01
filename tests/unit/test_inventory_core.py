from cell_os.inventory import Inventory, Resource, InventoryLoader


def test_inventory_from_resources_isolation():
    base_resource = Resource(
        resource_id="media_a",
        name="Media A",
        vendor="Test",
        catalog_number="123",
        pack_size=10.0,
        pack_unit="mL",
        pack_price_usd=100.0,
        logical_unit="mL",
        unit_price_usd=1.0,
        category="media",
        stock_level=500.0,
    )

    inv = Inventory(resources={"media_a": base_resource})
    base_resource.stock_level = 0.0

    assert inv.resources["media_a"].stock_level == 500.0

    inv.consume("media_a", 100.0, "mL")
    assert inv.resources["media_a"].stock_level == 400.0


def test_inventory_snapshot_round_trip():
    resource = Resource(
        resource_id="buffer",
        name="PBS",
        vendor="Test",
        catalog_number="PBS-01",
        pack_size=50.0,
        pack_unit="mL",
        pack_price_usd=25.0,
        logical_unit="mL",
        unit_price_usd=0.5,
        category="buffer",
        stock_level=100.0,
    )
    inv = Inventory(resources={"buffer": resource})
    snapshot = inv.snapshot()

    restored = {
        rid: Resource(**data)
        for rid, data in snapshot.items()
    }
    inv2 = Inventory(resources=restored)
    assert inv2.resources["buffer"].stock_level == 100.0
    assert inv2.get_price("buffer") == 0.5


def test_inventory_loader_prefers_yaml(tmp_path):
    yaml_path = tmp_path / "pricing.yaml"
    yaml_path.write_text(
        "items:\n"
        "  media_b:\n"
        "    name: Media B\n"
        "    vendor: Lab\n"
        "    catalog_number: LAB-1\n"
        "    pack_size: 20\n"
        "    pack_unit: mL\n"
        "    pack_price_usd: 40\n"
        "    logical_unit: mL\n"
        "    unit_price_usd: 2\n"
        "    category: media\n"
    )

    loader = InventoryLoader(str(yaml_path), db_path="does-not-exist.db")
    resources = loader.load()
    assert "media_b" in resources
    assert resources["media_b"].unit_price_usd == 2.0
