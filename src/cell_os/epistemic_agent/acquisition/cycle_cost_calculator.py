"""
Composite cost calculator for experimental cycles.

Provides a simple API for batch sizing decisions by composing costs from
existing unit operations (imaging.py, analysis.py).

This is a WRAPPER around the existing cost infrastructure, not a replacement.
It queries the parametric unit ops to get costs, ensuring consistency with
WCB/MCB workflows and BOM tracking.
"""

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

# Import existing unit ops infrastructure
from cell_os.unit_ops.parametric import ParametricOps
from cell_os.unit_ops.base import VesselLibrary
from cell_os.inventory import Inventory


@dataclass
class CycleCostBreakdown:
    """Detailed cost breakdown for one experimental cycle."""
    plate_cost: float
    media_cost: float
    staining_cost: float
    ldh_assay_cost: float
    imaging_time_cost: float
    analyst_time_cost: float
    marginal_well_cost: float  # Cost per additional well (media + staining + LDH per well)

    @property
    def fixed_cost(self) -> float:
        """Fixed costs incurred regardless of well count."""
        return self.plate_cost + self.imaging_time_cost + self.analyst_time_cost

    @property
    def total_cost_baseline(self) -> float:
        """Total cost for minimal experiment (plate + baseline wells)."""
        # Assume baseline of 12 wells for comparison
        return self.fixed_cost + (12 * self.marginal_well_cost)

    def total_cost(self, n_wells: int) -> float:
        """Total cost for experiment using n_wells."""
        return self.fixed_cost + (n_wells * self.marginal_well_cost)

    def cost_per_df(self, n_wells: int, df_gain: int) -> float:
        """Cost per degree of freedom gained."""
        if df_gain <= 0:
            return float('inf')
        return self.total_cost(n_wells) / df_gain


