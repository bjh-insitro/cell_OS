"""
Menadione Phase 0 Design Generator

Generates experimental design specifically for Menadione dose-response in A549 cells.
Includes:
- 6 doses: Vehicle + 5 doses spanning shoulder to collapse
- 2 timepoints: 24h and 48h
- 3 passages × 3 plates per timepoint = 9 replicates per dose/timepoint
- 384-well plates with ~53 reps per dose per plate
- Cell Painting morphology + γ-H2AX supplemental IF
- Sentinels for variance partitioning (64 per plate)

Plate templates:
- 3 pre-generated templates (A, B, C) with different randomized layouts
- Templates reused across passages (Plate 1 always uses Template A, etc.)
- Sentinels in fixed positions across all templates

Reference: docs/2026Q1_Thalamus_Analysis_Plan.md, docs/PHASE_0_THALAMUS_PLAN_VarP.md
"""

import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .plate_template_generator import PlateTemplate, create_phase0_templates


@dataclass
class MenadioneWellAssignment:
    """Represents a single well assignment for Menadione Phase 0."""

    well_id: str
    cell_line: str
    compound: str
    dose_uM: float
    timepoint_h: float
    plate_id: str
    day: int
    operator: str
    is_sentinel: bool = False
    run_gamma_h2ax: bool = False  # Whether to run γ-H2AX assay on this well


