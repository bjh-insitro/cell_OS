"""
Phase 4: Episode loop for continuous control (decision problem with landscape).

This turns the sandbox from "two hardcoded policies" to "decision problem with action space."

Action space (discrete, 6h steps):
- Dose: {0, 0.25×, 0.5×, 1.0×} where 1× = reference dose (e.g., 0.005 µM paclitaxel)
- Washout: {yes, no}
- Feed: {yes, no}

Horizon: 48h = 8 steps (0h, 6h, 12h, 18h, 24h, 30h, 36h, 42h)
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Tuple
import numpy as np

from .biological_virtual import BiologicalVirtualMachine
from .reward import compute_microtubule_mechanism_reward, EpisodeReceipt


@dataclass
class Action:
    """Single action at a timestep."""
    dose_fraction: float  # 0, 0.25, 0.5, 1.0 (fraction of reference dose)
    washout: bool
    feed: bool

    def __str__(self):
        parts = []
        if self.dose_fraction > 0:
            parts.append(f"dose={self.dose_fraction:.2f}×")
        if self.washout:
            parts.append("washout")
        if self.feed:
            parts.append("feed")
        return f"Action({', '.join(parts) if parts else 'noop'})"


@dataclass
class Policy:
    """
    Sequence of actions over episode horizon.

    Actions are indexed by step (0-7 for 48h at 6h steps).
    """
    actions: List[Action]
    name: str = ""

    def __str__(self):
        if self.name:
            return f"Policy({self.name})"
        return f"Policy({len(self.actions)} steps)"

    def __repr__(self):
        return self.__str__()


@dataclass
class EpisodeState:
    """State at a specific timestep."""
    time_h: float
    actin_struct: float
    baseline_actin: float
    transport_dysfunction: float
    viability: float
    washout_count: int
    feed_count: int


class EpisodeRunner:
    """
    Execute policy and collect trajectory for evaluation.

    Usage:
        runner = EpisodeRunner(
            compound="paclitaxel",
            reference_dose_uM=0.005,
            cell_line="A549",
            horizon_h=48.0,
            step_h=6.0,
            seed=42
        )

        policy = Policy(actions=[...])
        receipt = runner.run(policy)

        # Or enumerate all policies
        pareto_frontier = runner.enumerate_policies(max_washouts=2)
    """

    def __init__(
        self,
        compound: str,
        reference_dose_uM: float,
        cell_line: str = "A549",
        horizon_h: float = 48.0,
        step_h: float = 6.0,
        seed: int = 42,
        lambda_dead: float = 2.0,
        lambda_ops: float = 0.1,
        actin_threshold: float = 1.4
    ):
        """
        Initialize episode runner.

        Args:
            compound: Compound name (e.g., "paclitaxel")
            reference_dose_uM: Reference dose (1.0× fraction)
            cell_line: Cell line for seeding
            horizon_h: Episode duration in hours
            step_h: Time step size in hours
            seed: RNG seed for reproducibility
            lambda_dead: Death penalty coefficient
            lambda_ops: Ops cost coefficient
            actin_threshold: Mechanism hit threshold
        """
        self.compound = compound
        self.reference_dose_uM = reference_dose_uM
        self.cell_line = cell_line
        self.horizon_h = horizon_h
        self.step_h = step_h
        self.seed = seed
        self.lambda_dead = lambda_dead
        self.lambda_ops = lambda_ops
        self.actin_threshold = actin_threshold

        # Compute number of steps
        self.n_steps = int(horizon_h / step_h)

        # Measurement times
        self.measurement_time_12h = 12.0
        self.measurement_time_48h = 48.0

    def run(self, policy: Policy) -> Tuple[EpisodeReceipt, List[EpisodeState]]:
        """
        Execute policy and return reward receipt + trajectory.

        Args:
            policy: Policy to execute

        Returns:
            (receipt, trajectory) tuple
            - receipt: EpisodeReceipt with reward and diagnostics
            - trajectory: List of EpisodeState snapshots at each step
        """
        if len(policy.actions) != self.n_steps:
            raise ValueError(
                f"Policy has {len(policy.actions)} actions, expected {self.n_steps} "
                f"(horizon={self.horizon_h}h, step={self.step_h}h)"
            )

        # Initialize VM
        vm = BiologicalVirtualMachine(seed=self.seed)
        vm.seed_vessel("episode", self.cell_line, 1e6, capacity=1e7, initial_viability=0.98)

        # Measure baseline
        baseline_result = vm.cell_painting_assay("episode")
        baseline_actin = baseline_result['morphology_struct']['actin']

        # Trajectory tracking
        trajectory = []
        washout_count = 0
        feed_count = 0

        # State snapshots at 12h and 48h
        actin_struct_12h = None
        viability_48h = None

        # Execute policy step by step
        for step_idx, action in enumerate(policy.actions):
            current_time = step_idx * self.step_h

            # Execute action
            vessel = vm.vessel_states["episode"]

            # 1. Apply dose (if non-zero)
            if action.dose_fraction > 0:
                dose_uM = action.dose_fraction * self.reference_dose_uM

                # Check if already dosed (don't re-dose if compound present)
                if self.compound not in vessel.compounds or vessel.compounds[self.compound] == 0:
                    vm.treat_with_compound("episode", self.compound, dose_uM=dose_uM)

            # 2. Washout (if requested)
            if action.washout:
                if self.compound in vessel.compounds and vessel.compounds[self.compound] > 0:
                    vm.washout_compound("episode", self.compound)
                    washout_count += 1

            # 3. Feed (if requested)
            if action.feed:
                vm.feed_vessel("episode")
                feed_count += 1

            # 4. Advance time by one step
            vm.advance_time(self.step_h)

            # 5. Measure state
            result = vm.cell_painting_assay("episode")
            morph_struct = result['morphology_struct']
            actin_struct = morph_struct['actin']
            transport_dysfunction = vessel.transport_dysfunction
            viability = vessel.viability

            # Record trajectory
            state = EpisodeState(
                time_h=current_time + self.step_h,
                actin_struct=actin_struct,
                baseline_actin=baseline_actin,
                transport_dysfunction=transport_dysfunction,
                viability=viability,
                washout_count=washout_count,
                feed_count=feed_count
            )
            trajectory.append(state)

            # Capture snapshots at key timepoints
            if abs(state.time_h - self.measurement_time_12h) < 1e-6:
                actin_struct_12h = actin_struct
            if abs(state.time_h - self.measurement_time_48h) < 1e-6:
                viability_48h = viability

        # Compute reward
        if actin_struct_12h is None or viability_48h is None:
            raise RuntimeError(
                f"Missing measurements: actin_12h={actin_struct_12h}, viability_48h={viability_48h}. "
                f"Check that measurement times ({self.measurement_time_12h}h, {self.measurement_time_48h}h) "
                f"align with step boundaries."
            )

        receipt = compute_microtubule_mechanism_reward(
            actin_struct_12h=actin_struct_12h,
            baseline_actin=baseline_actin,
            viability_48h=viability_48h,
            washout_count=washout_count,
            feed_count=feed_count,
            lambda_dead=self.lambda_dead,
            lambda_ops=self.lambda_ops,
            actin_threshold=self.actin_threshold
        )

        return receipt, trajectory

    def enumerate_policies(
        self,
        max_washouts: int = 2,
        max_feeds: int = 0,
        dose_fractions: Optional[List[float]] = None
    ) -> List[Tuple[Policy, EpisodeReceipt, List[EpisodeState]]]:
        """
        Enumerate all reasonable policies up to max_washouts.

        Heuristics to keep search tractable:
        1. Dose only in first 3 steps (0h, 6h, 12h)
        2. Washout only after dosing
        3. No washout in step 0 (nothing to wash out yet)
        4. At most one washout per episode (unless max_washouts > 1)
        5. No re-dosing after washout (recovery phase)

        Args:
            max_washouts: Maximum washouts per policy (0-2)
            max_feeds: Maximum feeds per policy (default: 0, no feeding)
            dose_fractions: List of dose fractions to try (default: [0.25, 0.5, 1.0])

        Returns:
            List of (policy, receipt, trajectory) tuples, sorted by reward descending
        """
        if dose_fractions is None:
            dose_fractions = [0.25, 0.5, 1.0]

        policies = []

        # Strategy 1: Continuous dosing (no washout)
        for dose_frac in dose_fractions:
            actions = []
            for step in range(self.n_steps):
                # Dose only at step 0, then maintain
                if step == 0:
                    actions.append(Action(dose_fraction=dose_frac, washout=False, feed=False))
                else:
                    actions.append(Action(dose_fraction=0, washout=False, feed=False))

            policy = Policy(actions=actions, name=f"continuous_{dose_frac:.2f}×")
            policies.append(policy)

        # Strategy 2: Pulse dosing (single washout at various times)
        if max_washouts >= 1:
            for dose_frac in dose_fractions:
                # Washout at 12h (step 2)
                for washout_step in [2]:  # 12h
                    actions = []
                    for step in range(self.n_steps):
                        if step == 0:
                            # Initial dose
                            actions.append(Action(dose_fraction=dose_frac, washout=False, feed=False))
                        elif step == washout_step:
                            # Washout
                            actions.append(Action(dose_fraction=0, washout=True, feed=False))
                        else:
                            # Recovery (no dose, no washout)
                            actions.append(Action(dose_fraction=0, washout=False, feed=False))

                    policy = Policy(actions=actions, name=f"pulse_{dose_frac:.2f}×_wash@{washout_step*self.step_h:.0f}h")
                    policies.append(policy)

        # Strategy 3: Double pulse (two washouts)
        if max_washouts >= 2:
            for dose_frac in dose_fractions:
                # Dose at 0h, washout at 12h, re-dose at 18h, washout at 30h
                actions = []
                actions.append(Action(dose_fraction=dose_frac, washout=False, feed=False))  # 0h: dose
                actions.append(Action(dose_fraction=0, washout=False, feed=False))          # 6h: maintain
                actions.append(Action(dose_fraction=0, washout=True, feed=False))           # 12h: washout
                actions.append(Action(dose_fraction=dose_frac, washout=False, feed=False))  # 18h: re-dose
                actions.append(Action(dose_fraction=0, washout=False, feed=False))          # 24h: maintain
                actions.append(Action(dose_fraction=0, washout=True, feed=False))           # 30h: washout
                actions.append(Action(dose_fraction=0, washout=False, feed=False))          # 36h: recovery
                actions.append(Action(dose_fraction=0, washout=False, feed=False))          # 42h: recovery

                policy = Policy(actions=actions, name=f"double_pulse_{dose_frac:.2f}×")
                policies.append(policy)

        # Strategy 4: Control (no treatment)
        actions = [Action(dose_fraction=0, washout=False, feed=False) for _ in range(self.n_steps)]
        policy = Policy(actions=actions, name="control")
        policies.append(policy)

        # Execute all policies and collect results
        results = []
        for policy in policies:
            try:
                receipt, trajectory = self.run(policy)
                results.append((policy, receipt, trajectory))
            except Exception as e:
                print(f"Warning: Policy {policy.name} failed: {e}")
                continue

        # Sort by reward descending
        results.sort(key=lambda x: x[1].reward_total, reverse=True)

        return results