class CycleCostCalculator:
    """Calculator for experimental cycle costs using existing unit ops.

    This is a WRAPPER around ParametricOps that composes costs from
    existing operations to provide a simple API for batch sizing.
    """

    def __init__(self, vessel_lib: VesselLibrary = None, inventory: Inventory = None):
        """Initialize calculator with unit ops infrastructure.

        Args:
            vessel_lib: Vessel library (created if None)
            inventory: Inventory system (created if None)
        """
        # Initialize unit ops infrastructure if not provided
        if vessel_lib is None:
            repo_root = Path(__file__).parent.parent.parent.parent.parent
            vessel_yaml = repo_root / "data" / "raw" / "vessels.yaml"
            vessel_lib = VesselLibrary(str(vessel_yaml) if vessel_yaml.exists() else None)

        if inventory is None:
            # Create inventory from database
            repo_root = Path(__file__).parent.parent.parent.parent.parent
            db_path = repo_root / "data" / "cell_os_inventory.db"
            inventory = self._create_inventory_from_db(str(db_path))

        # Create parametric ops with inventory
        self.ops = ParametricOps(vessel_lib, inventory)
        self.inventory = inventory

    def _create_inventory_from_db(self, db_path: str) -> Inventory:
        """Create Inventory object from SQLite database."""
        from cell_os.inventory import Resource

        inventory = Inventory()

        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT item_id, name, category, vendor, catalog_number,
                       pack_size, pack_unit, pack_price_usd, unit_price_usd
                FROM inventory_items
            """)
            rows = cursor.fetchall()

            for row in rows:
                item_id, name, category, vendor, catalog_number, pack_size, pack_unit, pack_price, unit_price = row
                if unit_price is not None:
                    resource = Resource(
                        resource_id=item_id,
                        name=name or item_id,
                        vendor=vendor or "Unknown",
                        catalog_number=catalog_number or "",
                        pack_size=pack_size or 1.0,
                        pack_unit=pack_unit or "unit",
                        pack_price_usd=pack_price or 0.0,
                        logical_unit=pack_unit or "unit",
                        unit_price_usd=float(unit_price),
                        category=category or "general",
                        stock_level=1000.0,  # Dummy stock
                    )
                    inventory.resources[item_id] = resource

            conn.close()
        except sqlite3.Error as e:
            print(f"Warning: Could not load pricing database: {e}")

        return inventory

    def compute_cell_painting_cycle_cost(
        self,
        vessel_id: str = "plate_384well",
        n_wells: int = 384,
        analyst_hours: float = 2.0,
        analyst_cost_per_hour: float = 75.0
    ) -> CycleCostBreakdown:
        """Compute full cost for one Cell Painting + LDH cycle using existing unit ops.

        This WRAPS the existing parametric unit ops to compute costs, ensuring
        consistency with WCB/MCB workflows and proper BOM tracking.

        Fixed costs (per cycle):
        - 384-well plate: $32.92 (from inventory DB)
        - Imaging time: from op_imaging (microscope amortization)
        - Analyst time: ~$150 (2h × $75/hr for setup, staining, analysis)
        Total fixed: ~$343

        Marginal costs (per well):
        - Cell Painting stains: from op_cell_painting (5-channel, $0.94/well)
        - LDH assay: from op_ldh_assay ($0.52/test)
        Total marginal: ~$1.47/well

        Args:
            vessel_id: Vessel ID (default: plate_384well)
            n_wells: Number of wells to use
            analyst_hours: Analyst time for cycle setup/execution
            analyst_cost_per_hour: Analyst labor cost ($/hr)

        Returns:
            CycleCostBreakdown with detailed cost components
        """
        # Get plate cost from inventory
        plate_cost = self.inventory.get_price("phenoplate_384")

        # Use existing ops to compute costs
        # IMPORTANT: vessel working_volume_ml for plate_384well is 0.05 mL (per well)
        # So ops return per-well costs, not full-plate costs

        # op_cell_painting includes MitoTracker, fixation, permeabilization, staining cocktail
        staining_op = self.ops.op_cell_painting(vessel_id)

        # op_imaging computes microscope time cost for FULL PLATE (384 wells)
        imaging_op = self.ops.op_imaging(vessel_id, channels=5, fields=9)

        # op_ldh_assay computes LDH reagent + plate reader cost for n_wells
        ldh_op = self.ops.op_ldh_assay(vessel_id, num_wells=n_wells)

        # Fixed costs (per cycle, regardless of wells used)
        # Imaging: microscope time for full plate
        imaging_time_cost = imaging_op.instrument_cost_usd

        # Staining: liquid handler run for full plate
        staining_instrument_cost = staining_op.instrument_cost_usd

        # LDH: plate reader time for reading full plate
        ldh_instrument_cost = ldh_op.instrument_cost_usd

        # Analyst labor
        analyst_time_cost = analyst_hours * analyst_cost_per_hour

        # Marginal costs (per well)
        # staining_op.material_cost_usd is ALREADY per-well cost (vessel volume = 0.05 mL = 1 well)
        staining_per_well = staining_op.material_cost_usd

        # LDH assay: op returns total cost for n_wells, so divide by n_wells
        ldh_per_well = ldh_op.material_cost_usd / n_wells if n_wells > 0 else 0.0

        # Media cost (not in staining_op, need to add separately)
        # TODO: Should op_seed_plate be included in the cycle cost?
        media_per_well = 0.008  # Placeholder from previous calculation

        marginal_well_cost = media_per_well + staining_per_well + ldh_per_well

        return CycleCostBreakdown(
            plate_cost=plate_cost,
            media_cost=media_per_well,
            staining_cost=staining_per_well,
            ldh_assay_cost=ldh_per_well,
            imaging_time_cost=imaging_time_cost + staining_instrument_cost + ldh_instrument_cost,
            analyst_time_cost=analyst_time_cost,
            marginal_well_cost=marginal_well_cost
        )

    def compute_baseline_cycle_cost(self) -> CycleCostBreakdown:
        """Compute cost for standard Cell Painting + LDH cycle with defaults.

        This is the canonical cost model for batch sizing decisions.

        Returns:
            CycleCostBreakdown with default parameters
        """
        return self.compute_cell_painting_cycle_cost()


# Singleton instance for use by batch sizing
_calculator_instance: Optional[CycleCostCalculator] = None


def get_cycle_cost_calculator() -> CycleCostCalculator:
    """Get or create singleton calculator instance."""
    global _calculator_instance
    if _calculator_instance is None:
        _calculator_instance = CycleCostCalculator()
    return _calculator_instance


def get_cycle_cost_breakdown() -> CycleCostBreakdown:
    """Get standard cycle cost breakdown for batch sizing.

    This is the main entry point for batch sizing decisions.

    Returns:
        CycleCostBreakdown with costs from inventory database
    """
    calculator = get_cycle_cost_calculator()
    return calculator.compute_baseline_cycle_cost()


if __name__ == "__main__":
    # Demo: show actual costs from database
    calc = CycleCostCalculator()
    breakdown = calc.compute_baseline_cycle_cost()

    print("=" * 70)
    print("CELL PAINTING + LDH CYCLE COST BREAKDOWN")
    print("=" * 70)
    print("\nFixed Costs (per cycle):")
    print(f"  384-well plate:        ${breakdown.plate_cost:.2f}")
    print(f"  Imaging time:          ${breakdown.imaging_time_cost:.2f}")
    print(f"  Analyst time:          ${breakdown.analyst_time_cost:.2f}")
    print(f"  TOTAL FIXED:           ${breakdown.fixed_cost:.2f}")

    print("\nMarginal Costs (per well):")
    print(f"  Media (seeding):       ${breakdown.media_cost:.3f}")
    print(f"  Cell Painting stains:  ${breakdown.staining_cost:.3f}")
    print(f"  LDH assay:             ${breakdown.ldh_assay_cost:.3f}")
    print(f"  TOTAL MARGINAL:        ${breakdown.marginal_well_cost:.3f}")

    print("\nExample Cycle Costs:")
    for n_wells in [12, 50, 100, 192, 384]:
        total = breakdown.total_cost(n_wells)
        cost_per_well = total / n_wells
        print(f"  {n_wells:3d} wells: ${total:6.2f} total (${cost_per_well:.2f}/well)")

    print("\n" + "=" * 70)
    print("Key Insight: Fixed costs dominate!")
    print("=" * 70)
    print(f"  12 wells:  ${breakdown.total_cost(12):.2f} → ${breakdown.total_cost(12)/12:.2f}/well")
    print(f"  192 wells: ${breakdown.total_cost(192):.2f} → ${breakdown.total_cost(192)/192:.2f}/well")
    print(f"  Savings: {(breakdown.total_cost(12)/12) / (breakdown.total_cost(192)/192):.1f}x cheaper per well at scale")