@dataclass
class MenadionePhase0Design:
    """
    Phase 0 design for Menadione dose-response calibration.

    Design matrix:
    - Cell line: A549 only (NRF2-primed, oxidative stress resistant)
    - Compound: Menadione (vitamin K3, redox cycler)
    - Doses: Vehicle (0) + 5 doses spanning EC10 to EC90
    - Timepoints: 24h (early/shoulder) and 48h (late/collapse)
    - Passages: 3 (biological replication, across-passage stability)
    - Plates per timepoint per passage: 3 (technical replication)
    - Total plates: 18 (3 passages × 2 timepoints × 3 plates)

    384-well plate structure:
    - 64 sentinel wells (40 vehicle + 12 mild + 12 strong)
    - 318 experimental wells (53 per dose × 6 doses)
    - ~53 replicates per dose per plate
    - Total replicates per dose/timepoint: 53 × 9 = 477

    Plate templates:
    - 3 pre-generated templates (A, B, C) with stratified randomization
    - Plate 1 always uses Template A, Plate 2 uses B, Plate 3 uses C
    - Templates reused across passages (same layout for Psg1_P1, Psg2_P1, Psg3_P1)
    - Sentinels in fixed positions across all templates

    Total wells: 18 plates × 382 wells = 6,876 wells
    """

    design_id: str = field(default_factory=lambda: f"menadione_phase0_{uuid.uuid4().hex[:8]}")
    cell_line: str = "A549"
    compound: str = "menadione"

    # Dose grid: Vehicle + 5 doses spanning shoulder to collapse
    # Based on EC50 = 25 µM × A549 modifier 1.4 = 35 µM effective
    # Doses chosen to span EC10 (~5 µM) to EC90 (~150 µM)
    doses_uM: list[float] = field(
        default_factory=lambda: [
            0.0,  # Vehicle (DMSO)
            5.0,  # ~EC10 - minimal effect, shoulder region
            15.0,  # ~EC25 - early response
            35.0,  # ~EC50 - half-maximal
            75.0,  # ~EC75 - strong response
            150.0,  # ~EC90 - near-maximal, approaching collapse
        ]
    )

    timepoints_h: list[float] = field(default_factory=lambda: [24.0, 48.0])

    # Replication structure (per VarP spec)
    passages: list[int] = field(default_factory=lambda: [1, 2, 3])  # 3 biological passages
    plates_per_timepoint: list[int] = field(
        default_factory=lambda: [1, 2, 3]
    )  # 3 tech reps per timepoint

    # Template mapping: plate number -> template ID
    template_mapping: dict[int, str] = field(default_factory=lambda: {1: "A", 2: "B", 3: "C"})

    # Operator (single for Phase 0, could expand later)
    operators: list[str] = field(default_factory=lambda: ["Operator_A"])

    # Cached templates (generated once)
    _templates: dict[str, PlateTemplate] | None = field(default=None, repr=False)

    def __post_init__(self):
        # Load params for sentinel definitions
        params_file = (
            Path(__file__).parent.parent.parent.parent / "data" / "cell_thalamus_params.yaml"
        )
        if params_file.exists():
            with open(params_file) as f:
                self.params = yaml.safe_load(f)
        else:
            self.params = {}

        # Generate templates once
        if self._templates is None:
            self._templates = create_phase0_templates()

    def generate_design(self) -> list[MenadioneWellAssignment]:
        """Generate the complete experimental design.

        Structure: 3 passages × 2 timepoints × 3 plates = 18 plates
        Each 384-well plate uses a pre-generated template (A, B, or C)
        - Plate 1 → Template A
        - Plate 2 → Template B
        - Plate 3 → Template C

        Templates have:
        - 64 sentinel wells in fixed positions
        - 318 experimental wells (53 per dose) in randomized positions
        """
        assignments = []

        for passage in self.passages:
            for timepoint in self.timepoints_h:
                for plate_num in self.plates_per_timepoint:
                    for operator in self.operators:
                        # Plate ID encodes passage, timepoint, and plate number
                        plate_id = f"MEN_Psg{passage}_T{int(timepoint)}h_P{plate_num}_{operator}"

                        # Get template for this plate number
                        template_id = self.template_mapping[plate_num]
                        template = self._templates[template_id]

                        # Get all wells from template
                        template_wells = template.get_all_wells()

                        for well_pos, well_info in template_wells.items():
                            dose = well_info["dose_uM"]
                            is_sentinel = well_info["is_sentinel"]

                            # Determine compound name
                            if dose == 0:
                                compound = "DMSO"
                            else:
                                compound = self.compound

                            # Run γ-H2AX on all non-vehicle wells
                            run_gamma_h2ax = dose > 0

                            assignment = MenadioneWellAssignment(
                                well_id=well_pos,
                                cell_line=self.cell_line,
                                compound=compound,
                                dose_uM=dose,
                                timepoint_h=timepoint,
                                plate_id=plate_id,
                                day=passage,  # passage serves as "day" for compatibility
                                operator=operator,
                                is_sentinel=is_sentinel,
                                run_gamma_h2ax=run_gamma_h2ax,
                            )
                            assignments.append(assignment)

        return assignments

    def get_summary(self) -> dict[str, Any]:
        """Get summary statistics of the design."""
        design = self.generate_design()

        experimental = [w for w in design if not w.is_sentinel]
        sentinels = [w for w in design if w.is_sentinel]
        gamma_h2ax_wells = [w for w in design if w.run_gamma_h2ax]

        # Count unique conditions
        unique_conditions = len(set((w.compound, w.dose_uM, w.timepoint_h) for w in experimental))

        # Count unique plates
        unique_plates = len(set(w.plate_id for w in design))

        # Count by dose (total across all plates)
        dose_counts = {}
        for dose in self.doses_uM:
            dose_counts[f"{dose} µM"] = len([w for w in experimental if w.dose_uM == dose])

        # Wells per plate (from template)
        wells_per_plate = len(design) // unique_plates if unique_plates > 0 else 0
        exp_per_plate = len(experimental) // unique_plates if unique_plates > 0 else 0
        sent_per_plate = len(sentinels) // unique_plates if unique_plates > 0 else 0

        # Replicates per dose per plate (from template)
        reps_per_dose_per_plate = exp_per_plate // len(self.doses_uM) if self.doses_uM else 0

        # Total replicates per dose/timepoint = reps_per_plate × plates_per_timepoint × passages
        n_plates_per_timepoint = len(self.plates_per_timepoint) * len(self.passages)
        reps_per_dose_timepoint = reps_per_dose_per_plate * n_plates_per_timepoint

        return {
            "design_id": self.design_id,
            "cell_line": self.cell_line,
            "compound": self.compound,
            "plate_format": 384,
            "total_wells": len(design),
            "experimental_wells": len(experimental),
            "sentinel_wells": len(sentinels),
            "gamma_h2ax_wells": len(gamma_h2ax_wells),
            "unique_conditions": unique_conditions,
            "doses": self.doses_uM,
            "dose_counts": dose_counts,
            "timepoints": self.timepoints_h,
            "passages": len(self.passages),
            "plates_per_timepoint": len(self.plates_per_timepoint),
            "total_plates": unique_plates,
            "operators": len(self.operators),
            # Per-plate stats
            "wells_per_plate": wells_per_plate,
            "experimental_per_plate": exp_per_plate,
            "sentinels_per_plate": sent_per_plate,
            "reps_per_dose_per_plate": reps_per_dose_per_plate,
            # Total replication
            "reps_per_dose_timepoint": reps_per_dose_timepoint,
            "templates": list(self.template_mapping.values()),
        }

    def to_plate_map(self, plate_id: str) -> dict[str, MenadioneWellAssignment]:
        """Get well assignments for a specific plate as a map."""
        design = self.generate_design()
        return {w.well_id: w for w in design if w.plate_id == plate_id}

    def get_dose_response_matrix(self) -> list[dict[str, Any]]:
        """
        Get the dose-response matrix for analysis.

        Returns list of dicts with dose, timepoint, and expected assay outputs.
        """
        matrix = []
        # Replicates = plates_per_timepoint × passages
        n_reps = len(self.plates_per_timepoint) * len(self.passages)

        for dose in self.doses_uM:
            for timepoint in self.timepoints_h:
                matrix.append(
                    {
                        "dose_uM": dose,
                        "timepoint_h": timepoint,
                        "compound": "DMSO" if dose == 0 else self.compound,
                        "n_replicates": n_reps,
                        "assays": {
                            "cell_painting": True,
                            "cytotox_glo": True,  # CytoTox-Glo viability
                            "gamma_h2ax": dose > 0,  # γ-H2AX on treated wells only
                        },
                    }
                )
        return matrix


