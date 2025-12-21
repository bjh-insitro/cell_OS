"""
Phase 6A: Beam search over action sequences.

Deterministic search for optimal action schedule under hard constraints:
- interventions ≤ 2
- death ≤ 20% at 48h

No peeking at hidden truth (latents, true axis). Only observed readouts.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any, Set
import numpy as np

from .episode import Action, Policy, EpisodeRunner, EpisodeReceipt, EpisodeState
from .biological_virtual import BiologicalVirtualMachine
from .reward import compute_microtubule_mechanism_reward
from ..epistemic_agent.governance import (
    Blocker,
    GovernanceAction,
    GovernanceDecision,
    GovernanceInputs,
    GovernanceThresholds,
    decide_governance,
)
from enum import Enum


class ActionIntent(str, Enum):
    """
    Coarse intent tags for actions.

    Used by governance-driven action biasing to prioritize actions that resolve blockers.
    """
    DISCRIMINATE = "DISCRIMINATE"  # Actions likely to separate mechanisms
    REDUCE_NUISANCE = "REDUCE_NUISANCE"  # Washout, wait, replicate, context reset
    AMPLIFY_SIGNAL = "AMPLIFY_SIGNAL"  # Increase dose, extend duration
    OBSERVE = "OBSERVE"  # Measure, readout at a timepoint


def classify_action_intent(action: Action, has_dosed: bool) -> ActionIntent:
    """
    Classify an action's coarse intent.

    This is not perfect taxonomy. It's consistent taxonomy.
    """
    # Washout = reduce nuisance (clear confounders)
    if action.washout:
        return ActionIntent.REDUCE_NUISANCE

    # Feed = reduce nuisance (refresh medium, reduce contact pressure artifacts)
    if action.feed:
        return ActionIntent.REDUCE_NUISANCE

    # No dose = observe (just measure current state)
    if action.dose_fraction == 0.0:
        return ActionIntent.OBSERVE

    # Higher dose after already dosing = amplify signal
    if has_dosed and action.dose_fraction > 0.5:
        return ActionIntent.AMPLIFY_SIGNAL

    # First dose or low dose = discriminate (establish baseline response)
    return ActionIntent.DISCRIMINATE


def action_intent_cost(intent: ActionIntent) -> float:
    """
    Cost model for action intents.

    Returns normalized cost (1.0 = baseline observation).
    These are constants for now, can be refined with empirical data later.

    Cost reflects:
      - TIME: How long does it take?
      - REAGENT: How expensive is it?
      - RISK: How much viability/quality risk?
    """
    costs = {
        ActionIntent.OBSERVE: 1.0,  # Baseline: just measure
        ActionIntent.REDUCE_NUISANCE: 1.5,  # Intervention (washout/feed) + measure
        ActionIntent.DISCRIMINATE: 2.0,  # Dose + measure + analysis
        ActionIntent.AMPLIFY_SIGNAL: 2.5,  # High dose + risk + measure
    }
    return costs[intent]


def compute_action_bias(
    blockers: Set[Blocker],
    evidence_strength: float,
) -> Dict[ActionIntent, float]:
    """
    Map governance blockers to action intent bias multipliers.

    Returns weight multipliers for each ActionIntent (1.0 = neutral, >1.0 = boost, <1.0 = downweight).

    Heuristics:
      - HIGH_NUISANCE → boost REDUCE_NUISANCE, downweight AMPLIFY_SIGNAL (don't make it worse)
      - LOW_POSTERIOR_TOP → boost DISCRIMINATE and OBSERVE
      - Both blockers → prioritize nuisance reduction first (confounded discrimination is useless)
    """
    if not blockers:
        # No blockers: neutral bias
        return {intent: 1.0 for intent in ActionIntent}

    bias = {intent: 1.0 for intent in ActionIntent}

    # Blocker: HIGH_NUISANCE
    if Blocker.HIGH_NUISANCE in blockers:
        bias[ActionIntent.REDUCE_NUISANCE] = 3.0  # Strong boost
        bias[ActionIntent.OBSERVE] = 1.5  # Moderate boost (observe after cleanup)
        bias[ActionIntent.AMPLIFY_SIGNAL] = 0.3  # Downweight (don't escalate into noise)
        bias[ActionIntent.DISCRIMINATE] = 0.5  # Downweight (confounded discrimination is misleading)

    # Blocker: LOW_POSTERIOR_TOP
    if Blocker.LOW_POSTERIOR_TOP in blockers:
        # If nuisance is ALSO high, prioritize nuisance first (already handled above)
        if Blocker.HIGH_NUISANCE not in blockers:
            bias[ActionIntent.DISCRIMINATE] = 2.5  # Strong boost
            bias[ActionIntent.OBSERVE] = 2.0  # Boost observation
            # If evidence is weak, might need signal amplification
            if evidence_strength < 0.5:
                bias[ActionIntent.AMPLIFY_SIGNAL] = 1.5

    return bias


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
    nuisance_fraction: float = 0.0  # v2: stores nuisance_probability (observation-aware)
    calibrated_confidence: float = 0.0

    # Forensics: nuisance model components
    nuisance_mean_shift_mag: float = 0.0  # ||mean_shift||
    nuisance_var_inflation: float = 0.0   # Total variance inflation

    # CAUSAL ATTRIBUTION: Full posterior for split-ledger accounting
    posterior: Optional[object] = None  # MechanismPosterior object
    attribution_source: Optional[str] = None  # "evidence" | "nuisance_reweight" | "both" | "none"


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

        # Cached calibrator (load once instead of every rollout)
        self._calibrator = None

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

        # Capture baseline vessel state (for contact_pressure baseline)
        baseline_vessel = vm.vessel_states["episode"]

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

        # Tie variance inflations to shift magnitude (not constants)
        pipeline_shift = np.array([0.01, -0.01, 0.01])
        shift_mag = np.linalg.norm(context_shift + pipeline_shift)
        shift_mag = min(shift_mag, 0.25)  # Cap to avoid pathological cases

        k_context = 0.5  # Scale factors chosen so typical shift_mag ~ 0.05 gives small variances
        k_pipe = 0.3
        context_var = (k_context * shift_mag) ** 2
        pipeline_var = (k_pipe * shift_mag) ** 2

        # Contact pressure nuisance: mean shift in fold-space from Δp between baseline and readout
        # IMPORTANT: use baseline pressure from the same baseline measurement that produced baseline_* values
        p_obs = float(np.clip(getattr(vessel, "contact_pressure", 0.0), 0.0, 1.0))
        p_base = float(np.clip(getattr(baseline_vessel, "contact_pressure", 0.0), 0.0, 1.0))
        delta_p = float(np.clip(p_obs - p_base, -1.0, 1.0))
        contact_shift = np.array([
            0.10 * delta_p,   # actin
            -0.05 * delta_p,  # mito
            0.06 * delta_p    # ER
        ])
        # Small variance term to reflect model mismatch (kept conservative)
        contact_var = (0.10 * abs(delta_p) * 0.25) ** 2  # tweak later; ~ (2.5% at full Δp)^2

        nuisance = NuisanceModel(
            context_shift=context_shift,
            pipeline_shift=pipeline_shift,
            contact_shift=contact_shift,
            artifact_var=artifact_var,
            heterogeneity_var=hetero_width ** 2,
            context_var=context_var,
            pipeline_var=pipeline_var,
            contact_var=contact_var
        )

        # CAUSAL ATTRIBUTION: Look up prior posterior for split-ledger accounting
        prior_posterior = None
        if n_steps_prefix > 1:
            # Look up prior prefix (one step back)
            prior_schedule_prefix = schedule_prefix[:-1]
            prior_cache_key = (tuple((a.dose_fraction, a.washout, a.feed) for a in prior_schedule_prefix), n_steps_prefix - 1)
            if prior_cache_key in self._prefix_cache:
                prior_result = self._prefix_cache[prior_cache_key]
                prior_posterior = prior_result.posterior

        # Compute posterior (with split-ledger accounting if prior available)
        posterior = compute_mechanism_posterior_v2(
            actin_fold=actin_fold,
            mito_fold=mito_fold,
            er_fold=er_fold,
            nuisance=nuisance,
            prior_posterior=prior_posterior
        )

        # Build belief state
        belief_state = BeliefState(
            top_probability=posterior.top_probability,
            margin=posterior.margin,
            entropy=posterior.entropy,
            nuisance_fraction=nuisance.inflation_share_nonhetero,  # v1: bookkeeping ratio
            nuisance_probability=posterior.nuisance_probability,   # v2: observation-aware P(NUISANCE|x)
            timepoint_h=current_time_h,
            dose_relative=1.0,  # TODO: track actual dose relative to reference
            viability=viability
        )

        # Load calibrator once and cache (avoid reloading on every rollout)
        if self._calibrator is None:
            self._calibrator = ConfidenceCalibrator.load('/Users/bjh/cell_OS/data/confidence_calibrator_v1.pkl')
        calibrated_conf = self._calibrator.predict_confidence(belief_state)

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
            nuisance_fraction=posterior.nuisance_probability,  # v2: observation-aware P(NUISANCE|x)
            calibrated_confidence=calibrated_conf,
            # Forensics: nuisance components
            nuisance_mean_shift_mag=mean_shift_mag,
            nuisance_var_inflation=var_inflation,
            # CAUSAL ATTRIBUTION: Store full posterior and attribution source
            posterior=posterior,
            attribution_source=posterior.attribution_source
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
class NoCommitEpisode:
    """
    Track a single NO_COMMIT episode for cost-aware closed-loop analysis.

    An episode is a window from NO_COMMIT decision to resolution (commit/detection) or timeout.
    """
    episode_id: str  # Unique identifier
    t_start: int  # Timestep when NO_COMMIT fired
    blockers_start: Set[Blocker]  # Which blockers caused NO_COMMIT
    posterior_gap_start: float
    nuisance_gap_start: float

    # Actions taken to resolve (window of k steps)
    actions_taken: List[ActionIntent]  # Sequence of intents chosen
    costs_incurred: List[float]  # Cost per action

    # Outcome after k steps
    t_end: int
    blockers_end: Set[Blocker]  # Which blockers remain
    posterior_gap_end: float
    nuisance_gap_end: float

    # Derived metrics
    @property
    def total_cost(self) -> float:
        return sum(self.costs_incurred)

    @property
    def posterior_gap_reduction(self) -> float:
        return self.posterior_gap_start - self.posterior_gap_end

    @property
    def nuisance_gap_reduction(self) -> float:
        return self.nuisance_gap_start - self.nuisance_gap_end

    @property
    def gap_reduction_per_cost(self) -> float:
        """Primary KPI: information-optimal metric."""
        if self.total_cost == 0:
            return 0.0
        total_reduction = self.posterior_gap_reduction + self.nuisance_gap_reduction
        return total_reduction / self.total_cost

    @property
    def resolved(self) -> bool:
        """Did we resolve at least one blocker?"""
        return len(self.blockers_end) < len(self.blockers_start)


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

    # Governance forensics (what the contract decided and why)
    governance_action: Optional[str] = None  # "COMMIT", "NO_COMMIT", "NO_DETECTION"
    governance_reason: Optional[str] = None
    governance_mechanism: Optional[str] = None  # Approved mechanism if COMMIT
    governance_posterior_top: Optional[float] = None
    governance_nuisance_prob: Optional[float] = None
    governance_evidence_strength: Optional[float] = None

    # Distance to commit tracking (closed-loop KPI)
    governance_posterior_gap: Optional[float] = None  # max(0, threshold - posterior_top)
    governance_nuisance_gap: Optional[float] = None  # max(0, nuisance - threshold)


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
        w_interventions: float = 0.1,  # Small penalty for interventions
        # Action space
        dose_levels: Optional[List[float]] = None
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

        # Action space (configurable for speed testing)
        self.dose_levels = dose_levels if dose_levels is not None else [0.0, 0.25, 0.5, 1.0]

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

        # GOVERNANCE FORENSICS: Capture what the contract decided and why
        # This enables "why didn't it commit?" debugging without rerunning
        gov_decision = self._apply_governance_contract(best_node)

        # DISTANCE TO COMMIT: Compute gaps (closed-loop KPI)
        # These measure "how far from being allowed to commit"
        thresholds = GovernanceThresholds()
        posterior_gap = max(0.0, thresholds.commit_posterior_min - best_node.posterior_top_prob_current)
        nuisance_gap = max(0.0, best_node.nuisance_frac_current - thresholds.nuisance_max_for_commit)

        return BeamSearchResult(
            best_schedule=best_node.schedule,
            best_policy=best_policy,
            best_reward=best_receipt.reward_total,
            best_receipt=best_receipt,
            nodes_expanded=self.nodes_expanded,
            nodes_pruned_death=self.nodes_pruned_death,
            nodes_pruned_interventions=self.nodes_pruned_interventions,
            nodes_pruned_dominated=self.nodes_pruned_dominated,
            # Governance forensics
            governance_action=gov_decision.action.value,
            governance_reason=gov_decision.reason,
            governance_mechanism=gov_decision.mechanism,
            governance_posterior_top=best_node.posterior_top_prob_current,
            governance_nuisance_prob=best_node.nuisance_frac_current,
            governance_evidence_strength=best_node.posterior_top_prob_current,  # Using as proxy
            # Distance to commit (closed-loop KPI)
            governance_posterior_gap=posterior_gap,
            governance_nuisance_gap=nuisance_gap,
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

    def _apply_governance_contract(self, node: BeamNode) -> GovernanceDecision:
        """
        Apply governance contract to node's belief state.

        This is the choke point: all terminal decisions (COMMIT/NO_DETECTION) must pass through here.

        Constructs GovernanceInputs from node's belief state and delegates to decide_governance.
        """
        # Build minimal posterior dict from node's belief state
        # We only have top mechanism + probability, so construct a minimal dict
        predicted_mech = node.predicted_axis_current
        top_prob = node.posterior_top_prob_current

        if predicted_mech and predicted_mech != "unknown":
            posterior = {predicted_mech: top_prob}
        else:
            # No concrete mechanism predicted
            posterior = {}

        # Use posterior_top_prob as evidence_strength proxy
        # Interpretation: if the top mechanism has high probability, evidence exists
        evidence_strength = top_prob

        gov_inputs = GovernanceInputs(
            posterior=posterior,
            nuisance_prob=node.nuisance_frac_current,
            evidence_strength=evidence_strength,
        )

        # Use default thresholds (can be customized later)
        thresholds = GovernanceThresholds(
            commit_posterior_min=0.80,
            nuisance_max_for_commit=0.35,
            evidence_min_for_detection=0.70,
        )

        return decide_governance(gov_inputs, thresholds)

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

        # GOVERNANCE-DRIVEN BIASING: If in NO_COMMIT state, compute action bias from blockers
        # This makes NO_COMMIT productive by prioritizing actions that resolve blockers
        gov_decision_for_bias = self._apply_governance_contract(node) if node.t_step > 0 else None
        action_bias = {}
        if gov_decision_for_bias and gov_decision_for_bias.action == GovernanceAction.NO_COMMIT:
            evidence_strength = node.posterior_top_prob_current
            action_bias = compute_action_bias(gov_decision_for_bias.blockers, evidence_strength)

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

                    # APPLY GOVERNANCE BIAS: Multiply heuristic by action intent bias
                    # This prioritizes actions that resolve blockers (productive NO_COMMIT)
                    if action_bias:
                        intent = classify_action_intent(action, has_dosed)
                        bias_multiplier = action_bias.get(intent, 1.0)
                        heuristic *= bias_multiplier

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

        # 3) Generate COMMIT successor (if governance contract allows)
        if node.t_step > 0:  # Can't commit at root
            # GOVERNANCE CHOKE POINT: All terminal decisions must pass through contract
            gov_decision = self._apply_governance_contract(node)

            if gov_decision.action == GovernanceAction.COMMIT:
                elapsed_time_h = node.t_step * self.runner.step_h
                ops_penalty = node.washout_count + node.feed_count
                viability = node.viability_current
                cal_conf = node.calibrated_confidence_current

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
                    commit_target=gov_decision.mechanism,  # CONTRACT: mechanism approved by governance
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

            elif gov_decision.action == GovernanceAction.NO_DETECTION:
                # CONTRACT: NO_DETECTION only allowed when contract permits (low evidence)
                cal_conf = node.calibrated_confidence_current
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

            # else: gov_decision.action == GovernanceAction.NO_COMMIT
            #   CONTRACT: No terminal node created, beam search continues exploring
            #   This is the correct behavior when evidence exists but confidence isn't sufficient

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
