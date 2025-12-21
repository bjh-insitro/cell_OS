"""
Design Quality Checker: Scientific heuristics, not physics laws.

This module checks for common experimental design pitfalls:
- Observation time mismatch (treatment arms at different timepoints)
- Position confounding (spatial allocation differs by treatment)
- Batch confounding (treatments correlate with batch variables)

These are WARNINGS, not blockers. The world executes anything physically valid.
The agent decides whether to proceed with risky designs.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from collections import defaultdict

from .schemas import Proposal, WellSpec
from ..core.legacy_adapters import well_spec_to_well
from ..core.experiment import Well


@dataclass
class QualityWarning:
    """A single design quality issue."""
    category: str  # 'confluence_confounding', 'batch_confounding', etc.
    severity: str  # 'low', 'medium', 'high'
    message: str
    details: Dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return f"[{self.severity.upper()}] {self.category}: {self.message}"


@dataclass
class QualityReport:
    """Report on design quality."""
    warnings: List[QualityWarning] = field(default_factory=list)
    score: Optional[float] = None  # 0.0 (bad) to 1.0 (good)
    blocks_execution: bool = False  # Should almost always be False

    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0

    @property
    def high_severity_count(self) -> int:
        return sum(1 for w in self.warnings if w.severity == 'high')

    def summary(self) -> str:
        if not self.warnings:
            return "No design quality issues detected."

        counts = defaultdict(int)
        for w in self.warnings:
            counts[w.severity] += 1

        parts = [f"{count} {sev}" for sev, count in sorted(counts.items())]
        return f"Design quality issues: {', '.join(parts)}"


class DesignQualityChecker:
    """
    Checks for common experimental design pitfalls.

    Key principle: This returns WARNINGS, not exceptions.
    The world doesn't care about these. Only the agent does.
    """

    def __init__(self, strict_mode: bool = False):
        """
        Args:
            strict_mode: If True, high-severity warnings block execution.
                        Even then, blocks_execution is a flag, not an exception.
        """
        self.strict_mode = strict_mode

    def check(self, proposal: Proposal) -> QualityReport:
        """
        Check a proposal for design quality issues.

        Args:
            proposal: Agent's experiment proposal

        Returns:
            QualityReport with warnings (if any)
        """
        warnings = []

        # Convert to canonical Wells for analysis
        canonical_wells = [well_spec_to_well(spec) for spec in proposal.wells]

        # Check 1: Observation time mismatch
        time_warnings = self._check_observation_time_mismatch(canonical_wells)
        warnings.extend(time_warnings)

        # Check 2: Position confounding
        position_warnings = self._check_position_confounding(canonical_wells)
        warnings.extend(position_warnings)

        # Check 3: Batch confounding
        # (Placeholder - implement when agent supports multi-batch designs)
        batch_warnings = self._check_batch_confounding(proposal)
        warnings.extend(batch_warnings)

        # Compute quality score (optional)
        score = self._compute_quality_score(warnings)

        # Determine if execution should be blocked
        blocks = False
        if self.strict_mode:
            high_severity = sum(1 for w in warnings if w.severity == 'high')
            if high_severity > 0:
                blocks = True

        return QualityReport(
            warnings=warnings,
            score=score,
            blocks_execution=blocks
        )

    def _check_observation_time_mismatch(self, wells: List[Well]) -> List[QualityWarning]:
        """
        Check if treatment arms are observed at different times.

        Problem: Different observation_time_h means different cell densities/confluence,
        confounding treatment effects with density effects.

        This is the SYMPTOM. The CONSEQUENCE is confluence confounding.
        """
        warnings = []

        # Group wells by treatment
        groups = defaultdict(list)
        for well in wells:
            # Key = (compound, dose) to identify treatment arms
            key = (well.treatment.compound, well.treatment.dose_uM)
            groups[key].append(well)

        # Extract observation times by group
        times_by_group = {}
        for key, group_wells in groups.items():
            times = {w.observation_time_h for w in group_wells}
            times_by_group[key] = times

        # Check if control and treatment have different observation times
        control_key = ('DMSO', 0.0)
        if control_key in times_by_group:
            control_times = times_by_group[control_key]
            for key, times in times_by_group.items():
                if key == control_key:
                    continue

                if times != control_times:
                    warnings.append(QualityWarning(
                        category='observation_time_mismatch',
                        severity='high',
                        message=(
                            f"Treatment {key[0]}@{key[1]}µM observed at {sorted(times)}h "
                            f"but control observed at {sorted(control_times)}h"
                        ),
                        details={
                            'control_observation_times_h': sorted(control_times),
                            'treatment_observation_times_h': sorted(times),
                            'consequence': (
                                'Different observation times → different cell densities → '
                                'confluence confounding. Cannot separate treatment effect from density effect.'
                            ),
                            'recommendation': (
                                'Match observation_time_h across all treatment arms, '
                                'or stratify/adjust for density explicitly.'
                            )
                        }
                    ))

        return warnings

    def _check_position_confounding(self, wells: List[Well]) -> List[QualityWarning]:
        """
        Check if spatial allocation differs by treatment.

        Problem: Edge wells have different microenvironment (evaporation, temperature)
        than center wells. If treatment is correlated with position, effects are confounded.

        Note: We don't have position_tag in canonical Well, so we need to get it from
        the original proposal. For now, skip this check until we have proper location
        semantics in canonical Well.
        """
        # TODO: Implement once canonical Well has proper spatial semantics
        # For now, this check is disabled because canonical Well doesn't have position_tag
        return []

    def _check_batch_confounding(self, proposal: Proposal) -> List[QualityWarning]:
        """
        Check if treatments correlate with batch variables.

        Current agent doesn't specify batch structure, so this is a placeholder.
        When agent supports multi-day or multi-plate campaigns, implement this.
        """
        # Placeholder: agent currently runs single-plate, single-day
        # No batch structure to check
        return []

    def _compute_quality_score(self, warnings: List[QualityWarning]) -> float:
        """
        Compute overall quality score from warnings.

        Returns:
            Score in [0.0, 1.0] where 1.0 = perfect design
        """
        if not warnings:
            return 1.0

        # Simple penalty system
        penalty = 0.0
        for w in warnings:
            if w.severity == 'high':
                penalty += 0.3
            elif w.severity == 'medium':
                penalty += 0.15
            else:  # 'low'
                penalty += 0.05

        return max(0.0, 1.0 - penalty)
