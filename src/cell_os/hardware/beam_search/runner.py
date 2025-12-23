"""
Phase 5 Episode Runner

Executes episodes with Phase 5 classifier and governance integration.
"""

from typing import List, Optional, Tuple
import numpy as np

from ..episode import Action, Policy, EpisodeRunner, EpisodeReceipt, EpisodeState
from ..biological_virtual import BiologicalVirtualMachine
from ..reward import compute_microtubule_mechanism_reward
from .types import PrefixRolloutResult

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
        from ..masked_compound_phase5 import infer_stress_axis_with_confidence

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
        from ..mechanism_posterior_v2 import compute_mechanism_posterior_v2, NuisanceModel
        from ..confidence_calibrator import ConfidenceCalibrator, BeliefState

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


