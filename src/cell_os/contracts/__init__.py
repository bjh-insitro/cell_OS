"""
Contract enforcement for cell_OS invariants.

Contracts are runtime-checked specifications that:
1. Document invariants formally
2. Fail loudly on violation (no silent corruption)
3. Provide forensic evidence for debugging

Exports:
- Measurement contracts: enforce_measurement_contract, MeasurementContract, etc.
- Conservation contracts: conserved_death, assert_conservation, ConservationViolation
- Debt contracts: debt_enforced, check_debt_threshold, DebtViolation
"""

from .causal_contract import (
    CausalContractViolation,
    MeasurementContract,
    enforce_measurement_contract,
    get_recorded_contract_violations,
    clear_recorded_contract_violations,
    validate_measurement_output,
)

from .measurement_contracts import (
    CELL_PAINTING_CONTRACT,
    LDH_VIABILITY_CONTRACT,
    SCRNA_CONTRACT,
)

from .conservation import (
    ConservationViolation,
    assert_conservation,
    conserved_death,
    check_monotonicity,
)

from .debt import (
    DEBT_HARD_BLOCK_THRESHOLD,
    CALIBRATION_ACTION_TYPES,
    DebtViolation,
    is_calibration_action,
    check_debt_threshold,
    debt_enforced,
    compute_cost_multiplier,
)

__all__ = [
    # Measurement contracts
    "enforce_measurement_contract",
    "MeasurementContract",
    "CausalContractViolation",
    "validate_measurement_output",
    "CELL_PAINTING_CONTRACT",
    "LDH_VIABILITY_CONTRACT",
    "SCRNA_CONTRACT",
    "get_recorded_contract_violations",
    "clear_recorded_contract_violations",
    # Conservation contracts
    "ConservationViolation",
    "assert_conservation",
    "conserved_death",
    "check_monotonicity",
    # Debt contracts
    "DEBT_HARD_BLOCK_THRESHOLD",
    "CALIBRATION_ACTION_TYPES",
    "DebtViolation",
    "is_calibration_action",
    "check_debt_threshold",
    "debt_enforced",
    "compute_cost_multiplier",
]
