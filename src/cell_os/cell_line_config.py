"""
Cell line configuration store.

Provides a unified interface for loading protocol configs from the canonical
SQLite database, while preserving backward-compatible YAML support for legacy
tests and notebooks.
"""
from __future__ import annotations

import copy
import yaml
from pathlib import Path
from typing import Dict, Any, Optional

from cell_os.database.repositories.cell_line import CellLineRepository


class CellLineConfigStore:
    """Loads cell line configurations from SQLite or legacy YAML."""

    def __init__(
        self,
        yaml_path: str = "data/cell_lines.yaml",
        db_path: str = "data/cell_lines.db",
    ):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._yaml_data: Optional[Dict[str, Any]] = None
        self._db: Optional[CellLineRepository] = None

        yaml_file = Path(yaml_path)
        if yaml_file.exists():
            with open(yaml_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            self._yaml_data = data.get("cell_lines", {})

        # Always initialize the DB repository so we can fall back to SQLite when
        # a cell line is missing from the legacy YAML fixtures.
        self._db = CellLineRepository(db_path)

        if self._yaml_data and self._db:
            self._source = "hybrid"
        elif self._yaml_data:
            self._source = "yaml"
        else:
            self._source = "db"

    def get_config(self, cell_line: str) -> Dict[str, Any]:
        """Return a legacy-style configuration dictionary for a cell line."""
        key = self._resolve_cell_line_key(cell_line)
        cache_key = key.lower()
        if cache_key not in self._cache:
            if self._yaml_data and key in self._yaml_data:
                config = self._get_yaml_config(key)
            elif self._db:
                config = self._build_config_from_db(key)
            else:
                raise ValueError(f"Unknown cell line: {cell_line}")
            self._cache[cache_key] = config
        return copy.deepcopy(self._cache[cache_key])

    def list_cell_lines(self) -> Dict[str, str]:
        """Return mapping from uppercase names to canonical IDs."""
        mapping: Dict[str, str] = {}
        if self._yaml_data is not None:
            mapping.update({name.upper(): name for name in self._yaml_data})
        if self._db:
            for name in self._db.get_all_cell_lines():
                mapping.setdefault(name.upper(), name)
        return mapping

    # Internal helpers -------------------------------------------------

    def _resolve_cell_line_key(self, cell_line: str) -> str:
        mapping = self.list_cell_lines()
        upper = cell_line.upper()
        if upper in mapping:
            return mapping[upper]
        raise ValueError(f"Unknown cell line: {cell_line}")

    def _get_yaml_config(self, key: str) -> Dict[str, Any]:
        assert self._yaml_data is not None
        if key not in self._yaml_data:
            raise ValueError(f"Unknown cell line: {key}")
        return copy.deepcopy(self._yaml_data[key])

    def _build_config_from_db(self, cell_line: str) -> Dict[str, Any]:
        assert self._db is not None
        cell = self._db.get_cell_line(cell_line)
        if cell is None:
            raise ValueError(f"Unknown cell line: {cell_line}")

        # Convert list of characteristics to dict
        char_list = self._db.get_characteristics(cell_line)
        characteristics = {c.characteristic: c.value for c in char_list}
        
        config: Dict[str, Any] = {
            "growth_media": cell.growth_media,
            "wash_buffer": cell.wash_buffer,
            "detach_reagent": cell.detach_reagent,
            "coating_required": cell.coating_required,
            "coating_reagent": cell.coating_reagent,
            "profile": {
                **characteristics,
                "cell_type": cell.cell_type,
                "coating_required": cell.coating_required,
                "coating_reagent": cell.coating_reagent or "none",
                "media": characteristics.get("media", cell.growth_media),
            },
        }

        for protocol_type in ["passage", "thaw", "feed"]:
            proto_cfg = self._load_protocols_from_db(cell_line, protocol_type)
            if proto_cfg:
                config[protocol_type] = proto_cfg

        return config

    def _load_protocols_from_db(
        self, cell_line: str, protocol_type: str
    ) -> Dict[str, Any]:
        assert self._db is not None
        # Get list of ProtocolParameters objects
        protocol_list = self._db.get_protocols(cell_line, protocol_type)
        if not protocol_list:
            return {}

        # Convert to dict mapping vessel_type -> parameters
        config = {p.vessel_type: p.parameters for p in protocol_list}
        
        if "reference_vessel" not in config:
            if "T75" in config:
                config["reference_vessel"] = "T75"
            elif config:
                config["reference_vessel"] = next(iter(config.keys()))
        return config
