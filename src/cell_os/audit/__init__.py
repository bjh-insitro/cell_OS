"""
Audit tools for epistemic honesty verification.

v0.6.2: Post-hoc verification and run narratives.
"""

from .verify_run_honesty import (
    HonestyVerifier,
    VerificationResult,
    Violation,
    ViolationType,
    verify_jsonl_file,
    verify_artifacts,
)

from .run_narrative import (
    NarrativeGenerator,
    RunNarrative,
    CycleRecord,
    generate_narrative,
    generate_narrative_from_jsonl,
)

__all__ = [
    # Verifier
    "HonestyVerifier",
    "VerificationResult",
    "Violation",
    "ViolationType",
    "verify_jsonl_file",
    "verify_artifacts",
    # Narrative
    "NarrativeGenerator",
    "RunNarrative",
    "CycleRecord",
    "generate_narrative",
    "generate_narrative_from_jsonl",
]
