"""
Causal contract enforcement for measurement functions.

Exports:
- enforce_measurement_contract: Decorator for VM assay entrypoints
- MeasurementContract: Declarative contract specification
- CausalContractViolation: Exception raised on violations
- Predefined contracts: CELL_PAINTING_CONTRACT, LDH_VIABILITY_CONTRACT, SCRNA_CONTRACT
- Violation recording: get_recorded_contract_violations, clear_recorded_contract_violations
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

__all__ = [
    # Core enforcement
    "enforce_measurement_contract",
    "MeasurementContract",
    "CausalContractViolation",
    "validate_measurement_output",

    # Predefined contracts
    "CELL_PAINTING_CONTRACT",
    "LDH_VIABILITY_CONTRACT",
    "SCRNA_CONTRACT",

    # Violation recording (for deterministic extraction)
    "get_recorded_contract_violations",
    "clear_recorded_contract_violations",
]
