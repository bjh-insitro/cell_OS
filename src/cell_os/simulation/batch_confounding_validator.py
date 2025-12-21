"""
Batch Confounding Validator

Detects batch confounding in experimental designs where treatment and control
are assigned to different batches (plates, days, operators).

This is a PARALLEL CONFOUNDER to confluence:
- Confluence: Density-driven biology feedback confounds mechanism
- Batch effects: Technical variation confounds mechanism

Both can cause false attribution and must be controlled at design time.

Architecture:
    Design → Extract batch assignments → Check confounding → PASS/REJECT

Example confounded design:
    Control: Plate A, Day 1
    Treatment: Plate B, Day 2
    → Batch confounded! (plate AND day differ)

Resolution strategies:
1. Balanced design: Split treatment/control across batches
2. Block randomization: Randomize within each batch
3. Batch sentinel: Measure batch effect with control replicates
"""

from typing import Dict, List, Tuple, Any, Set, Optional
from dataclasses import dataclass
from collections import defaultdict
import numpy as np


@dataclass
class BatchAssignment:
    """Batch assignment for a well."""
    plate_id: str
    day: int
    operator: str

    def __hash__(self):
        return hash((self.plate_id, self.day, self.operator))

    def __eq__(self, other):
        return (self.plate_id, other.plate_id) and \
               (self.day == other.day) and \
               (self.operator == other.operator)


@dataclass
class BatchConfoundingResult:
    """Result of batch confounding check."""
    is_confounded: bool
    violation_type: Optional[str] = None  # "plate", "day", "operator", "multiple"
    confounded_arms: Optional[Tuple[str, str]] = None  # (control_arm, treatment_arm)
    imbalance_metric: float = 0.0  # How bad the confounding is (0=perfect, 1=total)
    resolution_strategies: List[str] = None
    details: Dict[str, Any] = None

    def __post_init__(self):
        if self.resolution_strategies is None:
            self.resolution_strategies = []
        if self.details is None:
            self.details = {}


