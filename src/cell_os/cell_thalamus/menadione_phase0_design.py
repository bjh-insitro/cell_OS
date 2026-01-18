"""
Menadione Phase 0 Design Generator

Generates experimental design specifically for Menadione dose-response in A549 cells.

═══════════════════════════════════════════════════════════════════════════════
CRITICAL DESIGN PHILOSOPHY - READ BEFORE MODIFYING DOSES
═══════════════════════════════════════════════════════════════════════════════

Phase 0 is NOT a toxicology study. The goal is NOT to characterize the kill curve.

From docs/PHASE_0_THALAMUS_PLAN_VarP.md:
    "Identify operating region where: Morphology shifts meaningfully,
     Viability remains compatible with pooled screening"

From docs/Cell_Thalamus_Dose_and_Timepoint_Calibration_2026-01-16.md:
    "Identify stressor doses and timepoints that produce maximal, reproducible
     morphological separation WITHOUT viability collapse."

    "Decision rule: nominate the dose/timepoint with the largest reproducible
     morphology shift that occurs BEFORE the CytoTox-Glo collapse inflection."

The goal is to find the PRE-COLLAPSE SHOULDER where:
- Cells are stressed enough to show morphological phenotypes
- Cells are ALIVE enough that you're measuring biology, not death
- Typically 60-90% viability range (roughly EC10 to EC40)

WRONG mental model (toxicology):
    "Span EC10 to EC90 to capture the full dose-response curve"
    → This gives you mostly dead cells, viability dominates all signals
    → Morphology channels all correlate ~0.97 because death drowns out biology

RIGHT mental model (operating point optimization):
    "Dense sampling in the shoulder region to find maximal morphology signal"
    → Focus on EC5 to EC40 where cells show stress but aren't dying
    → Include 1-2 higher doses to confirm where collapse occurs
    → Morphology channels can diverge because stress effects dominate, not death

═══════════════════════════════════════════════════════════════════════════════

Includes:
- 6 doses: Vehicle + 5 doses focused on the PRE-COLLAPSE SHOULDER
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
           docs/Cell_Thalamus_Dose_and_Timepoint_Calibration_2026-01-16.md
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


def _stable_hash(s: str) -> int:
    """Stable 32-bit hash for seed derivation. Same string always gives same int."""
    import hashlib

    return int(hashlib.sha256(s.encode()).hexdigest()[:8], 16)


@dataclass
class VarianceModel:
    """
    Variance model specification for a design.

    Defines how stochastic noise is applied during simulation.
    This is a property of the DESIGN, not the runner - ensuring reproducible
    and explainable variance behavior across all execution paths.

    Seed Derivation (critical for reproducibility across parallelism):
    - base_seed = hash(design_id) if derived_from_design_id=True, else seed_policy.base_seed
    - plate_seed = hash(base_seed, plate_id) - via StochasticBiologyHelper
    - well_seed = hash(base_seed, plate_id, well_id) - via StochasticBiologyHelper

    This ensures:
    - Same design re-run gives same distribution
    - Different wells/plates get different but deterministic seeds
    - Worker pool ordering doesn't affect results (no shared global RNG)
    """

    # Schema version for forward compatibility
    # Increment when adding new fields; from_dict handles missing fields gracefully
    VERSION: int = field(default=1, repr=False)

    # Master switch
    enabled: bool = True

    # Biology noise (vessel-level heterogeneity)
    # Default CVs are biologically realistic for typical cell lines
    biology_noise: dict = field(
        default_factory=lambda: {
            "enabled": True,
            "growth_cv": 0.12,  # 12% CV in growth rate (cell line variability)
            "stress_sensitivity_cv": 0.18,  # 18% CV in stress response (IC50 heterogeneity)
            "hazard_scale_cv": 0.15,  # 15% CV in death hazard (apoptotic priming)
            "ic50_cv": 0.20,  # 20% CV in induction sensitivity
            "plate_level_fraction": 0.3,  # 30% of variance is plate-to-plate
        }
    )

    # Injection noise (hardware artifacts) - disabled by default for Phase 0
    injection_noise: dict = field(
        default_factory=lambda: {
            "enabled": False,
            "modules": [],  # e.g., ["pipetting_variance", "mixing_gradients", "evaporation"]
        }
    )

    # Seed policy for reproducibility across parallelism
    seed_policy: dict = field(
        default_factory=lambda: {
            "base_seed": 42,  # Used if derived_from_design_id=False
            "derived_from_design_id": True,  # If True, base_seed = hash(design_id)
            "derivation": "plate_well_hash",  # How to derive per-well seeds
        }
    )

    # Preserve unknown keys for forward compatibility
    _extra: dict = field(default_factory=dict, repr=False)

    def get_base_seed(self, design_id: str) -> int:
        """
        Get base seed for this design.

        If derived_from_design_id=True, seed is hash(design_id) for reproducibility.
        Otherwise, uses the explicit base_seed from seed_policy.

        Args:
            design_id: The design identifier

        Returns:
            Base seed (32-bit int) for RNG initialization
        """
        if self.seed_policy.get("derived_from_design_id", True):
            return _stable_hash(design_id)
        return self.seed_policy.get("base_seed", 42)

    def to_bio_noise_config(self, design_id: str | None = None) -> dict:
        """
        Convert to BiologicalVirtualMachine bio_noise_config format.

        Args:
            design_id: Optional design_id for seed derivation. If None, uses base_seed.

        Returns:
            Config dict for BiologicalVirtualMachine constructor
        """
        if not self.enabled:
            return {"enabled": False}

        config = dict(self.biology_noise)

        # Include seed for reproducibility
        if design_id and self.seed_policy.get("derived_from_design_id", True):
            config["seed"] = self.get_base_seed(design_id)
        else:
            config["seed"] = self.seed_policy.get("base_seed", 42)

        return config

    def to_dict(self) -> dict:
        """Serialize for storage in design metadata."""
        result = {
            "version": self.VERSION,
            "enabled": self.enabled,
            "biology_noise": self.biology_noise,
            "injection_noise": self.injection_noise,
            "seed_policy": self.seed_policy,
        }
        # Preserve unknown keys for forward compatibility
        result.update(self._extra)
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "VarianceModel":
        """
        Deserialize from design metadata.

        Tolerant to missing fields (uses defaults) and unknown fields (preserved).
        This allows older code to roundtrip newer designs without data loss.
        """
        known_keys = {"version", "enabled", "biology_noise", "injection_noise", "seed_policy"}
        extra = {k: v for k, v in data.items() if k not in known_keys}

        # Default biology_noise if missing or empty
        default_bio = {
            "enabled": True,
            "growth_cv": 0.12,
            "stress_sensitivity_cv": 0.18,
            "hazard_scale_cv": 0.15,
            "ic50_cv": 0.20,
            "plate_level_fraction": 0.3,
        }
        bio_noise = data.get("biology_noise") or default_bio

        # Default seed_policy if missing
        default_seed = {
            "base_seed": 42,
            "derived_from_design_id": True,
            "derivation": "plate_well_hash",
        }
        seed_policy = data.get("seed_policy") or default_seed

        return cls(
            VERSION=data.get("version", 1),
            enabled=data.get("enabled", True),
            biology_noise=bio_noise,
            injection_noise=data.get("injection_noise", {"enabled": False, "modules": []}),
            seed_policy=seed_policy,
            _extra=extra,
        )

    @classmethod
    def deterministic(cls) -> "VarianceModel":
        """Create a deterministic (no noise) variance model for testing."""
        return cls(enabled=False)

    @classmethod
    def conservative(cls) -> "VarianceModel":
        """
        Conservative variance model with modest, well-documented CVs.

        Use when you want visible error bars without dominating the signal.
        These values are anchored to typical technical + biological variance
        observed in high-content imaging screens:

        Literature anchors:
        - Technical CV (plate-to-plate, well-to-well): 5-10% typical
          (Bray et al. 2016, Cell Painting; Ljosa et al. 2013)
        - Biological CV (cell line heterogeneity): 10-15% for growth rate
          (Singh et al. 2014, PLOS ONE)
        - IC50 heterogeneity: 15-20% CV is typical for cell populations
          (Fallahi-Sichani et al. 2013, Nature Chemical Biology)

        Total CV (technical + biological combined): expect 12-20% at transition
        region, 5-10% at extremes where response is saturated.
        """
        return cls(
            enabled=True,
            biology_noise={
                "enabled": True,
                "growth_cv": 0.08,  # 8% - conservative biological heterogeneity
                "stress_sensitivity_cv": 0.12,  # 12% - moderate IC50 spread
                "hazard_scale_cv": 0.10,  # 10% - conservative death rate variation
                "ic50_cv": 0.15,  # 15% - anchored to Fallahi-Sichani et al.
                "plate_level_fraction": 0.25,  # 25% plate-to-plate
            },
        )

    @classmethod
    def realistic(cls) -> "VarianceModel":
        """
        Realistic variance model for production simulations.

        These CVs are calibrated to produce error bars consistent with:
        1. Observed HCS screen variability (15-25% CV at transition doses)
        2. Single-cell response heterogeneity in oxidative stress
        3. Plate-to-plate batch effects in 384-well screens

        Literature anchors:
        - IC50 heterogeneity in cancer cell lines: 20-30% CV
          (Fallahi-Sichani et al. 2013, Nature Chemical Biology)
        - Cell-to-cell variation in drug response: up to 50% CV at EC50
          (Spencer et al. 2009, Nature; Bhola et al. 2020, Cell Systems)
        - Oxidative stress response heterogeneity in A549: 15-25% CV
          (based on NRF2 pathway activation variability)

        WARNING: This produces substantial variance at transition region
        (30-60% CV at doses near EC50). This is biologically realistic but
        may blur EC50 fitting if not accounted for in analysis.

        Use conservative() if you want tighter error bars.
        """
        return cls(
            enabled=True,
            biology_noise={
                "enabled": True,
                "growth_cv": 0.12,  # 12% - typical cell line variability
                "stress_sensitivity_cv": 0.18,  # 18% - high heterogeneity
                "hazard_scale_cv": 0.15,  # 15% - apoptotic priming variation
                "ic50_cv": 0.20,  # 20% - anchored to literature
                "plate_level_fraction": 0.30,  # 30% plate effects
            },
        )

    def describe(self) -> str:
        """Human-readable description for dashboard display."""
        if not self.enabled:
            return "Deterministic (no noise)"

        bio = self.biology_noise
        parts = [
            f"growth_cv={bio.get('growth_cv', 0)}",
            f"stress_cv={bio.get('stress_sensitivity_cv', 0)}",
            f"hazard_cv={bio.get('hazard_scale_cv', 0)}",
            f"plate_fraction={bio.get('plate_level_fraction', 0)}",
        ]

        if self.injection_noise.get("enabled"):
            modules = self.injection_noise.get("modules", [])
            parts.append(f"injection={modules}")

        return "Realistic: " + ", ".join(parts)


@dataclass
class MenadionePhase0Design:
    """
    Phase 0 design for Menadione dose-response calibration.

    ═══════════════════════════════════════════════════════════════════════════
    DOSE RANGE RATIONALE (see module docstring for full philosophy)
    ═══════════════════════════════════════════════════════════════════════════

    For Menadione in A549, empirical EC50 ≈ 8-9 µM (from simulation data).

    The dose range is designed to DENSELY SAMPLE THE PRE-COLLAPSE SHOULDER:

    | Dose   | ~EC    | Expected Viability | Purpose                          |
    |--------|--------|-------------------|----------------------------------|
    | 0 µM   | -      | ~97%              | Vehicle baseline                 |
    | 2 µM   | EC10   | ~90%              | Subthreshold, minimal effect     |
    | 4 µM   | EC20   | ~80%              | Early shoulder, stress begins    |
    | 6 µM   | EC30   | ~70%              | Mid-shoulder, morphology shifts  |
    | 8 µM   | EC40   | ~60%              | Upper shoulder, max info region  |
    | 15 µM  | EC80   | ~20%              | Past collapse, confirms cliff    |

    This gives us 4 doses (2-8 µM) in the information-rich shoulder region
    where morphology channels can diverge because stress effects dominate
    over viability scaling.

    The 15 µM dose serves as a "collapse anchor" to confirm where the cliff
    is, but should NOT be used for operating point selection.

    ═══════════════════════════════════════════════════════════════════════════

    Design matrix:
    - Cell line: A549 only (NRF2-primed, oxidative stress resistant)
    - Compound: Menadione (vitamin K3, redox cycler)
    - Doses: Vehicle (0) + 5 doses focused on pre-collapse shoulder
    - Timepoints: 24h (early response) and 48h (late response)
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

    Variance Model:
    - Phase 0 uses REALISTIC variance by default (enabled=True)
    - Biology noise: growth CV 12%, stress sensitivity CV 18%, hazard CV 15%
    - This produces meaningful error bars in dose-response curves
    - Can be overridden by passing variance_model=VarianceModel.deterministic()
    """

    design_id: str = field(default_factory=lambda: f"menadione_phase0_{uuid.uuid4().hex[:8]}")

    # Variance model - defines noise behavior for this design
    # Phase 0 defaults to REALISTIC because we need error bars
    variance_model: VarianceModel = field(default_factory=VarianceModel.realistic)
    cell_line: str = "A549"
    compound: str = "menadione"

    # ═══════════════════════════════════════════════════════════════════════
    # DOSE GRID - PRE-COLLAPSE SHOULDER FOCUS
    # ═══════════════════════════════════════════════════════════════════════
    #
    # Phase 0 goal: Find the region with MAXIMAL MORPHOLOGY SIGNAL before
    # viability collapse. This is NOT a toxicology kill-curve study.
    #
    # Empirical EC50 for Menadione in A549: ~8-9 µM (from simulation)
    #
    # WRONG: Span EC10 to EC90 (5, 15, 35, 75, 150 µM)
    #   → 4 of 5 doses are past viability collapse
    #   → All channels correlate ~0.97 because death dominates
    #   → Wastes plates measuring corpses
    #
    # RIGHT: Dense sampling in shoulder (2, 4, 6, 8 µM) + collapse anchor
    #   → 4 doses in 60-90% viability range where stress effects dominate
    #   → Morphology channels can diverge (stress-specific phenotypes)
    #   → One dose past collapse to confirm the cliff location
    #
    # See module docstring and class docstring for full rationale.
    # ═══════════════════════════════════════════════════════════════════════
    doses_uM: list[float] = field(
        default_factory=lambda: [
            0.0,  # Vehicle (DMSO) - baseline, ~97% viability
            2.0,  # ~EC10 - subthreshold, minimal effect, ~90% viability
            4.0,  # ~EC20 - early shoulder, stress begins, ~80% viability
            6.0,  # ~EC30 - mid-shoulder, morphology shifts, ~70% viability
            8.0,  # ~EC40 - upper shoulder, max info region, ~60% viability
            15.0,  # ~EC80 - COLLAPSE ANCHOR (not for operating point), ~20% viability
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

    # ═══════════════════════════════════════════════════════════════════════
    # REPLICATION CONSTANTS (single source of truth)
    # ═══════════════════════════════════════════════════════════════════════
    REPS_PER_DOSE_PER_PLATE: int = 53
    SENTINEL_VEHICLE_COUNT: int = 40
    SENTINEL_SHOULDER_COUNT: int = 12  # 6 µM
    SENTINEL_COLLAPSE_COUNT: int = 12  # 15 µM
    SENTINEL_TOTAL: int = 64  # 40 + 12 + 12
    EXPERIMENTAL_WELLS_PER_PLATE: int = 318  # 53 × 6 doses

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

        # ═══════════════════════════════════════════════════════════════════
        # INVARIANT: Template doses must EQUAL design doses (bidirectional)
        # ═══════════════════════════════════════════════════════════════════
        # This prevents TWO failure modes:
        # 1. "Template introduces rogue dose" - template has dose not in design
        # 2. "Design adds phantom dose" - design claims dose that never appears on plates
        #
        # Equality is the honest default. If you need flexibility, make it explicit
        # with design.doses_uM_experimental vs design.doses_uM_global.
        for template_id, template in self._templates.items():
            template_doses = set()
            for well in template.get_all_wells().values():
                template_doses.add(well["dose_uM"])
            design_doses = set(self.doses_uM)

            if template_doses != design_doses:
                in_template_not_design = template_doses - design_doses
                in_design_not_template = design_doses - template_doses
                msg_parts = [f"Template {template_id} doses != design doses."]
                if in_template_not_design:
                    msg_parts.append(f"On template but not in design: {in_template_not_design}")
                if in_design_not_template:
                    msg_parts.append(f"In design but not on template: {in_design_not_template}")
                msg_parts.append(f"Template has: {sorted(template_doses)}")
                msg_parts.append(f"Design has: {sorted(design_doses)}")
                raise AssertionError(" ".join(msg_parts))

    @property
    def reps_per_dose_per_timepoint(self) -> int:
        """
        Calculate replicates per dose per timepoint.

        Formula: REPS_PER_DOSE_PER_PLATE × plates_per_timepoint × passages
                 = 53 × 3 × 3 = 477

        This is the single source of truth for replication math.
        """
        return self.REPS_PER_DOSE_PER_PLATE * len(self.plates_per_timepoint) * len(self.passages)

    @property
    def total_plates(self) -> int:
        """Total plates in the design: passages × timepoints × plates_per_timepoint."""
        return len(self.passages) * len(self.timepoints_h) * len(self.plates_per_timepoint)

    @property
    def wells_per_plate(self) -> int:
        """Wells per plate: sentinels + experimental."""
        return self.SENTINEL_TOTAL + self.EXPERIMENTAL_WELLS_PER_PLATE

    @property
    def total_wells(self) -> int:
        """Total wells across all plates."""
        return self.total_plates * self.wells_per_plate

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
            # Variance model - critical for understanding error bars
            "variance_model": self.variance_model.to_dict(),
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


def create_menadione_design(
    variance_mode: str = "realistic",
) -> MenadionePhase0Design:
    """
    Factory function to create a Menadione Phase 0 design.

    Args:
        variance_mode: Variance model to use. One of:
            - "deterministic": No stochastic noise (for debugging/testing)
            - "conservative": Modest CVs with visible error bars
            - "realistic": Production-level variance (default)

    Returns:
        Configured MenadionePhase0Design with specified variance model
    """
    variance_models = {
        "deterministic": VarianceModel.deterministic,
        "conservative": VarianceModel.conservative,
        "realistic": VarianceModel.realistic,
    }

    if variance_mode not in variance_models:
        raise ValueError(
            f"Unknown variance_mode '{variance_mode}'. "
            f"Expected one of: {list(variance_models.keys())}"
        )

    return MenadionePhase0Design(variance_model=variance_models[variance_mode]())


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
    print(f"Replicates per dose/timepoint: {summary['reps_per_dose_timepoint']}")
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
