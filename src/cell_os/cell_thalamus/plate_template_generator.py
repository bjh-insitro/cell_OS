"""
Plate Template Generator for Phase 0 Menadione Calibration

Generates 3 pre-defined plate templates (A, B, C) for 384-well plates:
- Fixed sentinel positions (same on every plate)
- Randomized experimental positions (different per template)
- Stratified spatial balance (edge/center, time bins)

Templates are reused across passages per VarP specification.
"""

from dataclasses import dataclass, field
from typing import Any

from cell_os.experimental_design.plate_allocator import (
    PlateAllocator,
    TreatmentRequest,
    WellAssignment,
)


@dataclass
class PlateTemplate:
    """A complete 384-well plate template with sentinel and experimental wells."""

    template_id: str
    seed: int
    sentinel_assignments: list[dict[str, Any]]
    experimental_assignments: list[WellAssignment]

    def get_all_wells(self) -> dict[str, dict[str, Any]]:
        """Get all well assignments as a dict keyed by well position."""
        wells = {}

        # Add sentinels
        for sentinel in self.sentinel_assignments:
            wells[sentinel["well_position"]] = {
                "treatment_id": sentinel["treatment_id"],
                "dose_uM": sentinel["dose_uM"],
                "is_sentinel": True,
                "sentinel_type": sentinel["sentinel_type"],
                "zone": sentinel["zone"],
            }

        # Add experimental
        for exp in self.experimental_assignments:
            wells[exp.well_position] = {
                "treatment_id": exp.treatment_id,
                "dose_uM": float(exp.treatment_id.split("_")[1].replace("uM", "")),
                "is_sentinel": False,
                "zone": exp.zone,
                "time_bin": exp.time_bin,
                "row": exp.row,
                "col": exp.col,
            }

        return wells

    def get_summary(self) -> dict[str, Any]:
        """Get template summary statistics."""
        all_wells = self.get_all_wells()
        sentinels = [w for w in all_wells.values() if w["is_sentinel"]]
        experimental = [w for w in all_wells.values() if not w["is_sentinel"]]

        # Count by dose
        dose_counts = {}
        for w in experimental:
            dose = w["dose_uM"]
            dose_counts[dose] = dose_counts.get(dose, 0) + 1

        # Edge/center balance
        exp_edge = sum(1 for w in experimental if w["zone"] == "edge")
        exp_center = len(experimental) - exp_edge

        return {
            "template_id": self.template_id,
            "seed": self.seed,
            "total_wells": len(all_wells),
            "sentinel_wells": len(sentinels),
            "experimental_wells": len(experimental),
            "dose_counts": dose_counts,
            "experimental_edge": exp_edge,
            "experimental_center": exp_center,
            "edge_fraction": exp_edge / len(experimental) if experimental else 0,
        }


