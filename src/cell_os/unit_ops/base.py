"""
Base classes and definitions for Unit Operations.
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Optional, Union
import pandas as pd
import yaml

@dataclass
class Vessel:
    id: str
    name: str
    surface_area_cm2: float
    working_volume_ml: float
    coating_volume_ml: float
    max_volume_ml: float

class VesselLibrary:
    def __init__(self, yaml_path: str):
        self.vessels: Dict[str, Vessel] = {}
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
                max_volume_ml=float(v_data.get('max_volume_ml', 0.0))
            )

    def get(self, v_id: str) -> Vessel:
        if v_id not in self.vessels:
            raise KeyError(f"Vessel {v_id} not found.")
        return self.vessels[v_id]

@dataclass
class UnitOp:
    uo_id: str
    name: str
    layer: str
    category: str
    time_score: int
    cost_score: int
    automation_fit: int
    failure_risk: int
    staff_attention: int
    instrument: Optional[str]
    material_cost_usd: float = 0.0
    instrument_cost_usd: float = 0.0
    sub_steps: List['UnitOp'] = field(default_factory=list)

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

    def __str__(self):
        s = f"Assay: {self.assay_name}\n"
        s += f"  Total Cost Score: {self.total_cost_score}\n"
        s += f"  Total Time Score: {self.total_time_score}\n"
        s += f"  Total USD: ${self.total_usd:.2f}\n"
        s += "  Breakdown by Layer:\n"
        for layer, score in self.layer_scores.items():
            s += f"    [{layer.upper()}] CostScore: {score.cost_score}, TimeScore: {score.time_score}, USD: ${score.total_material_usd + score.total_instrument_usd:.2f}, Avg Risk: {score.avg_risk:.2f}\n"
        s += f"  Bottleneck: {self.bottleneck_instrument}"
        return s

class AssayRecipe:
    def __init__(self, name: str, layers: Dict[str, List[Tuple[Union[str, UnitOp], int]]]):
        self.name = name
        self.layers = layers # Dict[layer_name, List[(uo_id_or_obj, count)]]

    def derive_score(self, library: "UnitOpLibrary") -> AssayScore:
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
                        uo = UnitOp(
                            uo_id=item, name=item, layer=layer_name, category="legacy",
                            time_score=0, cost_score=0, automation_fit=0, failure_risk=0,
                            staff_attention=0, instrument=None, material_cost_usd=0.0, instrument_cost_usd=0.0
                        )
                else:
                    uo = item
                
                # Scores
                l_score.cost_score += uo.cost_score * count
                l_score.time_score += uo.time_score * count
                l_score.risk_sum += uo.failure_risk * count
                l_score.count += count
                
                # Real USD
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
            self._load(path)

    def _load(self, csv_path: str):
        df = pd.read_csv(csv_path)
        if "material_cost_usd" not in df.columns:
            df["material_cost_usd"] = 0.0
        if "instrument_cost_usd" not in df.columns:
            df["instrument_cost_usd"] = 0.0

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
            raise KeyError(f"Unit Op {uo_id} not found in library.")
        return self.ops[uo_id]
