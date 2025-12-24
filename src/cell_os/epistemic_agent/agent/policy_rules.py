"""
Evidence-driven policy using BeliefState + TemplateChooser.

v0.4.2: Pay-for-calibration regime with gate lock invariant.
- Uses BeliefState to track what we know (with receipts)
- Uses TemplateChooser to decide what to test next
- Hard constraint: no biology until noise gate earned
"""

import hashlib
import json
from dataclasses import asdict, is_dataclass
from typing import Optional, Any, Mapping
from ..schemas import WellSpec, Proposal
from ..beliefs import BeliefState
from ..acquisition import TemplateChooser
from ..accountability import AccountabilityConfig, requires_spatial_mitigation, make_replate_proposal


def _normalize_for_hash(x: Any) -> Any:
    """Make x JSON-stable: deterministic ordering, JSON-safe primitives, repr fallback."""
    if x is None or isinstance(x, (bool, int, str)):
        return x
    if isinstance(x, float):
        # Stable float representation. Keep it simple.
        return float(f"{x:.12g}")
    if is_dataclass(x):
        return _normalize_for_hash(asdict(x))
    if isinstance(x, Mapping):
        # Sort keys to remove dict order drift
        return {str(k): _normalize_for_hash(v) for k, v in sorted(x.items(), key=lambda kv: str(kv[0]))}
    if isinstance(x, (list, tuple, set)):
        seq = list(x)
        # Sets are unordered; sort their normalized repr for stability
        if isinstance(x, set):
            seq = sorted((_normalize_for_hash(v) for v in seq), key=lambda v: json.dumps(v, sort_keys=True))
            return seq
        return [_normalize_for_hash(v) for v in seq]
    # Path, numpy scalars, enums, custom objects, etc.
    return repr(x)


