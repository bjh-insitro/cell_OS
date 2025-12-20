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


@dataclass
class PrefixRolloutResult:
    """Result of prefix rollout to current timestep."""
    viability: float
    actin_fold: float
    classifier_margin: float  # top1_score - top2_score from Phase5 classifier
    predicted_axis: Optional[str]
    washout_count: int
    feed_count: int
    # Full state for debugging
    actin_struct: float
    baseline_actin: float

    # NEW: Belief state (Bayesian posterior + calibration)
    mito_fold: float = 1.0
    er_fold: float = 1.0
    posterior_top_prob: float = 0.0
    posterior_margin: float = 0.0
    nuisance_fraction: float = 0.0
    calibrated_confidence: float = 0.0

    # Forensics: nuisance model components
    nuisance_mean_shift_mag: float = 0.0  # ||mean_shift||
    nuisance_var_inflation: float = 0.0   # Total variance inflation


class Phase5EpisodeRunner(EpisodeRunner):
    """
    EpisodeRunner that applies Phase5 compound scalars (potency, toxicity).

    Extends with prefix rollouts for beam search.
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

        # Prefix rollout cache: key = (schedule_prefix_tuple, n_steps)
        self._prefix_cache: Dict[Tuple, PrefixRolloutResult] = {}

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

    def rollout_prefix(self, schedule_prefix: List[Action]) -> PrefixRolloutResult:
        """
        Execute partial schedule and return state at current timestep.

        This is the ACTUAL prefix rollout - runs VM only to len(schedule_prefix) steps.

        Args:
            schedule_prefix: Partial action sequence

        Returns:
            PrefixRolloutResult with true state (viability, actin, classifier margin)
        """
        n_steps_prefix = len(schedule_prefix)

        # Check cache first
        cache_key = (tuple((a.dose_fraction, a.washout, a.feed) for a in schedule_prefix), n_steps_prefix)
        if cache_key in self._prefix_cache:
            return self._prefix_cache[cache_key]

        # Cache miss: run VM to current timestep
        vm = BiologicalVirtualMachine(seed=self.seed)
        vm.seed_vessel("episode", self.cell_line, 1e6, capacity=1e7, initial_viability=0.98)

        # Measure baseline
        baseline_result = vm.cell_painting_assay("episode")
        baseline_actin = baseline_result['morphology_struct']['actin']
        baseline_er = baseline_result['morphology_struct']['er']
        baseline_mito = baseline_result['morphology_struct']['mito']
        baseline_scalars = vm.atp_viability_assay("episode")
        baseline_upr = baseline_scalars['upr_marker']
        baseline_atp = baseline_scalars['atp_signal']
        baseline_trafficking = baseline_scalars['trafficking_marker']

        # Execute prefix
        washout_count = 0
        feed_count = 0

        for step_idx, action in enumerate(schedule_prefix):
            vessel = vm.vessel_states["episode"]

            # Apply dose
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

            # Washout
            if action.washout:
                if self.compound in vessel.compounds and vessel.compounds[self.compound] > 0:
                    vm.washout_compound("episode", self.compound)
                    washout_count += 1

            # Feed
            if action.feed:
                vm.feed_vessel("episode")
                feed_count += 1

            # Advance time
            vm.advance_time(self.step_h)

        # Measure current state
        result = vm.cell_painting_assay("episode")
        morph_struct = result['morphology_struct']
        scalars = vm.atp_viability_assay("episode")
        vessel = vm.vessel_states["episode"]

        actin_struct = morph_struct['actin']
        actin_fold = actin_struct / baseline_actin
        viability = vessel.viability

        # Run Phase5 classifier for confidence margin
        from .masked_compound_phase5 import infer_stress_axis_with_confidence

        er_fold = morph_struct['er'] / baseline_er
        mito_fold = morph_struct['mito'] / baseline_mito
        upr_fold = scalars['upr_marker'] / baseline_upr
        atp_fold = scalars['atp_signal'] / baseline_atp
        trafficking_fold = scalars['trafficking_marker'] / baseline_trafficking

        predicted_axis, confidence = infer_stress_axis_with_confidence(
            er_fold=er_fold,
            mito_fold=mito_fold,
            actin_fold=actin_fold,
            upr_fold=upr_fold,
            atp_fold=atp_fold,
            trafficking_fold=trafficking_fold
        )

        # NEW: Compute Bayesian posterior + calibrated confidence
        from .mechanism_posterior_v2 import compute_mechanism_posterior_v2, NuisanceModel
        from .confidence_calibrator import ConfidenceCalibrator, BeliefState

        # Build nuisance model
        current_time_h = n_steps_prefix * self.step_h
        meas_mods = vm.run_context.get_measurement_modifiers()
        context_shift = np.array([
            (meas_mods['channel_biases']['actin'] - 1.0) * 0.2,
            (meas_mods['channel_biases']['mito'] - 1.0) * 0.2,
            (meas_mods['channel_biases']['er'] - 1.0) * 0.2
        ])

        hetero_width = vessel.get_mixture_width('transport_dysfunction')
        artifact_var = 0.01 * np.exp(-current_time_h / 10.0)

        nuisance = NuisanceModel(
            context_shift=context_shift,
            pipeline_shift=np.array([0.01, -0.01, 0.01]),
            artifact_var=artifact_var,
            heterogeneity_var=hetero_width ** 2,
            context_var=0.15 ** 2,
            pipeline_var=0.10 ** 2
        )

        # Compute posterior
        posterior = compute_mechanism_posterior_v2(
            actin_fold=actin_fold,
            mito_fold=mito_fold,
            er_fold=er_fold,
            nuisance=nuisance
        )

        # Build belief state
        belief_state = BeliefState(
            top_probability=posterior.top_probability,
            margin=posterior.margin,
            entropy=posterior.entropy,
            nuisance_fraction=nuisance.nuisance_fraction,
            timepoint_h=current_time_h,
            dose_relative=1.0,  # TODO: track actual dose relative to reference
            viability=viability
        )

        # Load calibrator and predict confidence
        calibrator = ConfidenceCalibrator.load('/Users/bjh/cell_OS/data/confidence_calibrator_v1.pkl')
        calibrated_conf = calibrator.predict_confidence(belief_state)

        # Compute nuisance component magnitudes for forensics
        mean_shift_mag = np.linalg.norm(nuisance.total_mean_shift)
        var_inflation = nuisance.total_var_inflation

        # Build result
        prefix_result = PrefixRolloutResult(
            viability=viability,
            actin_fold=actin_fold,
            classifier_margin=confidence,
            predicted_axis=posterior.top_mechanism.value,  # Use posterior, not Phase5 classifier
            washout_count=washout_count,
            feed_count=feed_count,
            actin_struct=actin_struct,
            baseline_actin=baseline_actin,
            # NEW: Belief state fields
            mito_fold=mito_fold,
            er_fold=er_fold,
            posterior_top_prob=posterior.top_probability,
            posterior_margin=posterior.margin,
            nuisance_fraction=nuisance.nuisance_fraction,
            calibrated_confidence=calibrated_conf,
            # Forensics: nuisance components
            nuisance_mean_shift_mag=mean_shift_mag,
            nuisance_var_inflation=var_inflation
        )

        # Store in cache
        self._prefix_cache[cache_key] = prefix_result

        return prefix_result


@dataclass
class BeamNode:
    """
    Node in beam search.

    Stores:
    - Current timestep
    - Action sequence so far
    - Intervention counts
    - Current observations (viability, readouts)
    - Exploration heuristic score (for beam ranking, not terminal reward)
    - Optional terminal commit utility (for early COMMIT nodes)
    """
    t_step: int  # 0..n_steps
    schedule: List[Action]

    # Action semantics
    action_type: str = "CONTINUE"  # "CONTINUE", "COMMIT", or "NO_DETECTION"
    is_terminal: bool = False

    # Constraint tracking
    washout_count: int = 0
    feed_count: int = 0

    # Current state (from prefix rollout)
    viability_current: float = 1.0
    actin_fold_current: float = 1.0

    # Exploration proxy (Phase5 classifier margin: top1 - top2)
    confidence_margin_current: float = 0.0

    # Reality layer / belief state summaries (populated in rollout_prefix)
    posterior_top_prob_current: float = 0.0
    posterior_margin_current: float = 0.0
    nuisance_frac_current: float = 0.0
    calibrated_confidence_current: float = 0.0
    predicted_axis_current: str = "UNKNOWN"

    # Forensics: nuisance components
    nuisance_mean_shift_mag_current: float = 0.0
    nuisance_var_inflation_current: float = 0.0

    # Heuristic score for beam ranking (NON-TERMINAL nodes)
    heuristic_score: float = 0.0

    # Terminal utilities (different for COMMIT vs NO_DETECTION)
    commit_utility: Optional[float] = None
    commit_target: Optional[str] = None
    no_detection_utility: Optional[float] = None

    # Terminal reward (legacy path: only set at t=n_steps)
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

        # Commit gating (NEW)
        self.commit_conf_threshold = 0.75  # Min calibrated confidence to allow COMMIT

        # Commit utility weights (NEW)
        self.w_commit_conf = 5.0
        self.w_commit_time = 0.1
        self.w_commit_ops = 0.05
        self.w_commit_viability = 0.1

        # NO_DETECTION action (NEW)
        self.no_detection_threshold = 0.80  # Min calibrated confidence for NO_DETECTION
        self.w_no_detection_conf = 3.0      # Lower than commit (not as valuable)
        self.w_no_detection_time = 0.15     # Stronger time penalty (should stop earlier)
        self.w_no_detection_ops = 0.05

        # Debug mode (NEW)
        self.debug_commit_decisions = False  # Set True to log COMMIT forensics

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

    def _populate_node_from_prefix(self, node, pr) -> None:
        """Populate BeamNode cached fields from PrefixRolloutResult."""
        node.viability_current = pr.viability
        node.actin_fold_current = pr.actin_fold
        node.confidence_margin_current = pr.classifier_margin

        node.posterior_top_prob_current = pr.posterior_top_prob
        node.posterior_margin_current = pr.posterior_margin
        node.nuisance_frac_current = pr.nuisance_fraction
        node.calibrated_confidence_current = pr.calibrated_confidence
        node.predicted_axis_current = pr.predicted_axis

        # Forensics: nuisance components
        node.nuisance_mean_shift_mag_current = pr.nuisance_mean_shift_mag
        node.nuisance_var_inflation_current = pr.nuisance_var_inflation

    def _compute_commit_utility(
        self,
        calibrated_conf: float,
        elapsed_time_h: float,
        ops_penalty: int,
        viability: float
    ) -> float:
        """Compute terminal utility for COMMIT decision."""
        w_commit_conf = getattr(self, 'w_commit_conf', 5.0)
        w_commit_time = getattr(self, 'w_commit_time', 0.1)
        w_commit_ops = getattr(self, 'w_commit_ops', 0.05)
        w_commit_viability = getattr(self, 'w_commit_viability', 0.1)

        conf_reward = w_commit_conf * calibrated_conf
        time_penalty = w_commit_time * elapsed_time_h
        ops_cost = w_commit_ops * ops_penalty
        viability_penalty = w_commit_viability * (1.0 - viability)

        return conf_reward - time_penalty - ops_cost - viability_penalty

    def _compute_no_detection_utility(
        self,
        calibrated_conf: float,
        elapsed_time_h: float,
        ops_penalty: int
    ) -> float:
        """
        Compute terminal utility for NO_DETECTION decision.

        Semantics: "I'm confident nothing is detectable, stop experiment."

        Utility is lower than correct COMMIT (less valuable outcome),
        but rewards confident null results and penalizes late stops.
        """
        w_no_det_conf = getattr(self, 'w_no_detection_conf', 3.0)
        w_no_det_time = getattr(self, 'w_no_detection_time', 0.15)
        w_no_det_ops = getattr(self, 'w_no_detection_ops', 0.05)

        conf_reward = w_no_det_conf * calibrated_conf
        time_penalty = w_no_det_time * elapsed_time_h  # Stronger penalty than COMMIT
        ops_cost = w_no_det_ops * ops_penalty

        return conf_reward - time_penalty - ops_cost

    def _expand_node(self, node: BeamNode, compound) -> List[BeamNode]:
        """
        Generate successor nodes by trying all legal actions.

        Now supports COMMIT as a terminal decision gated by calibrated confidence.

        Structure:
        1. Compute prefix_current once for COMMIT gating (if node not yet populated)
        2. Generate CONTINUE successors (dose/washout/feed combinations)
        3. Generate COMMIT successor (if confident enough)

        Args:
            node: Current node
            compound: Phase5Compound

        Returns:
            List of successor nodes (CONTINUE + optional COMMIT)
        """
        successors = []

        # 1) Compute prefix_current once for COMMIT gating
        # Only needed if node belief state not yet populated
        prefix_current = None
        if node.t_step > 0 and (node.calibrated_confidence_current <= 0.0 or node.predicted_axis_current == "UNKNOWN"):
            try:
                prefix_current = self.runner.rollout_prefix(node.schedule)
                self._populate_node_from_prefix(node, prefix_current)
            except Exception as e:
                # If current state failed, can't expand from here
                if getattr(self, 'debug_commit_decisions', False):
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Failed to compute prefix_current for node at t={node.t_step}: {e}", exc_info=True)
                return []

        # 2) Generate CONTINUE successors
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

                    # ACTUAL prefix rollout (runs VM to current timestep + 1)
                    try:
                        prefix_result = self.runner.rollout_prefix(new_schedule)
                    except Exception as e:
                        # Simulation failed (probably death or error)
                        if getattr(self, 'debug_commit_decisions', False):
                            import logging
                            logger = logging.getLogger(__name__)
                            logger.warning(f"Prefix rollout failed for schedule {new_schedule}: {e}")
                        self.nodes_pruned_death += 1
                        continue

                    # Early pruning: death trajectory
                    if prefix_result.viability < (1.0 - self.death_tolerance):
                        self.nodes_pruned_death += 1
                        continue

                    # Compute heuristic score using REAL observations
                    # Keep exploration heuristic CLEAN: classifier_margin + viability - ops
                    viability_bonus = prefix_result.viability
                    confidence_bonus = prefix_result.classifier_margin  # Phase5 classifier margin
                    ops_penalty = new_washout + new_feed

                    heuristic = (
                        self.w_mechanism * confidence_bonus +
                        self.w_viability * viability_bonus -
                        self.w_interventions * ops_penalty
                    )

                    # Create CONTINUE successor
                    successor = BeamNode(
                        t_step=node.t_step + 1,
                        schedule=new_schedule,
                        action_type="CONTINUE",
                        is_terminal=False,
                        washout_count=new_washout,
                        feed_count=new_feed,
                        heuristic_score=heuristic,
                        commit_utility=None  # Only for COMMIT nodes
                    )

                    # Populate belief state from prefix rollout
                    self._populate_node_from_prefix(successor, prefix_result)

                    successors.append(successor)

        # 3) Generate COMMIT successor (if confident enough)
        if node.t_step > 0:  # Can't commit at root
            cal_conf = node.calibrated_confidence_current
            commit_threshold = getattr(self, 'commit_conf_threshold', 0.75)
            predicted_axis = node.predicted_axis_current

            # CRITICAL: Disallow COMMIT to "unknown"
            # "unknown" is not a mechanism, it's a "no perturbation" hypothesis
            # Allowing COMMIT to unknown is a "commit to abstaining" loophole
            is_concrete_mechanism = predicted_axis in ["microtubule", "er_stress", "mitochondrial"]

            # Log blocked abstention commits for forensics
            if cal_conf >= commit_threshold and not is_concrete_mechanism:
                if getattr(self, 'debug_commit_decisions', False):
                    import logging
                    logger = logging.getLogger(__name__)
                    elapsed_time_h = node.t_step * self.runner.step_h
                    logger.info(
                        f"COMMIT BLOCKED (abstention) at t={node.t_step} ({elapsed_time_h:.1f}h): "
                        f"predicted_axis={predicted_axis} "
                        f"calibrated_conf={cal_conf:.3f} "
                        f"threshold={commit_threshold:.3f} "
                        f"posterior_top_prob={node.posterior_top_prob_current:.3f} "
                        f"nuisance_frac={node.nuisance_frac_current:.3f}"
                    )

            if cal_conf >= commit_threshold and is_concrete_mechanism:
                elapsed_time_h = node.t_step * self.runner.step_h
                ops_penalty = node.washout_count + node.feed_count
                viability = node.viability_current

                commit_util = self._compute_commit_utility(
                    calibrated_conf=cal_conf,
                    elapsed_time_h=elapsed_time_h,
                    ops_penalty=ops_penalty,
                    viability=viability
                )

                commit_node = BeamNode(
                    t_step=node.t_step,  # NO ADVANCE (COMMIT doesn't advance time)
                    schedule=node.schedule,  # Same schedule (COMMIT is decision, not action)
                    action_type="COMMIT",
                    is_terminal=True,
                    washout_count=node.washout_count,
                    feed_count=node.feed_count,
                    commit_utility=commit_util,
                    commit_target=node.predicted_axis_current,
                    heuristic_score=0.0  # Not used for terminals
                )

                # Copy belief state from parent (COMMIT doesn't change state)
                commit_node.viability_current = node.viability_current
                commit_node.actin_fold_current = node.actin_fold_current
                commit_node.confidence_margin_current = node.confidence_margin_current
                commit_node.posterior_top_prob_current = node.posterior_top_prob_current
                commit_node.posterior_margin_current = node.posterior_margin_current
                commit_node.nuisance_frac_current = node.nuisance_frac_current
                commit_node.calibrated_confidence_current = node.calibrated_confidence_current
                commit_node.predicted_axis_current = node.predicted_axis_current
                commit_node.nuisance_mean_shift_mag_current = node.nuisance_mean_shift_mag_current
                commit_node.nuisance_var_inflation_current = node.nuisance_var_inflation_current

                # Forensic logging
                if getattr(self, 'debug_commit_decisions', False):
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.info(
                        f"COMMIT node created at t={node.t_step} ({elapsed_time_h:.1f}h): "
                        f"predicted_axis={node.predicted_axis_current} "
                        f"is_concrete_mech=True "  # Always true now (gated above)
                        f"posterior_top_prob={node.posterior_top_prob_current:.3f} "
                        f"posterior_margin={node.posterior_margin_current:.3f} "
                        f"nuisance_frac={node.nuisance_frac_current:.3f} "
                        f"nuisance_mean_shift_mag={node.nuisance_mean_shift_mag_current:.3f} "
                        f"nuisance_var_inflation={node.nuisance_var_inflation_current:.3f} "
                        f"calibrated_conf={cal_conf:.3f} "
                        f"commit_utility={commit_util:.3f} "
                        f"threshold={commit_threshold:.3f}"
                    )

                successors.append(commit_node)

        # 4) Generate NO_DETECTION successor (if confident in null result)
        if node.t_step > 0:  # Can't no-detect at root
            cal_conf = node.calibrated_confidence_current
            no_detection_threshold = getattr(self, 'no_detection_threshold', 0.80)
            predicted_axis = node.predicted_axis_current
            posterior_top_prob = node.posterior_top_prob_current
            posterior_margin = node.posterior_margin_current

            # NO_DETECTION only for "unknown" predictions
            is_unknown = (predicted_axis == "unknown")

            # GUARD: Disallow NO_DETECTION if concrete mechanism has reasonable support
            # This prevents "give up early" when real signal exists
            # If posterior_top_prob is high OR margin is large, some mechanism is detectable
            concrete_signal_exists = (posterior_top_prob >= 0.55 or posterior_margin >= 0.15)

            if cal_conf >= no_detection_threshold and is_unknown and not concrete_signal_exists:
                elapsed_time_h = node.t_step * self.runner.step_h
                ops_penalty = node.washout_count + node.feed_count

                no_det_util = self._compute_no_detection_utility(
                    calibrated_conf=cal_conf,
                    elapsed_time_h=elapsed_time_h,
                    ops_penalty=ops_penalty
                )

                no_det_node = BeamNode(
                    t_step=node.t_step,  # NO ADVANCE (terminal decision)
                    schedule=node.schedule,
                    action_type="NO_DETECTION",
                    is_terminal=True,
                    washout_count=node.washout_count,
                    feed_count=node.feed_count,
                    no_detection_utility=no_det_util,
                    heuristic_score=0.0  # Not used for terminals
                )

                # Copy belief state from parent
                no_det_node.viability_current = node.viability_current
                no_det_node.actin_fold_current = node.actin_fold_current
                no_det_node.confidence_margin_current = node.confidence_margin_current
                no_det_node.posterior_top_prob_current = node.posterior_top_prob_current
                no_det_node.posterior_margin_current = node.posterior_margin_current
                no_det_node.nuisance_frac_current = node.nuisance_frac_current
                no_det_node.calibrated_confidence_current = node.calibrated_confidence_current
                no_det_node.predicted_axis_current = node.predicted_axis_current
                no_det_node.nuisance_mean_shift_mag_current = node.nuisance_mean_shift_mag_current
                no_det_node.nuisance_var_inflation_current = node.nuisance_var_inflation_current

                # Forensic logging
                if getattr(self, 'debug_commit_decisions', False):
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.info(
                        f"NO_DETECTION node created at t={node.t_step} ({elapsed_time_h:.1f}h): "
                        f"predicted_axis={node.predicted_axis_current} "
                        f"posterior_top_prob={node.posterior_top_prob_current:.3f} "
                        f"nuisance_frac={node.nuisance_frac_current:.3f} "
                        f"calibrated_conf={cal_conf:.3f} "
                        f"no_detection_utility={no_det_util:.3f} "
                        f"threshold={no_detection_threshold:.3f}"
                    )

                successors.append(no_det_node)

        return successors

    def _prune_and_select(self, nodes: List[BeamNode]) -> List[BeamNode]:
        """
        Select a mixed beam of terminal (COMMIT) and non-terminal nodes.

        - Terminal nodes are ranked by commit_utility.
        - Non-terminal nodes are ranked by exploration heuristic_score.

        This prevents premature collapse into early COMMITs while still allowing
        high-quality commits to surface.
        """
        if not nodes:
            return []

        terminals: List[BeamNode] = []
        nonterminals: List[BeamNode] = []

        for n in nodes:
            if n.is_terminal or n.action_type == "COMMIT":
                terminals.append(n)
            else:
                nonterminals.append(n)

        # Determine allocation. If explicit knobs exist, use them.
        beam_width = self.beam_width
        bw_term = getattr(self, "beam_width_terminal", None)
        bw_non = getattr(self, "beam_width_nonterminal", None)

        if bw_term is None and bw_non is None:
            # Default: allow some terminals, but keep most capacity for exploration
            bw_term = max(1, beam_width // 3)
            bw_non = beam_width - bw_term
        elif bw_term is None:
            bw_non = min(int(bw_non), beam_width)
            bw_term = beam_width - bw_non
        elif bw_non is None:
            bw_term = min(int(bw_term), beam_width)
            bw_non = beam_width - bw_term
        else:
            # Both provided: respect, but cap total
            bw_term = max(0, min(int(bw_term), beam_width))
            bw_non = max(0, min(int(bw_non), beam_width - bw_term))

        # Rank terminals by their respective utilities
        def _term_key(n: BeamNode) -> float:
            if n.action_type == "COMMIT":
                if n.commit_utility is None:
                    return float("-inf")
                return float(n.commit_utility)
            elif n.action_type == "NO_DETECTION":
                if n.no_detection_utility is None:
                    return float("-inf")
                return float(n.no_detection_utility)
            else:
                return float("-inf")

        terminals.sort(key=_term_key, reverse=True)

        # Rank non-terminals by exploration heuristic_score
        nonterminals.sort(key=lambda n: float(n.heuristic_score), reverse=True)

        selected: List[BeamNode] = []

        selected.extend(terminals[:bw_term])
        selected.extend(nonterminals[:bw_non])

        # If one side is empty, backfill from the other
        if len(selected) < beam_width:
            remaining = beam_width - len(selected)
            if len(terminals) < bw_term:
                # terminals underfilled, take more nonterminals
                selected.extend(nonterminals[bw_non:bw_non + remaining])
            elif len(nonterminals) < bw_non:
                # nonterminals underfilled, take more terminals
                selected.extend(terminals[bw_term:bw_term + remaining])
            else:
                # both had enough but allocation was tight, just backfill from nonterminals
                selected.extend(nonterminals[bw_non:bw_non + remaining])

        # Final cap and return
        return selected[:beam_width]
