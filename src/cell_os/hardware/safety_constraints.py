"""
Safety as a First-Class Constraint per Feala's Closed-Loop Manifesto.

"Safety as a first-class constraint - Encoding safety directly into
optimization algorithms rather than post-hoc screening"

This module implements:
1. Hard constraints (never violate)
2. Soft constraints (penalize in objective)
3. Safety-adjusted reward functions
4. Pareto-aware optimization support

Design principle: Safety should be integrated into the optimization
objective, not just a threshold filter applied afterward.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any
from enum import Enum
import math


class SafetyLevel(str, Enum):
    """Safety violation severity levels."""
    NONE = "none"           # No violation
    WARNING = "warning"     # Approaching limit
    SOFT = "soft"           # Soft constraint violated (penalized)
    HARD = "hard"           # Hard constraint violated (infeasible)


@dataclass
class SafetyViolation:
    """Record of a safety constraint violation."""
    constraint_name: str
    level: SafetyLevel
    observed_value: float
    threshold_value: float
    penalty_applied: float
    description: str

    def is_blocking(self) -> bool:
        """Check if this violation blocks the action."""
        return self.level == SafetyLevel.HARD


@dataclass
class SafetyConstraints:
    """
    First-class safety constraints per Feala's manifesto.

    Integrates safety into the optimization objective rather than
    treating it as a post-hoc filter.

    Constraint types:
    - Hard: Action is infeasible if violated (returns -inf reward)
    - Soft: Action is penalized proportionally to violation
    - Warning: No penalty, but logged for monitoring
    """
    # Hard constraints (never violate)
    max_death_fraction: float = 0.35          # Maximum acceptable death
    min_viability: float = 0.65               # Minimum viable population
    max_consecutive_interventions: int = 3    # Prevent intervention spam

    # Soft constraint thresholds
    death_warning_threshold: float = 0.20     # Start warning above this
    viability_warning_threshold: float = 0.80 # Start warning below this

    # Penalty weights for soft constraints
    death_penalty_weight: float = 10.0        # High penalty for death
    intervention_penalty_weight: float = 0.5  # Small penalty per intervention
    stress_accumulation_penalty: float = 2.0  # Penalty for high stress

    # Safety margin (buffer before hitting hard limits)
    safety_margin_fraction: float = 0.10      # 10% buffer

    def check_hard_constraints(
        self,
        death_fraction: float,
        viability: float,
        intervention_count: int = 0
    ) -> List[SafetyViolation]:
        """
        Check hard constraints. Any violation makes the action infeasible.

        Returns list of violations (empty if all constraints satisfied).
        """
        violations = []

        if death_fraction > self.max_death_fraction:
            violations.append(SafetyViolation(
                constraint_name="max_death_fraction",
                level=SafetyLevel.HARD,
                observed_value=death_fraction,
                threshold_value=self.max_death_fraction,
                penalty_applied=float('inf'),
                description=f"Death {death_fraction:.1%} exceeds max {self.max_death_fraction:.1%}"
            ))

        if viability < self.min_viability:
            violations.append(SafetyViolation(
                constraint_name="min_viability",
                level=SafetyLevel.HARD,
                observed_value=viability,
                threshold_value=self.min_viability,
                penalty_applied=float('inf'),
                description=f"Viability {viability:.1%} below min {self.min_viability:.1%}"
            ))

        if intervention_count > self.max_consecutive_interventions:
            violations.append(SafetyViolation(
                constraint_name="max_consecutive_interventions",
                level=SafetyLevel.HARD,
                observed_value=intervention_count,
                threshold_value=self.max_consecutive_interventions,
                penalty_applied=float('inf'),
                description=f"Interventions {intervention_count} exceed max {self.max_consecutive_interventions}"
            ))

        return violations

    def compute_soft_penalty(
        self,
        death_fraction: float,
        viability: float,
        intervention_count: int = 0,
        accumulated_stress: float = 0.0
    ) -> Tuple[float, List[SafetyViolation]]:
        """
        Compute soft constraint penalty.

        Returns (total_penalty, list of violations).
        Penalty is continuous and differentiable for gradient-based optimization.
        """
        total_penalty = 0.0
        violations = []

        # Death penalty (continuous, increases as death approaches limit)
        if death_fraction > self.death_warning_threshold:
            # Quadratic penalty: gets steeper as we approach the limit
            margin_used = (death_fraction - self.death_warning_threshold) / \
                          (self.max_death_fraction - self.death_warning_threshold)
            margin_used = min(margin_used, 1.0)  # Cap at 1.0

            penalty = self.death_penalty_weight * (margin_used ** 2)
            total_penalty += penalty

            level = SafetyLevel.SOFT if death_fraction < self.max_death_fraction else SafetyLevel.WARNING
            violations.append(SafetyViolation(
                constraint_name="death_soft_penalty",
                level=level,
                observed_value=death_fraction,
                threshold_value=self.death_warning_threshold,
                penalty_applied=penalty,
                description=f"Death {death_fraction:.1%} > warning threshold {self.death_warning_threshold:.1%}"
            ))

        # Viability penalty (continuous, increases as viability drops)
        if viability < self.viability_warning_threshold:
            margin_used = (self.viability_warning_threshold - viability) / \
                          (self.viability_warning_threshold - self.min_viability)
            margin_used = min(margin_used, 1.0)

            penalty = self.death_penalty_weight * (margin_used ** 2)
            total_penalty += penalty

            violations.append(SafetyViolation(
                constraint_name="viability_soft_penalty",
                level=SafetyLevel.SOFT,
                observed_value=viability,
                threshold_value=self.viability_warning_threshold,
                penalty_applied=penalty,
                description=f"Viability {viability:.1%} < warning threshold {self.viability_warning_threshold:.1%}"
            ))

        # Intervention penalty (linear, discourages excessive interventions)
        if intervention_count > 0:
            penalty = self.intervention_penalty_weight * intervention_count
            total_penalty += penalty
            violations.append(SafetyViolation(
                constraint_name="intervention_penalty",
                level=SafetyLevel.WARNING,
                observed_value=intervention_count,
                threshold_value=0,
                penalty_applied=penalty,
                description=f"{intervention_count} interventions applied"
            ))

        # Stress accumulation penalty (prevents chronic high stress)
        if accumulated_stress > 0.5:
            penalty = self.stress_accumulation_penalty * (accumulated_stress - 0.5)
            total_penalty += penalty
            violations.append(SafetyViolation(
                constraint_name="stress_accumulation_penalty",
                level=SafetyLevel.WARNING,
                observed_value=accumulated_stress,
                threshold_value=0.5,
                penalty_applied=penalty,
                description=f"Accumulated stress {accumulated_stress:.2f} > 0.5"
            ))

        return total_penalty, violations

    def safety_adjusted_reward(
        self,
        base_reward: float,
        death_fraction: float,
        viability: float,
        intervention_count: int = 0,
        accumulated_stress: float = 0.0
    ) -> Tuple[float, List[SafetyViolation]]:
        """
        Compute safety-adjusted reward.

        Integrates safety directly into the objective function:
        - Hard constraint violation → -inf (infeasible)
        - Soft constraint violation → continuous penalty

        Returns (adjusted_reward, all_violations).
        """
        all_violations = []

        # Check hard constraints first
        hard_violations = self.check_hard_constraints(
            death_fraction, viability, intervention_count
        )
        all_violations.extend(hard_violations)

        # If any hard constraint violated, return -inf
        if any(v.is_blocking() for v in hard_violations):
            return float('-inf'), all_violations

        # Compute soft penalty
        soft_penalty, soft_violations = self.compute_soft_penalty(
            death_fraction, viability, intervention_count, accumulated_stress
        )
        all_violations.extend(soft_violations)

        # Adjusted reward = base - penalty
        adjusted_reward = base_reward - soft_penalty

        return adjusted_reward, all_violations

    def is_feasible(
        self,
        death_fraction: float,
        viability: float,
        intervention_count: int = 0
    ) -> bool:
        """Quick check if action is feasible (no hard constraint violations)."""
        return len(self.check_hard_constraints(
            death_fraction, viability, intervention_count
        )) == 0

    def safety_margin(self, death_fraction: float) -> float:
        """
        Compute remaining safety margin before hitting hard limit.

        Returns value in [0, 1] where 1 = full margin, 0 = at limit.
        """
        if death_fraction >= self.max_death_fraction:
            return 0.0
        return 1.0 - (death_fraction / self.max_death_fraction)


@dataclass
class ParetoSafetyObjective:
    """
    Multi-objective optimization with safety as a Pareto dimension.

    Instead of just optimizing reward subject to safety constraints,
    treat safety and reward as separate objectives to optimize together.
    """
    safety_constraints: SafetyConstraints = field(default_factory=SafetyConstraints)

    def evaluate(
        self,
        reward: float,
        death_fraction: float,
        viability: float,
        intervention_count: int = 0
    ) -> Dict[str, float]:
        """
        Evaluate action on multiple objectives.

        Returns dict of objective values (all to be maximized).
        """
        return {
            'reward': reward,
            'safety_margin': self.safety_constraints.safety_margin(death_fraction),
            'viability': viability,
            'efficiency': 1.0 / (1.0 + intervention_count),  # Fewer interventions = better
        }

    def dominates(self, a: Dict[str, float], b: Dict[str, float]) -> bool:
        """
        Check if solution a Pareto-dominates solution b.

        a dominates b if a is at least as good on all objectives
        and strictly better on at least one.
        """
        at_least_as_good = all(a[k] >= b[k] for k in a)
        strictly_better = any(a[k] > b[k] for k in a)
        return at_least_as_good and strictly_better

    def pareto_filter(
        self,
        solutions: List[Tuple[Any, Dict[str, float]]]
    ) -> List[Tuple[Any, Dict[str, float]]]:
        """
        Filter solutions to keep only Pareto-optimal ones.

        Args:
            solutions: List of (action, objectives_dict) tuples

        Returns:
            List of non-dominated solutions
        """
        if not solutions:
            return []

        pareto_front = []
        for sol in solutions:
            _, obj = sol
            is_dominated = False

            # Check if this solution is dominated by any in current front
            for _, front_obj in pareto_front:
                if self.dominates(front_obj, obj):
                    is_dominated = True
                    break

            if not is_dominated:
                # Remove any solutions in front that this one dominates
                pareto_front = [
                    (s, o) for s, o in pareto_front
                    if not self.dominates(obj, o)
                ]
                pareto_front.append(sol)

        return pareto_front

    def scalarize(
        self,
        objectives: Dict[str, float],
        weights: Dict[str, float] = None
    ) -> float:
        """
        Convert multi-objective to scalar for ranking.

        Default weights emphasize safety over pure reward.
        """
        if weights is None:
            weights = {
                'reward': 1.0,
                'safety_margin': 2.0,  # Safety is 2x as important as reward
                'viability': 1.5,
                'efficiency': 0.5,
            }

        return sum(
            weights.get(k, 1.0) * v
            for k, v in objectives.items()
        )