def design_hash(template: str, spec: Mapping[str, Any], *, template_version: int = 1, length: int = 12) -> str:
    """
    Content hash of the well-defining spec (does NOT include cycle).

    Args:
        template: Template name (e.g., "baseline", "dose_ladder")
        spec: Dict of parameters that define which wells get generated
        template_version: Version number for template logic changes
        length: Hash length in hex characters

    Returns:
        Hex string content hash (e.g., "a1b2c3d4e5f6")

    Hash schema versioning:
        hash_schema="v1" is baked into the hash to prevent confusion if normalization
        semantics change later. If you ever need to change float formatting, dict
        ordering, or _normalize_for_hash behavior, bump hash_schema to "v2" to force
        all hashes to change (prevents "same spec, different hash" debugging hell).
    """
    payload = {
        "hash_schema": "v1",  # Bump this if normalization semantics change
        "template": template,
        "template_version": template_version,
        "spec": _normalize_for_hash(dict(spec)),
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha1(blob).hexdigest()[:length]


def deterministic_design_id(
    template: str,
    cycle: int,
    spec: Mapping[str, Any],
    *,
    template_version: int = 1,
    hash_len: int = 12,
) -> str:
    """
    Run-context identifier: unique per cycle, idempotent for same spec within the same cycle.

    Args:
        template: Template name (e.g., "baseline", "dose_ladder")
        cycle: Cycle number (ensures uniqueness across cycles)
        spec: Dict of parameters that define which wells get generated
        template_version: Version number for template logic changes
        hash_len: Hash length in hex characters (min 8 for collision resistance)

    Returns:
        Design ID like "baseline_c0001_a1b2c3d4e5f6" (deterministic)

    Examples:
        >>> deterministic_design_id("baseline", 1, {"n_reps": 12})
        'baseline_c0001_...'
        >>> deterministic_design_id("dose_ladder", 5, {"compound": "tBHQ", "doses_uM": [0.01, 0.1, 1.0, 10.0]})
        'dose_ladder_c0005_...'

    Spec policy (per template):
    - Baseline-style (minimal): Only values that vary across calls + template_version for constants
    - Dose-ladder-style (explicit): All values that define wells (even if constant)
    Both are valid; pick one per template and stick to it.
    """
    # Cheap insurance: catch accidental misuse
    assert isinstance(cycle, int), f"cycle must be int, got {type(cycle)}"
    assert hash_len >= 8, f"hash_len must be >= 8 for collision resistance, got {hash_len}"

    h = design_hash(template, spec, template_version=template_version, length=hash_len)
    return f"{template}_c{cycle:04d}_{h}"


class RuleBasedPolicy:
    """Evidence-driven policy with accountability."""

    def __init__(
        self,
        budget: int = 384,
        accountability: Optional[AccountabilityConfig] = None,
        seed: int = 0
    ):
        self.budget = budget
        self.budget_remaining = budget
        self.seed = seed
        self.beliefs = BeliefState()
        self.chooser = TemplateChooser()
        self.last_diagnostics = None
        self.last_decision = None  # v0.5.0: Canonical Decision object (kills side-channel)
        self.cycle = 0
        self.accountability = accountability or AccountabilityConfig()
        self._last_proposal: Optional[Proposal] = None
        self.layout_epoch = 0  # Track layout variations for REPLATE mitigation
        self.consecutive_epistemic_replications = 0  # Track consecutive REPLICATE actions

    def propose_next_experiment(
        self,
        capabilities: dict,
        previous_observation: Optional[dict] = None
    ) -> Proposal:
        """Propose next experiment using chooser + beliefs.

        v0.4.2: Enforces pay-for-calibration constraints.
        v0.5.0: Returns Decision object with full provenance (kills side-channel pattern).
        v0.6.0: Accountability override - replate if spatial QC flagged.
        """
        # Accountability override: check spatial QC before normal proposal logic
        if self.accountability.enabled and previous_observation:
            qc_struct = previous_observation.get("qc_struct", {})
            if requires_spatial_mitigation(qc_struct, self.accountability.spatial_key):
                # Spatial autocorrelation flagged: must replate
                if self._last_proposal is None:
                    # Fallback: no previous proposal to replate (first cycle or reset)
                    # Proceed with normal baseline generation but log the constraint
                    pass  # Fall through to normal logic
                else:
                    # Replate with explicit audit trail
                    replate_seed = self.seed + self.cycle
                    reason = f"spatial_autocorrelation[{self.accountability.spatial_key}]"
                    return make_replate_proposal(
                        self._last_proposal,
                        layout_seed=replate_seed,
                        reason=reason
                    )

        self.cycle += 1

        # Choose template based on current beliefs
        # v0.5.0: chooser.choose_next() now returns Decision (not tuple)
        decision = self.chooser.choose_next(
            beliefs=self.beliefs,
            budget_remaining_wells=self.budget_remaining,
            cycle=self.cycle
        )

        # Store decision for provenance (replaces side-channel last_decision_event)
        self.last_decision = decision

        # Extract template and kwargs from decision
        template_name = decision.chosen_template
        template_kwargs = dict(decision.chosen_kwargs)

        # Handle abort
        if template_name == "abort" or decision.kind == "abort":
            reason = template_kwargs.get("reason", "Unknown")
            raise RuntimeError(f"ABORT EXPERIMENT: {reason}")

        # Map template to proposal
        proposal = None
        if template_name == "baseline_replicates":
            proposal = self._template_baseline_replicates(capabilities, **template_kwargs)
        elif template_name == "edge_center_test":
            proposal = self._template_edge_center_test(capabilities, **template_kwargs)
        elif template_name == "dose_ladder_coarse":
            proposal = self._template_dose_ladder_coarse(capabilities, **template_kwargs)
        # v0.5.0: Assay ladder templates
        elif template_name == "calibrate_ldh_baseline":
            proposal = self._template_calibrate_ldh_baseline(capabilities, **template_kwargs)
        elif template_name == "calibrate_cell_paint_baseline":
            proposal = self._template_calibrate_cell_paint_baseline(capabilities, **template_kwargs)
        elif template_name == "calibrate_scrna_baseline":
            proposal = self._template_calibrate_scrna_baseline(capabilities, **template_kwargs)
        elif template_name == "cell_paint_screen":
            proposal = self._template_cell_paint_screen(capabilities, **template_kwargs)
        elif template_name == "scrna_upgrade_probe":
            proposal = self._template_scrna_upgrade_probe(capabilities, **template_kwargs)
        elif template_name == "abort_insufficient_assay_gate_budget":
            assay = template_kwargs.get("assay", "unknown")
            block_reason = template_kwargs.get("block_reason", "Unknown")
            calib_plan = template_kwargs.get("calibration_plan", {})
            reason = template_kwargs.get("reason", f"Cannot afford {assay} gate calibration")
            raise RuntimeError(f"ABORT EXPERIMENT: {reason}. Calibration plan: {calib_plan}")
        else:
            # Fallback
            proposal = self._template_baseline_replicates(capabilities, n_reps=12, reason="Fallback")

        # Cache proposal for potential replate
        self._last_proposal = proposal
        return proposal

    def _template_baseline_replicates(
        self,
        cap: dict,
        n_reps: int = 12,
        reason: str = "Measure baseline noise",
        coverage_strategy: str = "center_only",  # Ignored, for Documentary only
        **extra_kwargs  # Ignore other Documentary-only params
    ) -> Proposal:
        """Template: DMSO replicates at center position."""
        spec = {"n_reps": n_reps}
        design_id = deterministic_design_id("baseline", self.cycle, spec, template_version=1)

        wells = []
        for i in range(n_reps):
            wells.append(WellSpec(
                cell_line='A549',
                compound='DMSO',
                dose_uM=0.0,
                time_h=12.0,
                assay='cell_painting',
                position_tag='center'
            ))

        return Proposal(
            design_id=design_id,
            hypothesis=f"{reason}. Calibration: measure instrument noise to establish confidence intervals.",
            wells=wells,
            budget_limit=self.budget_remaining
        )

    def _template_edge_center_test(
        self,
        cap: dict,
        reason: str = "Test edge effects"
    ) -> Proposal:
        """Template: Compare edge vs center wells."""
        # Hash what defines the wells
        spec = {
            "compounds": ["DMSO", "tBHQ"],
            "doses_uM": [0.0, 10.0],
            "reps_per_position": 6,
            "positions": ["edge", "center"],
            "cell_line": "A549",
            "assay": "cell_painting",
            "time_h": 12.0,
        }
        design_id = deterministic_design_id("edge_test", self.cycle, spec, template_version=1)

        wells = []

        # 6 DMSO edge, 6 DMSO center
        for i in range(6):
            wells.append(WellSpec(
                cell_line='A549',
                compound='DMSO',
                dose_uM=0.0,
                time_h=12.0,
                assay='cell_painting',
                position_tag='edge'
            ))
        for i in range(6):
            wells.append(WellSpec(
                cell_line='A549',
                compound='DMSO',
                dose_uM=0.0,
                time_h=12.0,
                assay='cell_painting',
                position_tag='center'
            ))

        # 6 tBHQ edge, 6 tBHQ center (for robustness)
        for i in range(6):
            wells.append(WellSpec(
                cell_line='A549',
                compound='tBHQ',
                dose_uM=10.0,
                time_h=12.0,
                assay='cell_painting',
                position_tag='edge'
            ))
        for i in range(6):
            wells.append(WellSpec(
                cell_line='A549',
                compound='tBHQ',
                dose_uM=10.0,
                time_h=12.0,
                assay='cell_painting',
                position_tag='center'
            ))

        return Proposal(
            design_id=design_id,
            hypothesis=f"{reason}. Test if well position (edge vs center) introduces systematic bias.",
            wells=wells,
            budget_limit=self.budget_remaining
        )

    def _template_dose_ladder_coarse(
        self,
        cap: dict,
        reason: str = "Explore dose-response"
    ) -> Proposal:
        """Template: Coarse dose ladder for compound."""
        # Pick untested compound
        tested = self.beliefs.tested_compounds - {'DMSO'}
        available = set(cap.get('compounds', [])) - {'DMSO'} - tested

        if available:
            compound = sorted(available)[0]
        else:
            compound = 'tBHQ'  # fallback

        doses = [0.01, 0.1, 1.0, 10.0]

        # Define wells based on chosen compound and doses
        spec = {
            "compound": compound,
            "doses_uM": doses,
            "reps": 3,
            "cell_line": "A549",
            "assay": "cell_painting",
            "time_h": 12.0,
            "position_tag": "center",
        }
        design_id = deterministic_design_id("dose_ladder", self.cycle, spec, template_version=1)

        wells = []
        for dose in doses:
            for rep in range(3):
                wells.append(WellSpec(
                    cell_line='A549',
                    compound=compound,
                    dose_uM=dose,
                    time_h=12.0,
                    assay='cell_painting',
                    position_tag='center'
                ))

        return Proposal(
            design_id=design_id,
            hypothesis=f"{reason}. Map dose-response for {compound} across 4 log-spaced doses.",
            wells=wells,
            budget_limit=self.budget_remaining
        )

    def _template_calibrate_ldh_baseline(
        self,
        cap: dict,
        n_reps: int = 12,
        assay: str = "ldh",
        reason: str = "Calibrate LDH assay gate"
    ) -> Proposal:
        """Template: DMSO replicates for LDH assay calibration.

        v0.5.0: LDH proxy using noisy_morphology until real LDH assay added.
        """
        spec = {"n_reps": n_reps, "assay": assay}
        design_id = deterministic_design_id("ldh_calib", self.cycle, spec, template_version=1)

        wells = []
        for i in range(n_reps):
            wells.append(WellSpec(
                cell_line='A549',
                compound='DMSO',
                dose_uM=0.0,
                time_h=12.0,
                assay='ldh',  # Declare LDH assay intent (proxy: noisy_morphology)
                position_tag='center'
            ))

        return Proposal(
            design_id=design_id,
            hypothesis=f"{reason}. LDH gate calibration (proxy: noisy_morphology).",
            wells=wells,
            budget_limit=self.budget_remaining
        )

    def _template_calibrate_cell_paint_baseline(
        self,
        cap: dict,
        n_reps: int = 12,
        assay: str = "cell_paint",
        reason: str = "Calibrate Cell Painting assay gate"
    ) -> Proposal:
        """Template: DMSO replicates for Cell Painting assay calibration.

        v0.5.0: Cell Painting uses noisy_morphology (existing signal).
        """
        spec = {"n_reps": n_reps, "assay": assay}
        design_id = deterministic_design_id("cp_calib", self.cycle, spec, template_version=1)

        wells = []
        for i in range(n_reps):
            wells.append(WellSpec(
                cell_line='A549',
                compound='DMSO',
                dose_uM=0.0,
                time_h=12.0,
                assay='cell_painting',
                position_tag='center'
            ))

        return Proposal(
            design_id=design_id,
            hypothesis=f"{reason}. Cell Painting gate calibration (morphology features).",
            wells=wells,
            budget_limit=self.budget_remaining
        )

    def _template_calibrate_scrna_baseline(
        self,
        cap: dict,
        n_reps: int = 6,  # Smaller, expensive
        assay: str = "scrna",
        reason: str = "Calibrate scRNA assay gate"
    ) -> Proposal:
        """Template: DMSO replicates for scRNA assay calibration (placeholder).

        v0.5.0: scRNA placeholder using noisy_morphology proxy. Small n_reps (expensive).
        """
        spec = {"n_reps": n_reps, "assay": assay}
        design_id = deterministic_design_id("scrna_calib", self.cycle, spec, template_version=1)

        wells = []
        for i in range(n_reps):
            wells.append(WellSpec(
                cell_line='A549',
                compound='DMSO',
                dose_uM=0.0,
                time_h=12.0,
                assay='scrna',  # Declare scRNA intent (proxy: noisy_morphology)
                position_tag='center'
            ))

        return Proposal(
            design_id=design_id,
            hypothesis=f"{reason}. scRNA gate calibration (placeholder: proxy morphology).",
            wells=wells,
            budget_limit=self.budget_remaining
        )

    def _template_cell_paint_screen(
        self,
        cap: dict,
        reason: str = "Screen compounds with Cell Painting"
    ) -> Proposal:
        """Template: Small Cell Painting screen across diverse compounds."""
        # Diverse compound panel
        compounds = ['Staurosporine', 'Paclitaxel', 'Doxorubicin', 'DMSO']

        # Hash what defines the wells
        spec = {
            "compounds": compounds,
            "dose_uM": 1.0,
            "reps": 3,
            "cell_line": "A549",
            "assay": "cell_painting",
            "time_h": 12.0,
            "position_tag": "center",
        }
        design_id = deterministic_design_id("cp_screen", self.cycle, spec, template_version=1)

        wells = []
        for compound in compounds:
            dose = 1.0 if compound != 'DMSO' else 0.0
            for rep in range(3):
                wells.append(WellSpec(
                    cell_line='A549',
                    compound=compound,
                    dose_uM=dose,
                    time_h=12.0,
                    assay='cell_painting',
                    position_tag='center'
                ))

        return Proposal(
            design_id=design_id,
            hypothesis=f"{reason}. Screen {len(compounds)} compounds with Cell Painting morphology.",
            wells=wells,
            budget_limit=self.budget_remaining
        )

    def _template_scrna_upgrade_probe(
        self,
        cap: dict,
        novelty_score: float = 0.0,
        ldh_viable: bool = True,
        reason: str = "Upgrade to scRNA for mechanistic insight"
    ) -> Proposal:
        """Template: scRNA probe on selected conditions (upgrade from CP).

        v0.5.0: Placeholder implementation. Real version would select conditions
        based on CP novelty clusters.

        NOTE: novelty_score and ldh_viable are NOT included in design_id yet
        because they don't affect which wells get generated (TODO for later).
        """
        # Placeholder: run scRNA on most interesting compound (proxy: use last non-DMSO)
        compound = 'Staurosporine'

        # Hash only what defines wells TODAY (not unused kwargs)
        spec = {
            "compound": compound,
            "dose_uM": 1.0,
            "reps": 3,
            "cell_line": "A549",
            "assay": "scrna",
            "time_h": 12.0,
            "position_tag": "center",
        }
        design_id = deterministic_design_id("scrna_probe", self.cycle, spec, template_version=1)

        wells = []
        for rep in range(3):  # Small n for expensive assay
            wells.append(WellSpec(
                cell_line='A549',
                compound=compound,
                dose_uM=1.0,
                time_h=12.0,
                assay='scrna',
                position_tag='center'
            ))

        return Proposal(
            design_id=design_id,
            hypothesis=f"{reason}. scRNA probe (novelty={novelty_score:.3f}, ldh_viable={ldh_viable}).",
            wells=wells,
            budget_limit=self.budget_remaining
        )

    def update_from_observation(self, observation: dict):
        """Update beliefs from observation.

        v0.4.2: Updates BeliefState with evidence tracking.
        """
        self.budget_remaining = observation.budget_remaining

        # Update beliefs (returns events + diagnostics)
        events, diagnostics = self.beliefs.update(observation, cycle=self.cycle)

        # Store diagnostics for logging
        self.last_diagnostics = diagnostics

    def choose_mitigation_action(
        self,
        observation,
        budget_plates_remaining: float,
        previous_proposal
    ):
        """Choose mitigation action based on QC flags and budget.

        Args:
            observation: Observation with QC flags
            budget_plates_remaining: Budget remaining in plate equivalents
            previous_proposal: The proposal that triggered QC flag

        Returns:
            (action, rationale) tuple
        """
        from ..mitigation import get_spatial_qc_summary
        from ..accountability import MitigationAction

        flagged, morans_i_max, details = get_spatial_qc_summary(observation)

        if not flagged:
            return (MitigationAction.NONE, "No QC flags detected")

        if budget_plates_remaining < 0.5:
            return (
                MitigationAction.NONE,
                f"Insufficient budget ({budget_plates_remaining:.2f} plates)"
            )

        # Severity threshold: I > 0.5 is severe
        if morans_i_max > 0.5:
            return (
                MitigationAction.REPLATE,
                f"Severe spatial correlation (I={morans_i_max:.3f})"
            )
        else:
            return (
                MitigationAction.REPLICATE,
                f"Moderate spatial correlation (I={morans_i_max:.3f})"
            )

    def create_mitigation_proposal(
        self,
        action,
        previous_proposal,
        capabilities: dict
    ):
        """Create mitigation proposal based on action."""
        from ..accountability import MitigationAction, make_replicate_proposal

        if action == MitigationAction.REPLATE:
            self.layout_epoch += 1
            new_layout_seed = self.seed + 10_000 * self.layout_epoch
            proposal = make_replate_proposal(previous_proposal, layout_seed=new_layout_seed)
            return proposal
        elif action == MitigationAction.REPLICATE:
            return make_replicate_proposal(previous_proposal)
        else:
            raise ValueError(f"Cannot create proposal for action {action}")

    def choose_epistemic_action(
        self,
        observation,
        budget_plates_remaining: float,
        previous_proposal,
        previous_observation_dict
    ):
        """Choose epistemic action based on calibration uncertainty and budget.

        Decision logic:
        1. Query current calibration uncertainty from beliefs
        2. If consecutive replications ≥ cap: force EXPAND (prevent infinite loops)
        3. If uncertainty > threshold and budget allows replication: REPLICATE
        4. Else if budget allows expansion: EXPAND
        5. Else: NONE

        Threshold: 4.0 bits (mid-range calibration uncertainty)
        - Above 4.0: measurement quality uncertain, replicate to tighten ruler
        - Below 4.0: ruler confident enough, safe to explore

        GUARDRAIL: Max consecutive replications = 2
        - Prevents budget death spiral if uncertainty proxy doesn't drop reliably
        - Forces expansion after 2 consecutive REPLICATE actions
        - Logs when cap triggers forced EXPAND

        Args:
            observation: Latest observation with belief updates
            budget_plates_remaining: Budget remaining in plate equivalents
            previous_proposal: Proposal from previous cycle
            previous_observation_dict: Observation dict from previous cycle (for EXPAND)

        Returns:
            (action, rationale) tuple
        """
        from ..epistemic_actions import EpistemicAction

        # Query current calibration uncertainty
        uncertainty = self.beliefs.estimate_calibration_uncertainty()

        # Decision thresholds
        uncertainty_threshold = 4.0  # bits
        max_consecutive_replications = 2

        # Budget for replication
        replication_cost_wells = len(previous_proposal.wells)
        replication_cost_plates = replication_cost_wells / 96.0

        # GUARDRAIL: Cap consecutive replications to prevent infinite loops
        if self.consecutive_epistemic_replications >= max_consecutive_replications:
            self.consecutive_epistemic_replications = 0  # Reset counter
            return (
                EpistemicAction.EXPAND,
                f"Max consecutive replications ({max_consecutive_replications}) reached, "
                f"forcing expansion despite high uncertainty ({uncertainty:.2f} bits)"
            )

        # Decision logic
        if uncertainty > uncertainty_threshold:
            if budget_plates_remaining >= replication_cost_plates:
                return (
                    EpistemicAction.REPLICATE,
                    f"High calibration uncertainty ({uncertainty:.2f} bits > {uncertainty_threshold:.1f} threshold), "
                    f"replicate to tighten ruler confidence (consecutive: {self.consecutive_epistemic_replications + 1}/{max_consecutive_replications})"
                )
            else:
                return (
                    EpistemicAction.NONE,
                    f"High uncertainty ({uncertainty:.2f} bits) but insufficient budget "
                    f"({budget_plates_remaining:.2f} plates < {replication_cost_plates:.2f} needed)"
                )
        else:
            # Low uncertainty: safe to expand
            if budget_plates_remaining >= 0.25:  # Minimum budget for expansion
                return (
                    EpistemicAction.EXPAND,
                    f"Low calibration uncertainty ({uncertainty:.2f} bits ≤ {uncertainty_threshold:.1f} threshold), "
                    f"expand exploration"
                )
            else:
                return (
                    EpistemicAction.NONE,
                    f"Low uncertainty but insufficient budget ({budget_plates_remaining:.2f} plates)"
                )

    def create_epistemic_proposal(
        self,
        action,
        previous_proposal,
        previous_observation_dict,
        capabilities: dict,
        remaining_wells: int
    ):
        """Create proposal based on epistemic action.

        REPLICATE: Duplicate previous proposal exactly (double wells), shrink to fit budget
        EXPAND: Propose next science experiment (normal policy path with real observation)

        Args:
            action: Epistemic action to execute
            previous_proposal: Proposal from previous cycle
            previous_observation_dict: Observation dict from previous cycle (for EXPAND)
            capabilities: World capabilities
            remaining_wells: Actual remaining well budget

        Returns:
            New proposal for epistemic action, budget-constrained

        Raises:
            RuntimeError: If budget insufficient for minimum viable proposal
        """
        from ..epistemic_actions import EpistemicAction
        from ..accountability import make_replicate_proposal, shrink_proposal_to_budget

        if action == EpistemicAction.REPLICATE:
            # Replicate previous proposal exactly
            # Increment consecutive replication counter
            self.consecutive_epistemic_replications += 1

            # Create replicate proposal (may exceed budget)
            replicate_proposal = make_replicate_proposal(previous_proposal)

            # Shrink to fit remaining budget
            shrunk_proposal = shrink_proposal_to_budget(replicate_proposal, remaining_wells)

            if shrunk_proposal is None:
                raise RuntimeError(
                    f"ABORT: Cannot create viable replicate proposal with {remaining_wells} wells remaining. "
                    f"Minimum viable: 3 wells. Requested: {len(replicate_proposal.wells)} wells."
                )

            return shrunk_proposal

        elif action == EpistemicAction.EXPAND:
            # Reset consecutive replication counter
            self.consecutive_epistemic_replications = 0
            # Propose next science experiment (normal policy path)
            # CRITICAL: Pass real previous_observation to maintain determinism
            return self.propose_next_experiment(capabilities, previous_observation=previous_observation_dict)

        else:
            raise ValueError(f"Cannot create proposal for action {action}")
