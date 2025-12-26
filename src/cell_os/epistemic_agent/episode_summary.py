"""
Episode-level governance: the ledger that prevents death by 1000 locally-optimal choices.

This module provides EpisodeSummary, a structured accounting of:
- What we spent (plates, wells, time, edge wells used, actions taken)
- What we learned (epistemic gain components, variance reduction, gate status)
- What we sacrificed (health debt, mitigation actions, contract violations)

The uncomfortable truth: "reward went up" is not a unit of progress.
This ledger forces the loop to answer: what did you accomplish, and at what cost?

Design principles:
- No vibes, only receipts (aggregated from contract reports and belief events)
- Mitigation timeline with triggers and outcomes
- Instrument health time series (not just final state)
- Budget efficiency: cost per bit of information gained
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime


@dataclass
class BudgetSpending:
    """What we spent this episode."""
    total_wells: int = 0
    total_plates: float = 0.0
    wells_by_action_type: Dict[str, int] = field(default_factory=dict)  # {science: N, mitigation: M, epistemic: K}
    edge_wells_used: int = 0  # Risky edge wells (high spatial bias)
    calibration_wells: int = 0  # Wells spent on calibration/DMSO/baseline
    exploration_wells: int = 0  # Wells spent on science experiments


@dataclass
class EpistemicLearning:
    """What we learned this episode."""
    total_gain_bits: float = 0.0  # Cumulative epistemic gain (realized - expected)
    variance_reduction: Optional[float] = None  # Noise CI width: start → end
    gates_earned: List[str] = field(default_factory=list)  # ["noise_sigma", "ldh", "cell_paint"]
    gates_lost: List[str] = field(default_factory=list)  # Gates revoked during episode
    final_calibration_entropy: float = 0.0  # Remaining uncertainty about measurement quality
    compounds_tested: int = 0
    model_confidence: Optional[float] = None  # Placeholder for future: posterior confidence


@dataclass
class HealthSacrifices:
    """What we sacrificed this episode."""
    health_debt_accumulated: float = 0.0  # Sum of QC violations (Moran's I excess, nuclei CV excess)
    health_debt_repaid: float = 0.0  # Sum of mitigation improvements
    mitigation_actions: List[Dict[str, Any]] = field(default_factory=list)  # Timeline of mitigation cycles
    contract_violations: int = 0  # Count of contract violations (should always be 0)
    epistemic_debt_max: float = 0.0  # Peak epistemic debt during episode
    epistemic_refusals: int = 0  # Count of actions refused due to debt


@dataclass
class MitigationEvent:
    """Single mitigation action with trigger and outcome."""
    cycle: int
    trigger_cycle: int  # Which cycle flagged the issue
    action: str  # REPLATE, REPLICATE, CALIBRATE
    trigger_reason: str  # "spatial_qc_flag", "high_uncertainty"
    morans_i_before: Optional[float] = None
    morans_i_after: Optional[float] = None
    uncertainty_before: Optional[float] = None
    uncertainty_after: Optional[float] = None
    cost_wells: int = 0
    reward: Optional[float] = None  # Mitigation or epistemic reward
    rationale: str = ""


@dataclass
class InstrumentHealthTimeSeries:
    """Instrument health evolution over episode."""
    cycles: List[int] = field(default_factory=list)
    nuclei_cv_max: List[float] = field(default_factory=list)  # Per-cycle worst nuclei CV
    morans_i_max: List[float] = field(default_factory=list)  # Per-cycle worst spatial autocorrelation
    segmentation_quality_min: List[float] = field(default_factory=list)  # Per-cycle worst segmentation
    noise_rel_width: List[Optional[float]] = field(default_factory=list)  # Noise CI width over time


@dataclass
class EpisodeSummary:
    """
    Complete episode accounting: spending vs learning vs sacrifices.

    This is the answer to: "What is the unit of progress?"

    Per-episode metrics:
    - Efficiency: bits gained per plate spent
    - Quality: health debt vs repayment balance
    - Coverage: gates earned, compounds tested, exploration breadth
    - Integrity: contract violations (should be zero)

    Written at end of episode, read by benchmarks and audits.
    """

    # Episode metadata
    run_id: str
    seed: int
    cycles_completed: int
    start_time: str
    end_time: str
    abort_reason: Optional[str] = None

    # Ledger sections
    spending: BudgetSpending = field(default_factory=BudgetSpending)
    learning: EpistemicLearning = field(default_factory=EpistemicLearning)
    sacrifices: HealthSacrifices = field(default_factory=HealthSacrifices)

    # Timeline
    mitigation_timeline: List[MitigationEvent] = field(default_factory=list)
    instrument_health: InstrumentHealthTimeSeries = field(default_factory=InstrumentHealthTimeSeries)

    # Aggregate metrics
    efficiency_bits_per_plate: Optional[float] = None  # learning / spending
    health_balance: Optional[float] = None  # repaid - accumulated
    exploration_ratio: Optional[float] = None  # exploration_wells / total_wells

    def compute_aggregate_metrics(self):
        """Compute derived metrics from ledger sections."""
        # Efficiency: information gained per resource spent
        if self.spending.total_plates > 0 and self.learning.total_gain_bits > 0:
            self.efficiency_bits_per_plate = self.learning.total_gain_bits / self.spending.total_plates
        else:
            self.efficiency_bits_per_plate = 0.0

        # Health balance: did we pay down debt or accumulate it?
        self.health_balance = self.sacrifices.health_debt_repaid - self.sacrifices.health_debt_accumulated

        # Exploration ratio: science vs calibration
        if self.spending.total_wells > 0:
            self.exploration_ratio = self.spending.exploration_wells / self.spending.total_wells
        else:
            self.exploration_ratio = 0.0

    def to_dict(self) -> dict:
        """Serialize to JSON for persistence."""
        return {
            "run_id": self.run_id,
            "seed": self.seed,
            "cycles_completed": self.cycles_completed,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "abort_reason": self.abort_reason,
            "spending": {
                "total_wells": self.spending.total_wells,
                "total_plates": self.spending.total_plates,
                "wells_by_action_type": self.spending.wells_by_action_type,
                "edge_wells_used": self.spending.edge_wells_used,
                "calibration_wells": self.spending.calibration_wells,
                "exploration_wells": self.spending.exploration_wells,
            },
            "learning": {
                "total_gain_bits": self.learning.total_gain_bits,
                "variance_reduction": self.learning.variance_reduction,
                "gates_earned": self.learning.gates_earned,
                "gates_lost": self.learning.gates_lost,
                "final_calibration_entropy": self.learning.final_calibration_entropy,
                "compounds_tested": self.learning.compounds_tested,
                "model_confidence": self.learning.model_confidence,
            },
            "sacrifices": {
                "health_debt_accumulated": self.sacrifices.health_debt_accumulated,
                "health_debt_repaid": self.sacrifices.health_debt_repaid,
                "mitigation_actions": self.sacrifices.mitigation_actions,
                "contract_violations": self.sacrifices.contract_violations,
                "epistemic_debt_max": self.sacrifices.epistemic_debt_max,
                "epistemic_refusals": self.sacrifices.epistemic_refusals,
            },
            "mitigation_timeline": [
                {
                    "cycle": e.cycle,
                    "trigger_cycle": e.trigger_cycle,
                    "action": e.action,
                    "trigger_reason": e.trigger_reason,
                    "morans_i_before": e.morans_i_before,
                    "morans_i_after": e.morans_i_after,
                    "uncertainty_before": e.uncertainty_before,
                    "uncertainty_after": e.uncertainty_after,
                    "cost_wells": e.cost_wells,
                    "reward": e.reward,
                    "rationale": e.rationale,
                }
                for e in self.mitigation_timeline
            ],
            "instrument_health": {
                "cycles": self.instrument_health.cycles,
                "nuclei_cv_max": self.instrument_health.nuclei_cv_max,
                "morans_i_max": self.instrument_health.morans_i_max,
                "segmentation_quality_min": self.instrument_health.segmentation_quality_min,
                "noise_rel_width": self.instrument_health.noise_rel_width,
            },
            "efficiency_bits_per_plate": self.efficiency_bits_per_plate,
            "health_balance": self.health_balance,
            "exploration_ratio": self.exploration_ratio,
        }

    def summary_text(self) -> str:
        """Human-readable summary for logging."""
        lines = [
            "="*60,
            "EPISODE SUMMARY",
            "="*60,
            f"Run: {self.run_id} (seed={self.seed})",
            f"Cycles: {self.cycles_completed}",
            "",
            "SPENDING:",
            f"  Total: {self.spending.total_wells} wells ({self.spending.total_plates:.2f} plates)",
            f"  Calibration: {self.spending.calibration_wells} wells",
            f"  Exploration: {self.spending.exploration_wells} wells",
            f"  Edge wells: {self.spending.edge_wells_used} (risky)",
            "",
            "LEARNING:",
            f"  Total gain: {self.learning.total_gain_bits:.2f} bits",
            f"  Gates earned: {', '.join(self.learning.gates_earned) if self.learning.gates_earned else 'none'}",
            f"  Gates lost: {', '.join(self.learning.gates_lost) if self.learning.gates_lost else 'none'}",
            f"  Final entropy: {self.learning.final_calibration_entropy:.2f} bits",
            f"  Compounds tested: {self.learning.compounds_tested}",
        ]

        if self.learning.variance_reduction is not None:
            lines.append(f"  Variance reduction: {self.learning.variance_reduction:.4f}")

        lines.extend([
            "",
            "SACRIFICES:",
            f"  Health debt accumulated: {self.sacrifices.health_debt_accumulated:.2f}",
            f"  Health debt repaid: {self.sacrifices.health_debt_repaid:.2f}",
            f"  Balance: {self.health_balance:+.2f}",
            f"  Mitigation actions: {len(self.sacrifices.mitigation_actions)}",
            f"  Contract violations: {self.sacrifices.contract_violations}",
            f"  Epistemic refusals: {self.sacrifices.epistemic_refusals}",
        ])

        if self.sacrifices.epistemic_debt_max > 0:
            lines.append(f"  Peak epistemic debt: {self.sacrifices.epistemic_debt_max:.2f} bits")

        lines.extend([
            "",
            "EFFICIENCY:",
            f"  Bits per plate: {self.efficiency_bits_per_plate:.3f}" if self.efficiency_bits_per_plate else "  Bits per plate: N/A",
            f"  Exploration ratio: {self.exploration_ratio:.1%}" if self.exploration_ratio else "  Exploration ratio: N/A",
            "",
        ])

        if self.mitigation_timeline:
            lines.append("MITIGATION TIMELINE:")
            for event in self.mitigation_timeline:
                lines.append(f"  Cycle {event.cycle}: {event.action} (trigger: {event.trigger_reason})")
                if event.morans_i_before is not None:
                    lines.append(f"    Moran's I: {event.morans_i_before:.3f} → {event.morans_i_after:.3f}")
                if event.uncertainty_before is not None:
                    lines.append(f"    Uncertainty: {event.uncertainty_before:.2f} → {event.uncertainty_after:.2f} bits")
                lines.append(f"    Cost: {event.cost_wells} wells, Reward: {event.reward:+.2f}")
            lines.append("")

        if self.abort_reason:
            lines.extend([
                "ABORT:",
                f"  {self.abort_reason}",
                "",
            ])

        lines.append("="*60)
        return "\n".join(lines)
