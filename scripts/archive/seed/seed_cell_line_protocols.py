#!/usr/bin/env python3
"""
Seed protocol parameters in the SQLite cell line database from the legacy YAML.

Usage:
    python scripts/seed_cell_line_protocols.py \
        --yaml data/cell_lines.yaml \
        --db data/cell_lines.db \
        [--overwrite]
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from pathlib import Path
from typing import Dict, Any

import yaml

from cell_os.database.repositories.cell_line import (
    CellLineRepository,
    CellLine,
    CellLineCharacteristic,
    ProtocolParameters,
)


def load_yaml(path: Path) -> Dict[str, Any]:
    """Load the cell line YAML fixture."""
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return data.get("cell_lines", {})


def upsert_cell_line(repo: CellLineRepository, cell_line_id: str, config: Dict[str, Any]) -> None:
    """Ensure the base cell_lines row exists with the latest metadata."""
    profile = config.get("profile", {})
    defaults = {
        "cell_line_id": cell_line_id,
        "display_name": profile.get("display_name", cell_line_id),
        "cell_type": profile.get("cell_type", "immortalized"),
        "growth_media": config.get("growth_media", profile.get("media", "mtesr_plus_kit")),
        "wash_buffer": config.get("wash_buffer"),
        "detach_reagent": config.get("detach_reagent"),
        "coating_required": bool(config.get("coating_required", profile.get("coating_required", False))),
        "coating_reagent": config.get("coating_reagent", profile.get("coating_reagent")),
        "cost_tier": profile.get("cost_tier", "standard"),
    }

    existing = repo.get_cell_line(cell_line_id)
    if existing:
        payload = asdict(existing)
        payload.update(defaults)
        # Remove primary key from update dict
        payload.pop("cell_line_id", None)
        repo._update("cell_lines", payload, "cell_line_id = ?", (cell_line_id,))
    else:
        repo.add_cell_line(CellLine(**defaults))

    sync_characteristics(repo, cell_line_id, profile)


def sync_characteristics(repo: CellLineRepository, cell_line_id: str, profile: Dict[str, Any]) -> None:
    """Update the cell_line_characteristics table from profile metadata."""
    skip_keys = {"cell_type", "coating_required", "coating_reagent", "media"}
    for key, value in profile.items():
        if key in skip_keys or value is None:
            continue
        repo._delete(
            "cell_line_characteristics",
            "cell_line_id = ? AND characteristic = ?",
            (cell_line_id, key),
        )
        repo.add_characteristic(
            CellLineCharacteristic(
                cell_line_id=cell_line_id,
                characteristic=key,
                value=str(value),
            )
        )


def seed_protocols(
    repo: CellLineRepository,
    cell_line_id: str,
    config: Dict[str, Any],
    overwrite: bool = False,
) -> None:
    """Write thaw/feed/passage protocol parameters into SQLite."""
    for protocol_type in ("thaw", "feed", "passage"):
        block = config.get(protocol_type)
        if not block:
            continue

        reference = block.get("reference_vessel")
        for vessel, params in block.items():
            if vessel == "reference_vessel":
                continue

            payload = dict(params)
            if reference and "reference_vessel" not in payload:
                payload["reference_vessel"] = reference

            if overwrite:
                repo._delete(
                    "protocol_parameters",
                    "cell_line_id = ? AND protocol_type = ? AND vessel_type = ?",
                    (cell_line_id, protocol_type, vessel),
                )
            elif repo.get_protocol(cell_line_id, protocol_type, vessel):
                continue

            repo.add_protocol(
                ProtocolParameters(
                    cell_line_id=cell_line_id,
                    protocol_type=protocol_type,
                    vessel_type=vessel,
                    parameters=payload,
                )
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed cell line protocols into SQLite.")
    parser.add_argument("--yaml", default="data/cell_lines.yaml", help="Path to legacy YAML config.")
    parser.add_argument("--db", default="data/cell_lines.db", help="Path to SQLite database.")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace existing protocol_parameters rows instead of skipping them.",
    )
    args = parser.parse_args()

    yaml_path = Path(args.yaml)
    if not yaml_path.exists():
        raise SystemExit(f"YAML file not found: {yaml_path}")

    configs = load_yaml(yaml_path)
    repo = CellLineRepository(args.db)

    for cell_line_id, config in configs.items():
        upsert_cell_line(repo, cell_line_id, config)
        seed_protocols(repo, cell_line_id, config, overwrite=args.overwrite)

    print(f"Seeded {len(configs)} cell lines into {args.db}")


if __name__ == "__main__":
    main()
