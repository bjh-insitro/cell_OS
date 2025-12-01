"""
Base classes and definitions for Unit Operations.
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Optional, Union
import pandas as pd
import yaml
import os

@dataclass
class Vessel:
    id: str
    name: str
    surface_area_cm2: float
    working_volume_ml: float
    coating_volume_ml: float
    max_volume_ml: float
    consumable_id: Optional[str] = None  # Links to pricing in master_pricing.yaml

class VesselLibrary:
    def __init__(self, yaml_path: str = "data/raw/vessels.yaml"):
        self.vessels: Dict[str, Vessel] = {}
        if os.path.exists(yaml_path):
            self._load(yaml_path)

    def _load(self, path: str):
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
        for v_id, v_data in data.get('vessels', {}).items():
            self.vessels[v_id] = Vessel(
                id=v_id,
                name=v_data.get('name', ''),
                surface_area_cm2=float(v_data.get('surface_area_cm2', 0.0)),
                working_volume_ml=float(v_data.get('working_volume_ml', 0.0)),
                coating_volume_ml=float(v_data.get('coating_volume_ml', 0.0)),
                max_volume_ml=float(v_data.get('max_volume_ml', 0.0)),
                consumable_id=v_data.get('consumable_id')  # Optional link to pricing
            )

    def get(self, v_id: str) -> Vessel:
        if v_id is None:
            return Vessel("None", "Generic Vessel", 0.0, 1.0, 0.0, 1.0)

        if v_id not in self.vessels:
            # Fallback for aliases used in code but not in YAML
            if "plate_6well" in v_id: 
                return Vessel(v_id, "6-Well Plate", 9.5, 3.0, 1.5, 16.8)
            if "flask_t75" in v_id.lower():
                return Vessel(v_id, "T-75 Flask", 75.0, 15.0, 12.5, 250.0)
            if "flask_t175" in v_id:
                return Vessel(v_id, "T-175 Flask", 175.0, 30.0, 15.0, 600.0)
            if "tube_50ml" in v_id:
                return Vessel(v_id, "50mL Conical Tube", 15.0, 50.0, 0.0, 50.0)
            if "tube_15ml" in v_id:
                return Vessel(v_id, "15mL Conical Tube", 5.0, 15.0, 0.0, 15.0)
            if "cryovial" in v_id:
                return Vessel(v_id, "Cryovial", 1.8, 1.0, 0.0, 1.8)
            if "flow_tubes" in v_id:
                return Vessel(v_id, "Flow Tube", 0.0, 0.5, 0.0, 5.0)
            
            return Vessel(v_id, "Generic Vessel", 0.0, 1.0, 0.0, 1.0)
            
        return self.vessels[v_id]

@dataclass
class UnitOp:
    uo_id: str = ""
    name: str = "Generic Op"
    layer: str = "base"
    category: str = "handling"
    time_score: int = 1
    cost_score: int = 1
    automation_fit: int = 1
    failure_risk: int = 1
    staff_attention: int = 1
    instrument: Optional[str] = None
    material_cost_usd: float = 0.0
    instrument_cost_usd: float = 0.0
    sub_steps: List['UnitOp'] = field(default_factory=list)
    items: List = field(default_factory=list)  # List of BOMItem for resource tracking

@dataclass
class LayerScore:
    layer_name: str
    cost_score: int = 0
    time_score: int = 0
    risk_sum: int = 0
    count: int = 0
    instruments: List[str] = field(default_factory=list)
    total_material_usd: float = 0.0
    total_instrument_usd: float = 0.0

    @property
    def avg_risk(self) -> float:
        return self.risk_sum / self.count if self.count > 0 else 0.0

@dataclass
class AssayScore:
    assay_name: str
    total_cost_score: int
    total_time_score: int
    total_usd: float
    layer_scores: Dict[str, LayerScore]
    bottleneck_instrument: str

class AssayRecipe:
    def __init__(self, name: str, layers: Dict[str, List[Tuple[Union[str, UnitOp], int]]]):
        self.name = name
        self.layers = layers

    def derive_score(self, library) -> AssayScore:
        total_cost_score = 0
        total_time_score = 0
        total_usd = 0.0
        layer_scores = {}
        all_instruments = []

        for layer_name, steps in self.layers.items():
            l_score = LayerScore(layer_name=layer_name)
            
            for item, count in steps:
                if isinstance(item, str):
                    try:
                        uo = library.get(item)
                    except:
                        uo = UnitOp(uo_id=item, name=item)
                else:
                    uo = item
                
                l_score.cost_score += uo.cost_score * count
                l_score.time_score += uo.time_score * count
                l_score.risk_sum += uo.failure_risk * count
                l_score.count += count
                
                mat_cost = uo.material_cost_usd * count
                inst_cost = uo.instrument_cost_usd * count
                l_score.total_material_usd += mat_cost
                l_score.total_instrument_usd += inst_cost
                
                if uo.instrument:
                    l_score.instruments.append(uo.instrument)
                    all_instruments.append(uo.instrument)
            
            layer_scores[layer_name] = l_score
            total_cost_score += l_score.cost_score
            total_time_score += l_score.time_score
            total_usd += (l_score.total_material_usd + l_score.total_instrument_usd)

        bottleneck = ", ".join(sorted(list(set(all_instruments)))) if all_instruments else "None"

        return AssayScore(
            assay_name=self.name,
            total_cost_score=total_cost_score,
            total_time_score=total_time_score,
            total_usd=total_usd,
            layer_scores=layer_scores,
            bottleneck_instrument=bottleneck
        )

class UnitOpLibrary:
    def __init__(self, csv_paths: List[str]):
        self.ops: Dict[str, UnitOp] = {}
        for path in csv_paths:
            if os.path.exists(path):
                self._load(path)

    def _load(self, csv_path: str):
        df = pd.read_csv(csv_path)
        for _, row in df.iterrows():
            self.ops[row["uo_id"]] = UnitOp(
                uo_id=row["uo_id"],
                name=row["name"],
                layer=row["layer"],
                category=row["category"],
                time_score=int(row["time_score"]),
                cost_score=int(row["cost_score"]),
                automation_fit=int(row["automation_fit"]),
                failure_risk=int(row["failure_risk"]),
                staff_attention=int(row["staff_attention"]),
                instrument=row["instrument"] if pd.notna(row["instrument"]) else None,
                material_cost_usd=float(row.get("material_cost_usd", 0.0)),
                instrument_cost_usd=float(row.get("instrument_cost_usd", 0.0))
            )

    def get(self, uo_id: str) -> UnitOp:
        if uo_id not in self.ops:
            raise KeyError(f"Unit Op {uo_id} not found.")
        return self.ops[uo_id]