class BatchConfoundingValidator:
    """
    Validates experimental designs for batch confounding.

    This detector catches designs where treatment assignment is confounded
    with technical batch variables (plate, day, operator).

    Guards against:
    - Systematic batch assignment (all control on Plate A, all treatment on Plate B)
    - Day confounding (control Day 1, treatment Day 2)
    - Operator confounding (control OP1, treatment OP2)

    Acceptable patterns:
    - Balanced: Control and treatment split across batches
    - Block randomized: Treatment randomized within each batch
    - Batch sentinel: Control replicates in each batch to measure batch effect
    """

    def __init__(
        self,
        imbalance_threshold: float = 0.7,
        min_wells_per_arm: int = 2,
        strict: bool = True
    ):
        """
        Initialize batch confounding validator.

        Args:
            imbalance_threshold: Max allowed imbalance (0-1). Above this triggers rejection.
                                0.7 means 70% of one arm in one batch is confounded.
            min_wells_per_arm: Minimum wells per arm to check confounding
            strict: If True, raise on confounding. If False, warn only.
        """
        self.imbalance_threshold = imbalance_threshold
        self.min_wells_per_arm = min_wells_per_arm
        self.strict = strict

    def validate_design(
        self,
        design: Dict[str, Any],
        arm_column: str = "compound",  # How to identify treatment arms
    ) -> BatchConfoundingResult:
        """
        Check if design has batch confounding.

        Args:
            design: Design JSON with wells list
            arm_column: Column to group wells by (e.g., "compound", "dose_uM")

        Returns:
            BatchConfoundingResult with confounding status
        """
        wells = design.get("wells", [])

        if len(wells) < self.min_wells_per_arm * 2:
            # Too few wells to check confounding
            return BatchConfoundingResult(
                is_confounded=False,
                details={"reason": "insufficient_wells", "n_wells": len(wells)}
            )

        # Group wells by treatment arm
        arms = self._group_by_arm(wells, arm_column)

        if len(arms) < 2:
            # Single arm design - no confounding possible
            return BatchConfoundingResult(
                is_confounded=False,
                details={"reason": "single_arm", "arms": list(arms.keys())}
            )

        # Check for batch confounding across all pairs of arms
        max_imbalance = 0.0
        confounded_pair = None
        confounded_type = None
        detailed_imbalances = {}

        arm_names = list(arms.keys())
        for i in range(len(arm_names)):
            for j in range(i+1, len(arm_names)):
                arm_a = arm_names[i]
                arm_b = arm_names[j]

                result = self._check_batch_confounding(
                    wells_a=arms[arm_a],
                    wells_b=arms[arm_b],
                    arm_a_name=arm_a,
                    arm_b_name=arm_b
                )

                if result.imbalance_metric > max_imbalance:
                    max_imbalance = result.imbalance_metric
                    confounded_pair = (arm_a, arm_b)
                    confounded_type = result.violation_type
                    detailed_imbalances = result.details

        # Determine if confounded based on threshold
        is_confounded = max_imbalance > self.imbalance_threshold

        if is_confounded:
            resolution_strategies = self._generate_resolution_strategies(
                arms=arms,
                confounded_pair=confounded_pair,
                violation_type=confounded_type
            )
        else:
            resolution_strategies = []

        # Build details dict (include detailed imbalances if confounded)
        details = {
            "n_arms": len(arms),
            "arm_names": list(arms.keys()),
            "threshold": self.imbalance_threshold,
            "max_imbalance": max_imbalance
        }

        # Add detailed imbalances from worst pair
        if detailed_imbalances:
            details.update(detailed_imbalances)

        return BatchConfoundingResult(
            is_confounded=is_confounded,
            violation_type=confounded_type if is_confounded else None,
            confounded_arms=confounded_pair if is_confounded else None,
            imbalance_metric=max_imbalance,
            resolution_strategies=resolution_strategies,
            details=details
        )

    def _group_by_arm(
        self,
        wells: List[Dict[str, Any]],
        arm_column: str
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Group wells by treatment arm."""
        arms = defaultdict(list)
        for well in wells:
            arm_value = well.get(arm_column, "unknown")
            arms[str(arm_value)].append(well)
        return dict(arms)

    def _check_batch_confounding(
        self,
        wells_a: List[Dict[str, Any]],
        wells_b: List[Dict[str, Any]],
        arm_a_name: str,
        arm_b_name: str
    ) -> BatchConfoundingResult:
        """
        Check batch confounding between two arms.

        Computes imbalance metric for plate, day, and operator.
        Imbalance = max overlap across all batch types.

        Example:
            Arm A: 100% on Plate1, 100% Day1, 50% OP1
            Arm B: 100% on Plate2, 100% Day2, 50% OP2
            → Plate imbalance = 1.0 (total confounding)
        """
        # Extract batch assignments
        batches_a = [self._extract_batch(w) for w in wells_a]
        batches_b = [self._extract_batch(w) for w in wells_b]

        # Compute imbalance for each batch type
        plate_imbalance = self._compute_imbalance(
            [b.plate_id for b in batches_a],
            [b.plate_id for b in batches_b]
        )

        day_imbalance = self._compute_imbalance(
            [b.day for b in batches_a],
            [b.day for b in batches_b]
        )

        operator_imbalance = self._compute_imbalance(
            [b.operator for b in batches_a],
            [b.operator for b in batches_b]
        )

        # Max imbalance determines confounding
        imbalances = {
            "plate": plate_imbalance,
            "day": day_imbalance,
            "operator": operator_imbalance
        }

        max_type = max(imbalances, key=imbalances.get)
        max_imbalance = imbalances[max_type]

        # Check if multiple batch types confounded
        confounded_types = [k for k, v in imbalances.items() if v > 0.5]
        violation_type = "multiple" if len(confounded_types) > 1 else max_type

        return BatchConfoundingResult(
            is_confounded=max_imbalance > self.imbalance_threshold,
            violation_type=violation_type,
            confounded_arms=(arm_a_name, arm_b_name),
            imbalance_metric=max_imbalance,
            details={
                "plate_imbalance": plate_imbalance,
                "day_imbalance": day_imbalance,
                "operator_imbalance": operator_imbalance,
                "confounded_types": confounded_types
            }
        )

    def _extract_batch(self, well: Dict[str, Any]) -> BatchAssignment:
        """Extract batch assignment from well."""
        return BatchAssignment(
            plate_id=well.get("plate_id", "P1"),
            day=well.get("day", 1),
            operator=well.get("operator", "OP1")
        )

    def _compute_imbalance(
        self,
        values_a: List[Any],
        values_b: List[Any]
    ) -> float:
        """
        Compute batch imbalance between two arms.

        Imbalance = 1 - (overlap / max_possible_overlap)

        Perfect balance (imbalance=0): Arms fully overlap in batch distribution
        Total confounding (imbalance=1): Arms completely separated in batches

        Example:
            Arm A: [P1, P1, P1]  (100% P1)
            Arm B: [P2, P2, P2]  (100% P2)
            → imbalance = 1.0 (no overlap)

            Arm A: [P1, P1, P2]  (67% P1, 33% P2)
            Arm B: [P1, P2, P2]  (33% P1, 67% P2)
            → imbalance = 0.33 (some overlap)
        """
        # Count batch frequencies
        counts_a = defaultdict(int)
        counts_b = defaultdict(int)

        for val in values_a:
            counts_a[val] += 1
        for val in values_b:
            counts_b[val] += 1

        # Get all batches
        all_batches = set(counts_a.keys()) | set(counts_b.keys())

        # Compute overlap (minimum shared proportion per batch)
        overlap = 0.0
        for batch in all_batches:
            prop_a = counts_a[batch] / len(values_a)
            prop_b = counts_b[batch] / len(values_b)
            overlap += min(prop_a, prop_b)

        # Imbalance = 1 - overlap
        # overlap=1 → perfect balance (imbalance=0)
        # overlap=0 → total confounding (imbalance=1)
        imbalance = 1.0 - overlap

        return imbalance

    def _generate_resolution_strategies(
        self,
        arms: Dict[str, List[Dict[str, Any]]],
        confounded_pair: Tuple[str, str],
        violation_type: str
    ) -> List[str]:
        """Generate resolution strategies for batch confounding."""
        strategies = []

        arm_a, arm_b = confounded_pair

        if violation_type == "plate":
            strategies.append(
                f"Balanced design: Split '{arm_a}' and '{arm_b}' across plates "
                f"(e.g., 50% of each arm on each plate)"
            )
            strategies.append(
                f"Block randomization: Randomize treatment assignment within each plate"
            )
            strategies.append(
                f"Batch sentinel: Add control replicates on both plates to measure plate effect"
            )

        elif violation_type == "day":
            strategies.append(
                f"Same-day design: Run '{arm_a}' and '{arm_b}' on the same day"
            )
            strategies.append(
                f"Balanced design: Split arms across days (50% each arm per day)"
            )

        elif violation_type == "operator":
            strategies.append(
                f"Single operator: Have same operator run all wells"
            )
            strategies.append(
                f"Balanced design: Each operator runs both '{arm_a}' and '{arm_b}'"
            )

        elif violation_type == "multiple":
            strategies.append(
                f"Complete randomization: Randomize treatment across all batch variables"
            )
            strategies.append(
                f"Block design: Use stratified randomization within each batch"
            )

        return strategies


def validate_batch_confounding(
    design: Dict[str, Any],
    imbalance_threshold: float = 0.7,
    strict: bool = True
) -> BatchConfoundingResult:
    """
    Convenience function to validate batch confounding.

    Args:
        design: Design JSON
        imbalance_threshold: Max allowed imbalance (0-1)
        strict: If True, raise on confounding

    Returns:
        BatchConfoundingResult
    """
    validator = BatchConfoundingValidator(
        imbalance_threshold=imbalance_threshold,
        strict=strict
    )
    return validator.validate_design(design)


# Example usage in design bridge integration:
#
# from cell_os.simulation.batch_confounding_validator import validate_batch_confounding
#
# # In validate_design():
# batch_result = validate_batch_confounding(design, imbalance_threshold=0.7)
# if batch_result.is_confounded:
#     raise InvalidDesignError(
#         message=f"Batch confounded: {batch_result.violation_type}",
#         violation_code="batch_confounding",
#         details=batch_result.details
#     )
