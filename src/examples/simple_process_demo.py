# src/examples/simple_process_demo.py

"""
Minimal demo of a linear Process composed of PassageOp and FeedOp.

Usage:
    python -m src.examples.simple_process_demo
"""

from src.core.world_model import Artifact, PassageOp, FeedOp
from src.core.store import ArtifactStore
from src.core.process import Process
from src.core.costing import InventoryCostEngine
from src.inventory import Inventory


def main() -> None:
    # 1. Create starting Artifact
    start_artifact = Artifact(
        id="art_001",
        kind="CellPopulation",
        state={
            "cell_line": "HepG2",
            "media": "DMEM+10%FBS",
            "vessel_id": "plate_6well_01",
            "cell_count": 1_000_000.0,
            "passage_number": 5,
            "time_since_last_feed_h": 24.0,
        },
        lineage=[],
    )

    # 2. Initialize ArtifactStore and register the starting artifact
    store = ArtifactStore()
    store.add(start_artifact)

    # 3. Initialize Inventory and Cost Engine
    # Assuming running from project root
    inventory = Inventory("data/raw/pricing.yaml")
    cost_engine = InventoryCostEngine(inventory)

    # 4. Define UnitOps
    passage_op = PassageOp()
    feed_op = FeedOp()

    # 5. Define Process
    passage_and_feed = Process(
        name="HepG2_passage_and_feed",
        steps=[passage_op, feed_op],
    )

    # 6. Define parameters for each UnitOp by name
    process_params = {
        "op_passage": {
            "target_vessel": "plate_6well_02",
            "split_ratio": 4.0,
            "dissociation_method": "trypsin",
        },
        "op_feed": {
            "media": "DMEM+10%FBS+PenStrep",
        },
    }

    # 7. Run the process with cost engine
    result = passage_and_feed.run(
        store=store,
        input_ids=[start_artifact.id],
        cost_engine=cost_engine,
        **process_params,
    )

    # 8. Inspect results
    print("=== PROCESS COMPLETE ===")
    print(f"Process name: {passage_and_feed.name}")
    print()

    print("Final output artifacts:")
    for art in result.outputs:
        print(f"  id: {art.id}")
        print(f"  kind: {art.kind}")
        print(f"  state: {art.state}")
        print(f"  lineage: {art.lineage}")
        print(f"  full_lineage_chain: {store.lineage(art.id)}")
        print()

    print("Execution records (in order):")
    for rec in result.records:
        print(f"  unit_op_name: {rec.unit_op_name}")
        print(f"    inputs: {rec.inputs}")
        print(f"    outputs: {rec.outputs}")
        print(f"    params: {rec.params}")
        print(f"    time_start: {rec.time_start}")
        print(f"    time_end: {rec.time_end}")
        print(f"    cost_usd: {rec.cost_usd:.4f}")
        if rec.warnings:
            print(f"    warnings: {rec.warnings}")
        if rec.errors:
            print(f"    errors: {rec.errors}")
        print()

    print(f"Total process cost (USD): {result.total_cost_usd:.4f}")


if __name__ == "__main__":
    main()
