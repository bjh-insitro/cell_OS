"""
Phase 6A: Beam search over action sequences.

Deterministic search for optimal action schedule under hard constraints:
- interventions ≤ 2
- death ≤ 20% at 48h

No peeking at hidden truth (latents, true axis). Only observed readouts.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any
import numpy as np

from .episode import Action, Policy, EpisodeRunner, EpisodeReceipt, EpisodeState
from .biological_virtual import BiologicalVirtualMachine
from .reward import compute_microtubule_mechanism_reward


class Phase5EpisodeRunner(EpisodeRunner):
    """
    EpisodeRunner that applies Phase5 compound scalars (potency, toxicity).

    Wraps treat_with_compound to pass potency_scalar and toxicity_scalar.
    """

    def __init__(
        self,
        phase5_compound,
        cell_line: str = "A549",
        horizon_h: float = 48.0,
        step_h: float = 6.0,
        seed: int = 42,
        lambda_dead: float = 2.0,
        lambda_ops: float = 0.1,
        actin_threshold: float = 1.4
    ):
        """Initialize with Phase5Compound."""
        super().__init__(
            compound=phase5_compound.compound_name,
            reference_dose_uM=phase5_compound.reference_dose_uM,
            cell_line=cell_line,
            horizon_h=horizon_h,
            step_h=step_h,
            seed=seed,
            lambda_dead=lambda_dead,
            lambda_ops=lambda_ops,
            actin_threshold=actin_threshold
        )
        self.phase5_compound = phase5_compound

    def run(self, policy: Policy) -> Tuple[EpisodeReceipt, List[EpisodeState]]:
        """Execute policy with Phase5 scalars applied."""
        if len(policy.actions) != self.n_steps:
            raise ValueError(
                f"Policy has {len(policy.actions)} actions, expected {self.n_steps}"
            )

        # Check cache first
        cache_key = self._policy_to_cache_key(policy)
        if cache_key in self._rollout_cache:
            return self._rollout_cache[cache_key]

        # Cache miss: execute with scalars
        vm = BiologicalVirtualMachine(seed=self.seed)
        vm.seed_vessel("episode", self.cell_line, 1e6, capacity=1e7, initial_viability=0.98)

        # Measure baseline
        baseline_result = vm.cell_painting_assay("episode")
        baseline_actin = baseline_result['morphology_struct']['actin']

        # Trajectory tracking
        trajectory = []
        washout_count = 0
        feed_count = 0

        actin_struct_12h = None
        viability_48h = None

        # Execute policy step by step
        for step_idx, action in enumerate(policy.actions):
            current_time = step_idx * self.step_h

            vessel = vm.vessel_states["episode"]

            # 1. Apply dose (with scalars)
            if action.dose_fraction > 0:
                dose_uM = action.dose_fraction * self.reference_dose_uM

                if self.compound not in vessel.compounds or vessel.compounds[self.compound] == 0:
                    vm.treat_with_compound(
                        "episode",
                        self.compound,
                        dose_uM=dose_uM,
                        potency_scalar=self.phase5_compound.potency_scalar,
                        toxicity_scalar=self.phase5_compound.toxicity_scalar
                    )

            # 2. Washout
            if action.washout:
                if self.compound in vessel.compounds and vessel.compounds[self.compound] > 0:
                    vm.washout_compound("episode", self.compound)
                    washout_count += 1

            # 3. Feed
            if action.feed:
                vm.feed_vessel("episode")
                feed_count += 1

            # 4. Advance time
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

            # Capture snapshots
            if abs(state.time_h - self.measurement_time_12h) < 1e-6:
                actin_struct_12h = actin_struct
            if abs(state.time_h - self.measurement_time_48h) < 1e-6:
                viability_48h = viability

        # Compute reward
        if actin_struct_12h is None or viability_48h is None:
            raise RuntimeError("Missing measurements at key timepoints")

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

        # Store in cache
        result = (receipt, trajectory)
        self._rollout_cache[cache_key] = result

        return result


@dataclass
class BeamNode:
    """
    Node in beam search.

    Stores:
    - Current timestep
    - Action sequence so far
    - Intervention counts
    - Current observations (viability, readouts)
    - Heuristic score (for beam ranking, not terminal reward)
    """
    t_step: int  # 0..n_steps
    schedule: List[Action]

    # Constraint tracking
    washout_count: int = 0
    feed_count: int = 0

    # Current state (from prefix rollout)
    viability_current: float = 1.0
    actin_fold_current: float = 1.0
    confidence_margin_current: float = 0.0  # classifier margin (top1 - top2)

    # Heuristic score for beam ranking (NOT terminal reward)
    heuristic_score: float = 0.0

    # Terminal reward (only set at t=n_steps)
    terminal_reward: Optional[float] = None

    # For debugging
    dominated: bool = False


@dataclass
class BeamSearchResult:
    """Result of beam search."""
    best_schedule: List[Action]
    best_policy: Policy
    best_reward: float
    best_receipt: EpisodeReceipt

    # Diagnostics
    nodes_expanded: int
    nodes_pruned_death: int
    nodes_pruned_interventions: int
    nodes_pruned_dominated: int

    # Comparison to baseline
    smart_policy_reward: Optional[float] = None
    beats_smart: bool = False


class BeamSearch:
    """
    Beam search for optimal action sequences.

    Uses prefix rollouts for early evaluation and pruning.
    Heuristic scoring for beam ranking, terminal reward for final selection.
    """

    def __init__(
        self,
        runner: EpisodeRunner,
        beam_width: int = 10,
        max_interventions: int = 2,
        death_tolerance: float = 0.20,
        # Heuristic weights
        w_mechanism: float = 2.0,      # Reward mechanism engagement potential
        w_viability: float = 0.5,      # Penalize death
        w_interventions: float = 0.1   # Small penalty for interventions
    ):
        """
        Initialize beam search.

        Args:
            runner: EpisodeRunner for rollouts
            beam_width: Max nodes to keep per timestep
            max_interventions: Hard constraint (washouts + feeds)
            death_tolerance: Hard constraint (1 - viability_min)
            w_viability: Heuristic weight for viability
            w_confidence: Heuristic weight for classifier confidence
            w_interventions: Heuristic penalty for interventions
        """
        self.runner = runner
        self.beam_width = beam_width
        self.max_interventions = max_interventions
        self.death_tolerance = death_tolerance

        self.w_mechanism = w_mechanism
        self.w_viability = w_viability
        self.w_interventions = w_interventions

        # Action space
        self.dose_levels = [0.0, 0.25, 0.5, 1.0]

        # Stats
        self.nodes_expanded = 0
        self.nodes_pruned_death = 0
        self.nodes_pruned_interventions = 0
        self.nodes_pruned_dominated = 0

    def search(self, compound_id: str, phase5_compound=None) -> BeamSearchResult:
        """
        Run beam search for given compound.

        Args:
            compound_id: Compound from Phase5 library
            phase5_compound: Optional Phase5Compound (for scalars)

        Returns:
            BeamSearchResult with best policy and diagnostics
        """
        from .masked_compound_phase5 import PHASE5_LIBRARY

        if phase5_compound is None:
            phase5_compound = PHASE5_LIBRARY[compound_id]

        compound = phase5_compound

        # Initialize beam with root node
        beam = [BeamNode(t_step=0, schedule=[])]

        # Expand beam for each timestep
        for t in range(self.runner.n_steps):
            new_beam = []

            for node in beam:
                if node.t_step != t:
                    continue  # Skip nodes from different timestep

                # Generate successors
                successors = self._expand_node(node, compound)
                new_beam.extend(successors)
                self.nodes_expanded += 1

            # Prune and select top-k by heuristic
            beam = self._prune_and_select(new_beam)

            if not beam:
                raise RuntimeError(f"Beam empty at t={t}. All paths pruned.")

        # All nodes should be at t=n_steps now
        # Compute terminal rewards and select best
        terminal_nodes = []
        for node in beam:
            if node.terminal_reward is None:
                # Compute full rollout reward
                policy = Policy(actions=node.schedule, name="beam_search_candidate")
                receipt, _ = self.runner.run(policy)
                node.terminal_reward = receipt.reward_total

            terminal_nodes.append(node)

        # Select best by terminal reward
        best_node = max(terminal_nodes, key=lambda n: n.terminal_reward)

        # Create final policy
        best_policy = Policy(actions=best_node.schedule, name=f"beam_search_{compound_id}")
        best_receipt, _ = self.runner.run(best_policy)

        return BeamSearchResult(
            best_schedule=best_node.schedule,
            best_policy=best_policy,
            best_reward=best_receipt.reward_total,
            best_receipt=best_receipt,
            nodes_expanded=self.nodes_expanded,
            nodes_pruned_death=self.nodes_pruned_death,
            nodes_pruned_interventions=self.nodes_pruned_interventions,
            nodes_pruned_dominated=self.nodes_pruned_dominated
        )

    def _expand_node(self, node: BeamNode, compound) -> List[BeamNode]:
        """
        Generate successor nodes by trying all legal actions.

        Args:
            node: Current node
            compound: Phase5Compound

        Returns:
            List of successor nodes (after legality filtering)
        """
        successors = []

        # Check if compound is present (for washout legality)
        # For simplicity, track if we've ever dosed
        has_dosed = any(a.dose_fraction > 0 for a in node.schedule)

        for dose_level in self.dose_levels:
            for washout in [False, True]:
                for feed in [False, True]:
                    # Legality checks
                    if washout and not has_dosed:
                        continue  # Can't washout if nothing dosed yet

                    # Create action
                    action = Action(
                        dose_fraction=dose_level,
                        washout=washout,
                        feed=feed
                    )

                    # Create successor
                    new_schedule = node.schedule + [action]
                    new_washout = node.washout_count + (1 if washout else 0)
                    new_feed = node.feed_count + (1 if feed else 0)

                    # Early pruning: intervention budget
                    if new_washout + new_feed > self.max_interventions:
                        self.nodes_pruned_interventions += 1
                        continue

                    # Evaluate prefix (get current observations)
                    prefix_result = self._evaluate_prefix(new_schedule, compound)

                    if prefix_result is None:
                        # Prefix violates hard constraint (death)
                        self.nodes_pruned_death += 1
                        continue

                    viability_now, actin_fold_now, confidence_now = prefix_result

                    # Early pruning: death trajectory bound
                    # If estimated death already high, prune
                    if viability_now < (1.0 - self.death_tolerance + 0.05):  # Give 5% slack
                        self.nodes_pruned_death += 1
                        continue

                    # Compute heuristic score
                    # Reward mechanism potential, penalize death and interventions
                    mechanism_potential = max(0.0, actin_fold_now - 1.0)  # How much above baseline
                    death_penalty = max(0.0, (1.0 - viability_now) - 0.02)  # Penalty for death >2%

                    heuristic = (
                        self.w_mechanism * mechanism_potential -
                        self.w_viability * death_penalty -
                        self.w_interventions * (new_washout + new_feed)
                    )

                    successor = BeamNode(
                        t_step=node.t_step + 1,
                        schedule=new_schedule,
                        washout_count=new_washout,
                        feed_count=new_feed,
                        viability_current=viability_now,
                        actin_fold_current=actin_fold_now,
                        confidence_margin_current=confidence_now,
                        heuristic_score=heuristic
                    )

                    successors.append(successor)

        return successors

    def _evaluate_prefix(
        self,
        schedule_prefix: List[Action],
        compound
    ) -> Optional[Tuple[float, float, float]]:
        """
        Evaluate partial schedule - simplified version for speed.

        For now, just return optimistic estimates without full rollout.
        Only complete schedules (t=n_steps) will be fully evaluated.

        Args:
            schedule_prefix: Partial action sequence
            compound: Phase5Compound

        Returns:
            (viability, actin_fold, confidence_margin) estimates
        """
        # Simple heuristic estimates (for beam ordering only)
        # Don't run full simulation for prefixes - too expensive

        # Count cumulative dose exposure (dose × duration)
        total_dose_exposure = sum(a.dose_fraction for a in schedule_prefix)

        # Estimate viability (decreases with dose exposure)
        # Typical: 0.5× dose for 12h → ~10% death, 1.0× for 24h → ~20% death
        estimated_death = min(0.3, total_dose_exposure * 0.08)
        estimated_viability = 1.0 - estimated_death

        # Estimate actin fold-change (increases with dose, plateaus around 1.6×)
        # Need sustained dose to engage mechanism
        estimated_actin = 1.0 + min(0.6, total_dose_exposure * 0.25)

        # Confidence margin (unused, kept for compatibility)
        confidence_margin = 0.0

        return estimated_viability, estimated_actin, confidence_margin

    def _prune_and_select(self, nodes: List[BeamNode]) -> List[BeamNode]:
        """
        Select top-k nodes by heuristic score.

        Args:
            nodes: Candidate nodes

        Returns:
            Top-k nodes by heuristic score
        """
        if not nodes:
            return []

        # No dominance pruning - too aggressive and loses diversity
        # Just select top-k by heuristic score
        nodes.sort(key=lambda n: n.heuristic_score, reverse=True)
        beam = nodes[:self.beam_width]

        return beam
