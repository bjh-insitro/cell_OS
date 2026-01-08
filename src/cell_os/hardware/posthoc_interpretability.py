"""
Post-Hoc Interpretability per Feala's Closed-Loop Manifesto.

"Comprehension after competence - Extracting interpretability from
working systems post hoc, not before deployment"

Extract understanding AFTER optimization succeeds, not as a prerequisite.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from collections import defaultdict


@dataclass
class ActionPattern:
    """A discovered pattern in successful action sequences."""
    description: str
    frequency: float  # How often this pattern appears in successes
    confidence: float  # Statistical confidence
    examples: List[str] = field(default_factory=list)


@dataclass
class Hypothesis:
    """A testable hypothesis extracted from patterns."""
    statement: str
    supporting_evidence: List[str]
    confidence: float
    falsifiable_prediction: str


@dataclass
class InterpretabilityReport:
    """Summary of post-hoc understanding extracted from runs."""
    patterns: List[ActionPattern]
    hypotheses: List[Hypothesis]
    key_insights: List[str]
    recommendations: List[str]


class PostHocInterpretability:
    """Extract understanding AFTER optimization succeeds."""

    def __init__(self):
        self.successful_runs = []
        self.failed_runs = []

    def add_run(self, run_data: Dict, success: bool):
        """Add a run's data for analysis."""
        if success:
            self.successful_runs.append(run_data)
        else:
            self.failed_runs.append(run_data)

    def extract_patterns(self) -> List[ActionPattern]:
        """Mine patterns from successful experiments."""
        patterns = []

        # Pattern: Action sequences that appear in successful runs
        action_counts = defaultdict(int)
        for run in self.successful_runs:
            actions = run.get('actions', [])
            for action in actions:
                action_counts[str(action)] += 1

        total = len(self.successful_runs) or 1
        for action, count in sorted(action_counts.items(), key=lambda x: -x[1])[:5]:
            patterns.append(ActionPattern(
                description=f"Action '{action}' in successful runs",
                frequency=count / total,
                confidence=min(0.95, count / total + 0.1),
            ))

        return patterns

    def generate_hypotheses(self) -> List[Hypothesis]:
        """Generate testable hypotheses from patterns."""
        hypotheses = []
        patterns = self.extract_patterns()

        for p in patterns[:3]:
            hypotheses.append(Hypothesis(
                statement=f"Using {p.description} improves outcomes",
                supporting_evidence=[f"Observed in {p.frequency:.0%} of successes"],
                confidence=p.confidence,
                falsifiable_prediction=f"Removing this action should reduce success rate"
            ))

        return hypotheses

    def generate_report(self) -> InterpretabilityReport:
        """Generate full interpretability report."""
        patterns = self.extract_patterns()
        hypotheses = self.generate_hypotheses()

        insights = []
        if self.successful_runs:
            insights.append(f"Analyzed {len(self.successful_runs)} successful runs")
        if patterns:
            insights.append(f"Found {len(patterns)} recurring patterns")

        recommendations = []
        for h in hypotheses[:2]:
            recommendations.append(f"Test: {h.falsifiable_prediction}")

        return InterpretabilityReport(
            patterns=patterns,
            hypotheses=hypotheses,
            key_insights=insights,
            recommendations=recommendations
        )
