"""
Injection: Plate Map Execution Error (Rare Catastrophic Failures)

PROBLEM: Execution doesn't match design. Rare, but ruins entire plate.

This is NOT noise - it's **systematic mismapping** between intent and reality.
The robot executed the wrong plate map.

Error Types:
1. Column shift: All dispensing offset by N columns (±1, ±2)
2. Row swap: Two rows swapped (e.g., A ↔ H)
3. Reagent swap: Two compound IDs swapped in worklist
4. Dilution ladder error: Wrong serial dilution (off-by-one, reversed)

State Variables:
- error_active: Is there an execution error?
- error_type: Which error occurred
- error_parameters: Type-specific params (shift amount, swapped IDs, etc.)
- affected_wells: Which wells have wrong treatment

Exploits Blocked:
- "Execution matches design": Sometimes it doesn't
- "Dose-response is smooth": Column shift breaks it
- "Anchors are where I think": They might be shifted
- "Replicates cluster": Shifted replicates don't cluster

Real-World Motivation:
- Robot teaching error: Column indexing off by one
- Worklist typo: Swapped source plates
- Pipetting path error: Dispense order reversed
- Human error: Wrong reagent in wrong position
- Rare but real: ~0.5-2% of plates

Signature (Forensics):
- Column shift: Dose-response shifted spatially, anchors in wrong position
- Row swap: Treatment effects in wrong rows
- Reagent swap: "Impossible" mechanism clustering
- Detectable with: Sentinels, anchors, cross-plate consistency

Defeat Conditions:
- **Anchors**: Known phenotypes appear in wrong wells → flag error
- **Sentinels**: Replicate tiles don't match → flag error
- **Barcode checks**: Verify plate/reagent identity before execution
- **CANNOT PREVENT**: Human/robot errors happen
- **CAN DETECT**: With proper controls
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Tuple
from enum import Enum
import numpy as np
from .base import InjectionState, Injection, InjectionContext


class PlateMapErrorType(Enum):
    """Types of plate map execution errors."""
    NONE = "none"
    COLUMN_SHIFT = "column_shift"  # All columns offset by N
    ROW_SWAP = "row_swap"  # Two rows swapped
    REAGENT_SWAP = "reagent_swap"  # Two compounds swapped
    DILUTION_REVERSED = "dilution_reversed"  # Dose ladder backwards


@dataclass
class PlateMapErrorState(InjectionState):
    """
    Per-plate execution error state.

    This is NOT well-specific - errors affect entire plate systematically.
    """
    error_active: bool = False
    error_type: PlateMapErrorType = PlateMapErrorType.NONE
    error_parameters: Dict[str, Any] = field(default_factory=dict)
    affected_wells: List[str] = field(default_factory=list)
    forensic_signature: str = ""  # How to detect this error

    def check_invariants(self) -> None:
        """Errors are plate-level, not well-level."""
        if self.error_active:
            assert self.error_type != PlateMapErrorType.NONE
            assert len(self.error_parameters) > 0


class PlateMapErrorInjection(Injection):
    """
    Catastrophic but detectable plate map execution errors.

    Tests whether agent has sanity checks:
    - Do anchors appear where expected?
    - Do replicates cluster?
    - Is dose-response monotonic?
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.config = config or {}

        # Error rate (Bernoulli per plate)
        self.error_probability = self.config.get('error_probability', 0.02)  # 2% of plates

        # Error type distribution
        self.error_type_weights = self.config.get('error_type_weights', {
            PlateMapErrorType.COLUMN_SHIFT: 0.5,  # Most common
            PlateMapErrorType.ROW_SWAP: 0.2,
            PlateMapErrorType.REAGENT_SWAP: 0.2,
            PlateMapErrorType.DILUTION_REVERSED: 0.1
        })

    def initialize_state(self, ctx: InjectionContext, rng: np.random.Generator) -> PlateMapErrorState:
        """
        Sample whether this plate has an execution error.

        Errors are rare (p ~ 0.02) but catastrophic when they occur.
        """
        state = PlateMapErrorState()

        # Bernoulli: does this plate have an error?
        if rng.random() < self.error_probability:
            state.error_active = True

            # Sample error type
            types = list(self.error_type_weights.keys())
            weights = list(self.error_type_weights.values())
            weights = np.array(weights) / sum(weights)  # Normalize
            state.error_type = rng.choice(types, p=weights)

            # Generate error-specific parameters
            state.error_parameters = self._generate_error_parameters(
                error_type=state.error_type,
                ctx=ctx,
                rng=rng
            )

            state.forensic_signature = self._get_forensic_signature(state.error_type)

        return state

    def _generate_error_parameters(
        self,
        error_type: PlateMapErrorType,
        ctx: InjectionContext,
        rng: np.random.Generator
    ) -> Dict[str, Any]:
        """Generate error-specific parameters."""
        if error_type == PlateMapErrorType.COLUMN_SHIFT:
            # Shift by ±1 or ±2 columns
            shift_amount = rng.choice([-2, -1, 1, 2])
            return {
                'shift_amount': shift_amount,
                'description': f"All columns shifted by {shift_amount}"
            }

        elif error_type == PlateMapErrorType.ROW_SWAP:
            # Swap two rows (often edge rows: A↔H, B↔G)
            rows = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
            row1, row2 = rng.choice(rows, size=2, replace=False)
            return {
                'row1': row1,
                'row2': row2,
                'description': f"Rows {row1} and {row2} swapped"
            }

        elif error_type == PlateMapErrorType.REAGENT_SWAP:
            # Two reagent IDs swapped in worklist
            # (Specific reagents not known here - applied during execution)
            return {
                'swap_pair_index': rng.integers(0, 100),  # Placeholder
                'description': "Two reagents swapped in worklist"
            }

        elif error_type == PlateMapErrorType.DILUTION_REVERSED:
            # Dose ladder dispensed in reverse order
            return {
                'description': "Dilution ladder reversed (high↔low doses)"
            }

        return {}

    def _get_forensic_signature(self, error_type: PlateMapErrorType) -> str:
        """How to detect this error."""
        signatures = {
            PlateMapErrorType.COLUMN_SHIFT: "Anchors appear in wrong columns; dose-response spatially shifted",
            PlateMapErrorType.ROW_SWAP: "Treatment effects in wrong rows; row-specific cell lines swapped",
            PlateMapErrorType.REAGENT_SWAP: "Mechanism clustering impossible; anchors show wrong phenotype",
            PlateMapErrorType.DILUTION_REVERSED: "Dose-response inverted; high-dose wells show low effect"
        }
        return signatures.get(error_type, "Unknown")

    def apply_column_shift(
        self,
        well_id: str,
        intended_col: int,
        shift_amount: int,
        n_cols: int = 24
    ) -> int:
        """
        Apply column shift to well assignment.

        Args:
            well_id: Original well ID (e.g., "A5")
            intended_col: Column as designed
            shift_amount: Shift by this many columns
            n_cols: Total columns in plate

        Returns:
            Actual executed column (with wraparound)
        """
        # Shift with wraparound
        actual_col = (intended_col + shift_amount - 1) % n_cols + 1
        return actual_col

    def apply_row_swap(
        self,
        well_id: str,
        intended_row: str,
        row1: str,
        row2: str
    ) -> str:
        """
        Apply row swap to well assignment.

        Args:
            well_id: Original well ID
            intended_row: Row as designed
            row1, row2: Swapped row pair

        Returns:
            Actual executed row
        """
        if intended_row == row1:
            return row2
        elif intended_row == row2:
            return row1
        else:
            return intended_row

    def transform_well_assignment(
        self,
        state: PlateMapErrorState,
        intended_well_id: str,
        intended_treatment: Dict[str, Any]
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Transform intended well assignment based on execution error.

        This is the core hook: what agent THINKS vs what ACTUALLY happened.

        Args:
            state: Plate map error state
            intended_well_id: Well ID from plate design
            intended_treatment: Treatment as designed

        Returns:
            (actual_well_id, actual_treatment)
        """
        if not state.error_active:
            return intended_well_id, intended_treatment

        # Parse well ID
        row = intended_well_id[0]
        col = int(intended_well_id[1:])

        actual_well_id = intended_well_id
        actual_treatment = intended_treatment.copy()

        if state.error_type == PlateMapErrorType.COLUMN_SHIFT:
            shift = state.error_parameters['shift_amount']
            actual_col = self.apply_column_shift(intended_well_id, col, shift)
            actual_well_id = f"{row}{actual_col}"

        elif state.error_type == PlateMapErrorType.ROW_SWAP:
            row1 = state.error_parameters['row1']
            row2 = state.error_parameters['row2']
            actual_row = self.apply_row_swap(intended_well_id, row, row1, row2)
            actual_well_id = f"{actual_row}{col}"

        elif state.error_type == PlateMapErrorType.REAGENT_SWAP:
            # Reagent swap applied at compound level (not spatial)
            # Would need access to full plate map to swap specific compounds
            # For now, flag that swap occurred
            actual_treatment['_reagent_swap_occurred'] = True

        elif state.error_type == PlateMapErrorType.DILUTION_REVERSED:
            # If this well is part of a dose-response ladder, reverse its dose
            if 'dose_uM' in actual_treatment and actual_treatment['dose_uM'] > 0:
                # Mark that dose should be reversed (needs ladder context)
                actual_treatment['_dose_reversed'] = True

        return actual_well_id, actual_treatment

    def generate_forensic_report(self, state: PlateMapErrorState) -> Dict[str, Any]:
        """
        Generate forensic report for error detection.

        This is what a SMART agent would check.
        """
        if not state.error_active:
            return {'error_detected': False}

        report = {
            'error_detected': True,
            'error_type': state.error_type.value,
            'error_description': state.error_parameters.get('description', 'Unknown'),
            'forensic_signature': state.forensic_signature,
            'detection_methods': []
        }

        # Suggest detection methods
        if state.error_type == PlateMapErrorType.COLUMN_SHIFT:
            report['detection_methods'] = [
                "Check anchor phenotypes against expected columns",
                "Verify dose-response spatial pattern",
                "Cross-reference sentinel replicates"
            ]

        elif state.error_type == PlateMapErrorType.ROW_SWAP:
            report['detection_methods'] = [
                "Check cell line assignment by row",
                "Verify treatment effects in expected rows",
                "Compare row-wise phenotype distributions"
            ]

        elif state.error_type == PlateMapErrorType.REAGENT_SWAP:
            report['detection_methods'] = [
                "Verify anchor compounds produce expected phenotypes",
                "Check mechanism clustering consistency",
                "Cross-plate compound identity validation"
            ]

        elif state.error_type == PlateMapErrorType.DILUTION_REVERSED:
            report['detection_methods'] = [
                "Check dose-response monotonicity",
                "Verify high-dose wells show strong effects",
                "Compare ladder direction to design"
            ]

        return report

    def get_state_summary(self, state: PlateMapErrorState) -> Dict[str, Any]:
        """Summary for logging."""
        return {
            'error_active': state.error_active,
            'error_type': state.error_type.value if state.error_active else 'none',
            'error_description': state.error_parameters.get('description', 'None'),
            'forensic_signature': state.forensic_signature if state.error_active else 'None'
        }