@dataclass
class Phase0TemplateGenerator:
    """
    Generates plate templates for Phase 0 Menadione calibration.

    Creates 3 templates (A, B, C) with:
    - Fixed sentinel positions (identical across templates)
    - Randomized experimental positions (different per template)
    """

    # Doses for experimental wells
    doses_uM: list[float] = field(default_factory=lambda: [0.0, 5.0, 15.0, 35.0, 75.0, 150.0])

    # Replicates per dose per plate (to fill 384-well plate)
    reps_per_dose: int = 53

    # Template seeds (deterministic, different per template)
    template_seeds: dict[str, int] = field(
        default_factory=lambda: {"A": 1001, "B": 2002, "C": 3003}
    )

    def _get_fixed_sentinel_positions(self) -> list[dict[str, Any]]:
        """
        Define fixed sentinel positions (same on every plate).

        Layout strategy:
        - Vehicle sentinels: corners + edges for edge effect quantification
        - Mild menadione (15 µM): fixed interior positions for SPC
        - Strong menadione (75 µM): fixed interior positions for SPC

        Total: 64 sentinel wells
        """
        sentinels = []

        # Vehicle sentinels (40 total)
        # Corners (4)
        vehicle_corners = ["A01", "A24", "P01", "P24"]
        # Edge positions - spread along outer ring (16 more)
        vehicle_edges = [
            "A06",
            "A12",
            "A18",  # Top edge
            "P06",
            "P12",
            "P18",  # Bottom edge
            "D01",
            "H01",
            "L01",  # Left edge
            "D24",
            "H24",
            "L24",  # Right edge
            "A03",
            "A21",
            "P03",
            "P21",  # Additional corners
        ]
        # Interior positions (20 more) - spread across plate
        vehicle_interior = [
            "C03",
            "C08",
            "C13",
            "C18",
            "C22",
            "F05",
            "F10",
            "F15",
            "F20",
            "J05",
            "J10",
            "J15",
            "J20",
            "M03",
            "M08",
            "M13",
            "M18",
            "M22",
            "G12",
            "K12",  # Center column
        ]

        for pos in vehicle_corners + vehicle_edges + vehicle_interior:
            sentinels.append(
                {
                    "well_position": pos,
                    "treatment_id": "sentinel_vehicle",
                    "dose_uM": 0.0,
                    "sentinel_type": "vehicle",
                    "zone": "edge" if pos in vehicle_corners + vehicle_edges else "center",
                }
            )

        # Mild menadione sentinels (12 total) - 15 µM
        mild_positions = [
            # Fixed SPC positions (same across all plates)
            "E06",
            "E19",
            "L06",
            "L19",
            # Scattered for position effects
            "D11",
            "D14",
            "G08",
            "G17",
            "J08",
            "J17",
            "M11",
            "M14",
        ]
        for pos in mild_positions:
            sentinels.append(
                {
                    "well_position": pos,
                    "treatment_id": "sentinel_mild",
                    "dose_uM": 15.0,
                    "sentinel_type": "mild_menadione",
                    "zone": "center",
                }
            )

        # Strong menadione sentinels (12 total) - 75 µM
        strong_positions = [
            # Fixed SPC positions
            "E08",
            "E17",
            "L08",
            "L17",
            # Scattered for position effects
            "D09",
            "D16",
            "G06",
            "G19",
            "J06",
            "J19",
            "M09",
            "M16",
        ]
        for pos in strong_positions:
            sentinels.append(
                {
                    "well_position": pos,
                    "treatment_id": "sentinel_strong",
                    "dose_uM": 75.0,
                    "sentinel_type": "strong_menadione",
                    "zone": "center",
                }
            )

        return sentinels

    def _get_available_wells(self, sentinel_positions: set[str]) -> list[str]:
        """Get all wells not reserved for sentinels."""
        all_wells = []
        rows = [chr(ord("A") + i) for i in range(16)]  # A-P
        cols = range(1, 25)  # 1-24

        for row in rows:
            for col in cols:
                well_pos = f"{row}{col:02d}"
                if well_pos not in sentinel_positions:
                    all_wells.append(well_pos)

        return all_wells

    def generate_template(self, template_id: str) -> PlateTemplate:
        """
        Generate a single plate template.

        Args:
            template_id: "A", "B", or "C"

        Returns:
            PlateTemplate with fixed sentinels and randomized experimental wells
        """
        if template_id not in self.template_seeds:
            raise ValueError(f"Unknown template_id: {template_id}")

        seed = self.template_seeds[template_id]

        # Get fixed sentinel positions
        sentinels = self._get_fixed_sentinel_positions()
        sentinel_positions = {s["well_position"] for s in sentinels}

        # Get available wells for experimental
        available_wells = self._get_available_wells(sentinel_positions)

        # Create treatment requests for allocator
        treatments = []
        for dose in self.doses_uM:
            treatments.append(
                TreatmentRequest(
                    treatment_id=f"menadione_{dose}uM",
                    n_replicates=self.reps_per_dose,
                    metadata={"dose_uM": dose},
                )
            )

        # Check capacity
        total_reps = sum(t.n_replicates for t in treatments)
        if total_reps > len(available_wells):
            raise ValueError(
                f"Too many replicates ({total_reps}) for available wells "
                f"({len(available_wells)} after {len(sentinels)} sentinels)"
            )

        # Use PlateAllocator for stratified randomization
        allocator = PlateAllocator(plate_format=384, seed=seed)

        # Filter allocator's well metadata to only available wells
        # (This is a workaround - ideally PlateAllocator would accept a well mask)
        original_metadata = allocator._well_metadata.copy()
        allocator._well_metadata = {
            k: v for k, v in original_metadata.items() if k in available_wells
        }

        # Allocate
        experimental_assignments = allocator.allocate(treatments)

        return PlateTemplate(
            template_id=template_id,
            seed=seed,
            sentinel_assignments=sentinels,
            experimental_assignments=experimental_assignments,
        )

    def generate_all_templates(self) -> dict[str, PlateTemplate]:
        """Generate all 3 templates (A, B, C)."""
        return {tid: self.generate_template(tid) for tid in self.template_seeds.keys()}


def create_phase0_templates() -> dict[str, PlateTemplate]:
    """Factory function to create Phase 0 plate templates."""
    generator = Phase0TemplateGenerator()
    return generator.generate_all_templates()


if __name__ == "__main__":
    # Generate and display templates
    templates = create_phase0_templates()

    print("=" * 70)
    print("PHASE 0 MENADIONE PLATE TEMPLATES")
    print("=" * 70)

    for tid, template in templates.items():
        summary = template.get_summary()
        print(f"\nTemplate {tid} (seed={summary['seed']}):")
        print(f"  Total wells: {summary['total_wells']}")
        print(f"  Sentinels: {summary['sentinel_wells']}")
        print(f"  Experimental: {summary['experimental_wells']}")
        print(f"  Edge fraction: {summary['edge_fraction']:.2%}")
        print("  Dose distribution:")
        for dose, count in sorted(summary["dose_counts"].items()):
            print(f"    {dose:>6.1f} µM: {count} wells")

    # Verify templates are different
    print("\n" + "=" * 70)
    print("TEMPLATE COMPARISON")
    print("=" * 70)

    template_a = templates["A"].get_all_wells()
    template_b = templates["B"].get_all_wells()
    template_c = templates["C"].get_all_wells()

    # Check sentinel positions are identical
    sentinel_a = {k for k, v in template_a.items() if v["is_sentinel"]}
    sentinel_b = {k for k, v in template_b.items() if v["is_sentinel"]}
    sentinel_c = {k for k, v in template_c.items() if v["is_sentinel"]}

    print(f"\nSentinel positions identical: {sentinel_a == sentinel_b == sentinel_c}")

    # Check experimental positions differ
    exp_a = {k: v["dose_uM"] for k, v in template_a.items() if not v["is_sentinel"]}
    exp_b = {k: v["dose_uM"] for k, v in template_b.items() if not v["is_sentinel"]}

    matching = sum(1 for k in exp_a if k in exp_b and exp_a[k] == exp_b[k])
    print(
        f"Experimental positions matching A↔B: {matching}/{len(exp_a)} ({matching/len(exp_a):.1%})"
    )
    print("  (Should be ~16.7% by chance for 6 doses)")