def create_menadione_design() -> MenadionePhase0Design:
    """Factory function to create a Menadione Phase 0 design."""
    return MenadionePhase0Design()


if __name__ == "__main__":
    # Generate and print design summary
    design = create_menadione_design()
    summary = design.get_summary()

    print("=" * 60)
    print("MENADIONE PHASE 0 DESIGN")
    print("=" * 60)
    print(f"Design ID: {summary['design_id']}")
    print(f"Cell Line: {summary['cell_line']}")
    print(f"Compound: {summary['compound']}")
    print()
    print("Plate Structure:")
    print(f"  Passages: {summary['passages']}")
    print(f"  Timepoints: {summary['timepoints']}")
    print(f"  Plates per timepoint per passage: {summary['plates_per_timepoint']}")
    print(f"  Total plates: {summary['total_plates']}")
    print()
    print(f"Total Wells: {summary['total_wells']}")
    print(f"  Experimental: {summary['experimental_wells']}")
    print(f"  Sentinels: {summary['sentinel_wells']}")
    print(f"  γ-H2AX Assay: {summary['gamma_h2ax_wells']}")
    print()
    print(f"Unique Conditions: {summary['unique_conditions']}")
    print(f"Replicates per dose/timepoint: {summary['replicates_per_dose_timepoint']}")
    print()
    print("Doses (µM):", summary["doses"])
    print()
    print("Dose Counts:")
    for dose, count in summary["dose_counts"].items():
        reps = count // 2  # per timepoint
        print(f"  {dose}: {count} wells total ({reps} per timepoint)")
    print()
    print("Dose-Response Matrix:")
    for entry in design.get_dose_response_matrix():
        assays = ", ".join(k for k, v in entry["assays"].items() if v)
        print(
            f"  {entry['dose_uM']:>6.1f} µM @ {entry['timepoint_h']:>2.0f}h: {entry['n_replicates']} reps [{assays}]"
        )
