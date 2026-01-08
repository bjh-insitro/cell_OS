"""
Automation Readiness per Feala's Closed-Loop Manifesto.

"Automate as soon as you can, but no sooner."

Track which processes are mature enough for automation:
1. Measure process consistency and reliability
2. Track failure modes and edge cases encountered
3. Score automation readiness per process
4. Recommend what to automate vs what needs more iteration

Design principle: Automation is a standardization tool, not just labor-saving.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
from datetime import datetime
from enum import Enum


class AutomationLevel(str, Enum):
    """Levels of automation readiness."""
    MANUAL = "manual"           # Requires human judgment every time
    ASSISTED = "assisted"       # Human-in-the-loop with suggestions
    SUPERVISED = "supervised"   # Automated with human oversight
    AUTONOMOUS = "autonomous"   # Fully automated, human notified of exceptions


@dataclass
class ProcessExecution:
    """Record of a process execution."""
    timestamp: str
    success: bool
    duration_sec: float
    manual_intervention: bool
    error_type: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class ProcessMetrics:
    """Aggregated metrics for a process."""
    total_executions: int = 0
    successful_executions: int = 0
    manual_interventions: int = 0
    total_duration_sec: float = 0.0

    # Failure tracking
    failure_modes: Dict[str, int] = field(default_factory=dict)
    edge_cases_encountered: Set[str] = field(default_factory=set)

    # Consistency
    duration_variance: float = 0.0
    last_failure_timestamp: Optional[str] = None

    @property
    def success_rate(self) -> float:
        if self.total_executions == 0:
            return 0.0
        return self.successful_executions / self.total_executions

    @property
    def automation_rate(self) -> float:
        """Fraction of executions without manual intervention."""
        if self.total_executions == 0:
            return 0.0
        return 1.0 - (self.manual_interventions / self.total_executions)

    @property
    def mean_duration(self) -> float:
        if self.total_executions == 0:
            return 0.0
        return self.total_duration_sec / self.total_executions


@dataclass
class AutomationReadinessScore:
    """
    Score indicating how ready a process is for automation.

    Components:
    - reliability: Consistent success rate
    - predictability: Low variance in execution
    - coverage: Known failure modes are handled
    - maturity: Sufficient executions to trust
    """
    process_name: str
    reliability_score: float      # 0-1, based on success rate
    predictability_score: float   # 0-1, based on duration variance
    coverage_score: float         # 0-1, based on failure mode handling
    maturity_score: float         # 0-1, based on execution count

    @property
    def overall_score(self) -> float:
        """Weighted overall readiness score."""
        return (
            0.4 * self.reliability_score +
            0.2 * self.predictability_score +
            0.2 * self.coverage_score +
            0.2 * self.maturity_score
        )

    @property
    def recommended_level(self) -> AutomationLevel:
        """Recommend automation level based on score."""
        score = self.overall_score
        if score >= 0.9:
            return AutomationLevel.AUTONOMOUS
        elif score >= 0.75:
            return AutomationLevel.SUPERVISED
        elif score >= 0.5:
            return AutomationLevel.ASSISTED
        else:
            return AutomationLevel.MANUAL

    def gaps(self) -> List[str]:
        """Identify gaps preventing higher automation."""
        gaps = []
        if self.reliability_score < 0.9:
            gaps.append(f"Reliability: {self.reliability_score:.0%} (need 90%)")
        if self.predictability_score < 0.8:
            gaps.append(f"Predictability: {self.predictability_score:.0%} (need 80%)")
        if self.coverage_score < 0.7:
            gaps.append(f"Coverage: {self.coverage_score:.0%} (need 70%)")
        if self.maturity_score < 0.5:
            gaps.append(f"Maturity: {self.maturity_score:.0%} (need 50%)")
        return gaps


class AutomationReadinessTracker:
    """
    Track automation readiness across processes.

    Implements Feala's "automate at the right time" principle.
    """

    # Minimum executions for maturity score
    MIN_EXECUTIONS_FOR_MATURITY = 50

    def __init__(self):
        self.processes: Dict[str, ProcessMetrics] = {}
        self.executions: Dict[str, List[ProcessExecution]] = {}

    def record_execution(
        self,
        process_name: str,
        success: bool,
        duration_sec: float,
        manual_intervention: bool = False,
        error_type: Optional[str] = None,
        notes: Optional[str] = None
    ):
        """Record a process execution."""
        # Initialize if needed
        if process_name not in self.processes:
            self.processes[process_name] = ProcessMetrics()
            self.executions[process_name] = []

        # Create execution record
        execution = ProcessExecution(
            timestamp=datetime.now().isoformat(),
            success=success,
            duration_sec=duration_sec,
            manual_intervention=manual_intervention,
            error_type=error_type,
            notes=notes
        )
        self.executions[process_name].append(execution)

        # Update metrics
        metrics = self.processes[process_name]
        metrics.total_executions += 1
        metrics.total_duration_sec += duration_sec

        if success:
            metrics.successful_executions += 1
        else:
            metrics.last_failure_timestamp = execution.timestamp
            if error_type:
                metrics.failure_modes[error_type] = \
                    metrics.failure_modes.get(error_type, 0) + 1

        if manual_intervention:
            metrics.manual_interventions += 1

        # Update duration variance (online algorithm)
        self._update_variance(process_name, duration_sec)

    def _update_variance(self, process_name: str, new_duration: float):
        """Update duration variance using Welford's algorithm."""
        executions = self.executions[process_name]
        n = len(executions)

        if n < 2:
            return

        durations = [e.duration_sec for e in executions]
        mean = sum(durations) / n
        variance = sum((d - mean) ** 2 for d in durations) / (n - 1)

        self.processes[process_name].duration_variance = variance

    def get_readiness_score(self, process_name: str) -> AutomationReadinessScore:
        """Compute automation readiness score for a process."""
        if process_name not in self.processes:
            return AutomationReadinessScore(
                process_name=process_name,
                reliability_score=0.0,
                predictability_score=0.0,
                coverage_score=0.0,
                maturity_score=0.0
            )

        metrics = self.processes[process_name]

        # Reliability: success rate
        reliability = metrics.success_rate

        # Predictability: inverse of coefficient of variation
        if metrics.mean_duration > 0 and metrics.duration_variance > 0:
            cv = (metrics.duration_variance ** 0.5) / metrics.mean_duration
            predictability = max(0, 1 - cv)  # Lower CV = more predictable
        else:
            predictability = 1.0 if metrics.total_executions > 0 else 0.0

        # Coverage: ratio of handled failure modes
        # Assume each unique failure mode should be handled
        n_failure_modes = len(metrics.failure_modes)
        if n_failure_modes == 0:
            coverage = 1.0 if metrics.success_rate > 0.95 else 0.5
        else:
            # More failure modes seen = better coverage (we know what can go wrong)
            coverage = min(1.0, n_failure_modes / 5)  # Cap at 5 known modes

        # Maturity: based on execution count
        maturity = min(1.0, metrics.total_executions / self.MIN_EXECUTIONS_FOR_MATURITY)

        return AutomationReadinessScore(
            process_name=process_name,
            reliability_score=reliability,
            predictability_score=predictability,
            coverage_score=coverage,
            maturity_score=maturity
        )

    def get_all_scores(self) -> Dict[str, AutomationReadinessScore]:
        """Get readiness scores for all tracked processes."""
        return {
            name: self.get_readiness_score(name)
            for name in self.processes
        }

    def recommend_automation_priorities(self) -> List[Dict]:
        """
        Recommend which processes to automate next.

        Returns list sorted by automation opportunity (high score but not yet autonomous).
        """
        recommendations = []

        for name, score in self.get_all_scores().items():
            if score.recommended_level != AutomationLevel.AUTONOMOUS:
                recommendations.append({
                    'process': name,
                    'current_level': score.recommended_level.value,
                    'overall_score': score.overall_score,
                    'gaps': score.gaps(),
                    'priority': score.overall_score * (1 - len(score.gaps()) / 4)
                })

        # Sort by priority (highest first)
        recommendations.sort(key=lambda x: -x['priority'])
        return recommendations

    def summary(self) -> Dict:
        """Get summary of automation readiness across all processes."""
        scores = self.get_all_scores()

        by_level = {level.value: 0 for level in AutomationLevel}
        for score in scores.values():
            by_level[score.recommended_level.value] += 1

        return {
            'total_processes': len(self.processes),
            'by_automation_level': by_level,
            'mean_readiness': sum(s.overall_score for s in scores.values()) / len(scores) if scores else 0,
            'ready_for_automation': sum(1 for s in scores.values() if s.overall_score >= 0.75),
        }
