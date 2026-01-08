"""
Run Narrative Generator.

v0.6.2: Converts JSONL artifacts → structured court transcript.

Not prose. A structured story showing:
- Cycle-by-cycle calibration state
- Regime changes
- Confidence with caps/refusals and reasons
- Rewards earned
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Dict, Any, Optional, Sequence
import yaml


@dataclass
class CycleRecord:
    """Record for a single cycle."""
    cycle: int
    timestamp: Optional[str] = None

    # Calibration state
    calibration_wells: int = 0
    noise_sigma_stable: bool = False
    coverage_match: bool = False
    provenance: Dict[str, int] = field(default_factory=dict)

    # Regime
    regime: Optional[str] = None
    regime_changed: bool = False

    # Confidence
    confidence: float = 0.0
    confidence_source: Optional[str] = None
    was_capped: bool = False
    cap_reasons: List[str] = field(default_factory=list)

    # Refusal
    refused: bool = False
    refusal_reason: Optional[str] = None
    refusal_justified: Optional[bool] = None

    # Reward
    honesty_score: Optional[float] = None
    accuracy_score: Optional[float] = None

    # Events
    events: List[str] = field(default_factory=list)


@dataclass
class RunNarrative:
    """Complete narrative for a run."""
    run_id: Optional[str] = None
    total_cycles: int = 0
    cycles: List[CycleRecord] = field(default_factory=list)

    # Summary stats
    total_refusals: int = 0
    total_caps: int = 0
    total_regime_shifts: int = 0
    final_confidence: float = 0.0
    cumulative_honesty_score: float = 0.0

    # Verdict
    honesty_violations: int = 0
    verdict: str = "UNKNOWN"

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "total_cycles": self.total_cycles,
            "summary": {
                "total_refusals": self.total_refusals,
                "total_caps": self.total_caps,
                "total_regime_shifts": self.total_regime_shifts,
                "final_confidence": self.final_confidence,
                "cumulative_honesty_score": self.cumulative_honesty_score,
                "honesty_violations": self.honesty_violations,
                "verdict": self.verdict,
            },
            "cycles": [asdict(c) for c in self.cycles],
        }

    def to_yaml(self) -> str:
        return yaml.dump(self.to_dict(), default_flow_style=False, sort_keys=False)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


class NarrativeGenerator:
    """Generates structured narratives from run artifacts."""

    def __init__(self):
        self._prev_regime: Optional[str] = None

    def generate(
        self,
        artifacts: Sequence[Dict[str, Any]],
        run_id: Optional[str] = None,
    ) -> RunNarrative:
        """Generate narrative from artifacts.

        Args:
            artifacts: List of decision/event dicts from JSONL
            run_id: Optional run identifier

        Returns:
            RunNarrative with cycle-by-cycle records
        """
        self._prev_regime = None
        cycles_map: Dict[int, CycleRecord] = {}

        for artifact in artifacts:
            cycle_num = artifact.get("cycle", 0)

            if cycle_num not in cycles_map:
                cycles_map[cycle_num] = CycleRecord(cycle=cycle_num)

            record = cycles_map[cycle_num]
            self._process_artifact(record, artifact)

        # Sort cycles and build narrative
        cycles = [cycles_map[k] for k in sorted(cycles_map.keys())]

        # Compute summary
        narrative = RunNarrative(
            run_id=run_id,
            total_cycles=len(cycles),
            cycles=cycles,
            total_refusals=sum(1 for c in cycles if c.refused),
            total_caps=sum(1 for c in cycles if c.was_capped),
            total_regime_shifts=sum(1 for c in cycles if c.regime_changed),
            final_confidence=cycles[-1].confidence if cycles else 0.0,
            cumulative_honesty_score=sum(
                c.honesty_score or 0.0 for c in cycles
            ),
        )

        # Determine verdict (simple heuristic)
        if narrative.honesty_violations > 0:
            narrative.verdict = "FAILED"
        elif narrative.total_caps > 0 or narrative.total_refusals > 0:
            narrative.verdict = "HONEST_WITH_CONSTRAINTS"
        else:
            narrative.verdict = "CLEAN"

        return narrative

    def _process_artifact(self, record: CycleRecord, artifact: Dict) -> None:
        """Process a single artifact into the cycle record."""
        record.timestamp = artifact.get("timestamp", record.timestamp)

        # Extract confidence receipt if present
        receipt = artifact.get("confidence_receipt", {})
        if receipt:
            record.confidence = receipt.get("confidence_value", record.confidence)
            record.confidence_source = receipt.get("confidence_source")
            record.was_capped = receipt.get("was_capped", False)

            caps = receipt.get("caps_applied", [])
            record.cap_reasons = [c.get("reason", "") for c in caps]

            cal = receipt.get("calibration_support", {})
            record.noise_sigma_stable = cal.get("noise_sigma_stable", False)
            record.coverage_match = cal.get("coverage_match", False)
            record.calibration_wells = cal.get("provenance_total_wells", 0)
            record.provenance = {
                "center": cal.get("provenance_center_wells", 0),
                "edge": cal.get("provenance_edge_wells", 0),
            }

            ev = receipt.get("evidence_support", {})
            if ev:
                record.events.append(f"Evidence: {ev.get('n_wells_used', 0)} wells")

        # Extract rationale if present
        rationale = artifact.get("rationale", {})
        if rationale:
            regime = rationale.get("regime")
            if regime:
                if self._prev_regime is not None and regime != self._prev_regime:
                    record.regime_changed = True
                    record.events.append(f"Regime shift: {self._prev_regime} → {regime}")
                record.regime = regime
                self._prev_regime = regime

        # Extract refusal info
        if artifact.get("refused", False):
            record.refused = True
            record.refusal_reason = artifact.get("refusal_reason")
            record.refusal_justified = artifact.get("refusal_justified")
            record.events.append(f"Refused: {record.refusal_reason}")

        # Extract scores
        if "honesty_score" in artifact:
            record.honesty_score = artifact["honesty_score"]
        if "accuracy_score" in artifact:
            record.accuracy_score = artifact["accuracy_score"]


def generate_narrative(
    artifacts: List[Dict],
    run_id: Optional[str] = None,
) -> RunNarrative:
    """Generate a run narrative from artifacts.

    Args:
        artifacts: List of decision/event dicts
        run_id: Optional run identifier

    Returns:
        RunNarrative
    """
    generator = NarrativeGenerator()
    return generator.generate(artifacts, run_id)


def generate_narrative_from_jsonl(path: Path, run_id: Optional[str] = None) -> RunNarrative:
    """Generate narrative from JSONL file.

    Args:
        path: Path to JSONL file
        run_id: Optional run identifier (defaults to filename)

    Returns:
        RunNarrative
    """
    artifacts = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                artifacts.append(json.loads(line))

    return generate_narrative(artifacts, run_id or path.stem)


# CLI entrypoint
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python run_narrative.py <path_to_jsonl> [--yaml|--json]")
        sys.exit(1)

    path = Path(sys.argv[1])
    output_format = "yaml"
    if "--json" in sys.argv:
        output_format = "json"

    narrative = generate_narrative_from_jsonl(path)

    if output_format == "json":
        print(narrative.to_json())
    else:
        print(narrative.to_yaml())
