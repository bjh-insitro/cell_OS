#!/usr/bin/env python3
"""
Reusable KPI extraction utilities for epistemic agent benchmarking.

v0.4.2: Reads decisions.jsonl for regime transitions and forced-calibration rate.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional, List


def extract_gate_kpis(run_data: Dict, beliefs: Dict) -> Dict[str, Any]:
    """Extract gate-related KPIs from run data.

    KPIs:
    - gate_earned: Did agent earn noise gate?
    - rel_width_final: Final relative CI width
    - df_final: Final degrees of freedom
    - gate_slack: How much tighter than threshold (0.25)?
    - cycles_to_gate: How many cycles to earn gate?
    - abort_reason: Why did run end?
    - integrity_warnings: Missing evidence files?
    """
    gate_earned = beliefs.get("noise_sigma_stable", False)
    rel_width_final = beliefs.get("noise_rel_width")
    df_final = beliefs.get("noise_df_total", 0)

    # Gate slack: how much better than threshold?
    gate_slack = None
    if rel_width_final is not None and gate_earned:
        gate_slack = 0.25 - rel_width_final  # positive = better than threshold

    # Cycles to gate: scan evidence file for first gate_event
    cycles_to_gate = None
    paths = run_data.get("paths", {})
    evidence_file = Path(run_data.get("paths", {}).get("evidence", ""))

    if evidence_file.exists():
        with open(Path(evidence_file).parent / evidence_file.name) as f:
            for line in f:
                event = json.loads(line)
                if event.get("belief", "").startswith("gate_event:noise_sigma"):
                    cycles_to_gate = event.get("cycle")
                    break

    return {
        "gate_earned": gate_earned,
        "rel_width_final": rel_width_final,
        "df_final": df_final,
        "gate_slack": gate_slack,
        "cycles_to_gate": cycles_to_gate,
        "cycles_completed": run_data.get("cycles_completed", 0),
        "abort_reason": run_data.get("abort_reason"),
        "integrity_warnings": run_data.get("integrity_warnings", []),
    }


def extract_decision_kpis(run_data: Dict) -> Dict[str, Any]:
    """Extract decision provenance KPIs from decisions.jsonl.

    KPIs:
    - forced_calibration_rate: Fraction of cycles where calibration was forced
    - first_in_gate_cycle: First cycle where regime == "in_gate"
    - gate_revocation_count: How many times gate was lost
    - regime_distribution: Count of cycles per regime
    - abort_cycle: Cycle where abort occurred (if any)
    - abort_template: Which abort template triggered
    """
    paths = run_data.get("paths", {})
    decisions_file = Path(run_data.get("paths", {}).get("decisions", ""))

    if not decisions_file.exists():
        return {
            "forced_calibration_rate": None,
            "first_in_gate_cycle": None,
            "gate_revocation_count": 0,
            "regime_distribution": {},
            "abort_cycle": None,
            "abort_template": None,
            "decisions_missing": True,
        }

    decisions = []
    with open(Path(decisions_file).parent / decisions_file.name) as f:
        for line in f:
            decisions.append(json.loads(line))

    # Count forced calibration
    forced_count = sum(1 for d in decisions if d.get("selected_candidate", {}).get("forced", False))
    forced_rate = forced_count / len(decisions) if decisions else 0.0

    # Find first in-gate cycle
    first_in_gate = None
    for d in decisions:
        regime = d.get("selected_candidate", {}).get("regime")
        if regime == "in_gate":
            first_in_gate = d.get("cycle")
            break

    # Count gate revocations
    revocation_count = sum(
        1 for d in decisions
        if d.get("selected_candidate", {}).get("regime") == "gate_revoked"
    )

    # Regime distribution
    regime_counts: Dict[str, int] = {}
    for d in decisions:
        regime = d.get("selected_candidate", {}).get("regime", "unknown")
        regime_counts[regime] = regime_counts.get(regime, 0) + 1

    # Abort info
    abort_cycle = None
    abort_template = None
    for d in decisions:
        if d.get("selected", "").startswith("abort"):
            abort_cycle = d.get("cycle")
            abort_template = d.get("selected")
            break

    return {
        "forced_calibration_rate": forced_rate,
        "first_in_gate_cycle": first_in_gate,
        "gate_revocation_count": revocation_count,
        "regime_distribution": regime_counts,
        "abort_cycle": abort_cycle,
        "abort_template": abort_template,
        "decisions_missing": False,
    }


def extract_all_kpis(run_json_path: Path) -> Dict[str, Any]:
    """Extract all KPIs from a run JSON file.

    Args:
        run_json_path: Path to the run JSON file

    Returns:
        Dict with all KPIs (gate + decision)
    """
    with open(run_json_path) as f:
        run_data = json.load(f)

    beliefs = run_data.get("beliefs_final", {})

    gate_kpis = extract_gate_kpis(run_data, beliefs)
    decision_kpis = extract_decision_kpis(run_data)

    return {
        **gate_kpis,
        **decision_kpis,
        "run_json": str(run_json_path.name),
    }
