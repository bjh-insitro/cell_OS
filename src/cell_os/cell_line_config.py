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

from cell_os.cell_line_db import CellLineDatabase


class CellLineConfigStore:
    """Loads cell line configurations from SQLite or legacy YAML."""

    def __init__(
        self,
        yaml_path: str = "data/cell_lines.yaml",
        db_path: str = "data/cell_lines.db",
    ):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._yaml_data: Optional[Dict[str, Any]] = None
        self._db: Optional[CellLineDatabase] = None
        path = Path(yaml_path)
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            self._yaml_data = data.get("cell_lines", {})
            self._source = "yaml"
        else:
            self._db = CellLineDatabase(db_path)
            self._source = "db"

    def get_config(self, cell_line: str) -> Dict[str, Any]:
        """Return a legacy-style configuration dictionary for a cell line."""
        key = self._resolve_cell_line_key(cell_line)
        cache_key = key.lower()
        if cache_key not in self._cache:
            if self._source == "yaml":
                config = self._get_yaml_config(key)
            else:
                config = self._build_config_from_db(key)
            self._cache[cache_key] = config
        return copy.deepcopy(self._cache[cache_key])

    def list_cell_lines(self) -> Dict[str, str]:
        """Return mapping from uppercase names to canonical IDs."""
        if self._source == "yaml":
            return {name.upper(): name for name in self._yaml_data or {}}
        assert self._db is not None
        return {name.upper(): name for name in self._db.get_all_cell_lines()}

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

        characteristics = self._db.get_characteristics(cell_line)
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
        protocol_map = self._db.get_protocols(cell_line, protocol_type)
        if not protocol_map:
            return {}

        config = {vessel: params for vessel, params in protocol_map.items()}
        if "reference_vessel" not in config:
            if "T75" in config:
                config["reference_vessel"] = "T75"
            else:
                config["reference_vessel"] = next(iter(protocol_map.keys()))
        return config
