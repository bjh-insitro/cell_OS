"""
Beam Search Implementation

Main beam search algorithm for finding optimal action sequences
under hard constraints with governance integration.

v0.6.0: Added best-so-far preservation (Issue #9)
- Preserves the best node across all steps to avoid losing good paths
- Fixes issue where aggressive death pruning eliminates all paths
"""

from typing import List, Optional, Tuple, Dict, Any
import numpy as np

from ..episode import Action, Policy, EpisodeReceipt, EpisodeRunner
from ..biological_virtual import BiologicalVirtualMachine
from ...epistemic_agent.governance import (
    Blocker,
    GovernanceAction,
    GovernanceDecision,
    GovernanceInputs,
    GovernanceThresholds,
    decide_governance,
)
from .types import BeamNode, BeamSearchResult, PrefixRolloutResult
from .runner import Phase5EpisodeRunner
from .action_bias import ActionIntent, classify_action_intent, compute_action_bias

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
        from ..masked_compound_phase5 import PHASE5_LIBRARY

        if phase5_compound is None:
            phase5_compound = PHASE5_LIBRARY[compound_id]

        compound = phase5_compound

        # Initialize beam with root node
        beam = [BeamNode(t_step=0, schedule=[])]

        # v0.6.0: Best-so-far preservation (Issue #9)
        # Track the best node seen so far to avoid losing all good paths
        best_so_far: Optional[BeamNode] = None

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

            # v0.6.0: Update best-so-far from current beam
            if beam:
                current_best = max(beam, key=lambda n: n.heuristic_score)
                if best_so_far is None or current_best.heuristic_score > best_so_far.heuristic_score:
                    best_so_far = current_best

            # v0.6.0: If beam is empty, inject best-so-far to continue search
            if not beam:
                if best_so_far is not None:
                    # Extend best-so-far with no-op action to continue search
                    beam = [best_so_far]
                    # Note: This may repeat the same node, but allows search to continue
                else:
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
        # Ensure node state is populated before expansion
        if not self._ensure_node_state_populated(node):
            return []

        successors = []

        # Generate CONTINUE successors (exploration actions)
        continue_successors = self._generate_continue_successors(node)
        successors.extend(continue_successors)

        # Generate terminal successors (COMMIT/NO_DETECTION if governance allows)
        terminal_successors = self._generate_terminal_successors(node)
        successors.extend(terminal_successors)

        return successors

    def _ensure_node_state_populated(self, node: BeamNode) -> bool:
        """Ensure node belief state is populated before expansion.

        Returns:
            True if state is valid, False if expansion should be aborted
        """
        if node.t_step == 0:
            return True  # Root node has no state yet

        # Check if state needs population
        if node.calibrated_confidence_current > 0.0 and node.predicted_axis_current != "UNKNOWN":
            return True  # Already populated

        # Compute and populate state
        try:
            prefix_current = self.runner.rollout_prefix(node.schedule)
            self._populate_node_from_prefix(node, prefix_current)
            return True
        except Exception as e:
            if getattr(self, 'debug_commit_decisions', False):
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to compute prefix_current for node at t={node.t_step}: {e}", exc_info=True)
            return False

    def _generate_continue_successors(self, node: BeamNode) -> List[BeamNode]:
        """Generate CONTINUE successors by trying all legal action combinations."""
        successors = []
        has_dosed = any(a.dose_fraction > 0 for a in node.schedule)

        # Compute action bias from governance blockers (if in NO_COMMIT state)
        action_bias = self._compute_action_bias(node, has_dosed)

        for dose_level in self.dose_levels:
            for washout in [False, True]:
                for feed in [False, True]:
                    # Skip illegal actions
                    if washout and not has_dosed:
                        continue

                    action = Action(dose_fraction=dose_level, washout=washout, feed=feed)
                    successor = self._try_create_continue_node(
                        node, action, has_dosed, action_bias
                    )
                    if successor is not None:
                        successors.append(successor)

        return successors

    def _compute_action_bias(self, node: BeamNode, has_dosed: bool) -> Dict[ActionIntent, float]:
        """Compute action intent biases from governance blockers."""
        if node.t_step == 0:
            return {}

        gov_decision = self._apply_governance_contract(node)
        if not gov_decision or gov_decision.action != GovernanceAction.NO_COMMIT:
            return {}

        evidence_strength = node.posterior_top_prob_current
        return compute_action_bias(gov_decision.blockers, evidence_strength)

    def _try_create_continue_node(
        self,
        node: BeamNode,
        action: Action,
        has_dosed: bool,
        action_bias: Dict[ActionIntent, float]
    ) -> Optional[BeamNode]:
        """Try to create a CONTINUE successor node. Returns None if pruned."""
        new_schedule = node.schedule + [action]
        new_washout = node.washout_count + (1 if action.washout else 0)
        new_feed = node.feed_count + (1 if action.feed else 0)

        # Early pruning: intervention budget
        if new_washout + new_feed > self.max_interventions:
            self.nodes_pruned_interventions += 1
            return None

        # Rollout prefix to get actual observations
        try:
            prefix_result = self.runner.rollout_prefix(new_schedule)
        except Exception as e:
            if getattr(self, 'debug_commit_decisions', False):
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Prefix rollout failed for schedule {new_schedule}: {e}")
            self.nodes_pruned_death += 1
            return None

        # Early pruning: death trajectory
        if prefix_result.viability < (1.0 - self.death_tolerance):
            self.nodes_pruned_death += 1
            return None

        # Compute heuristic score
        heuristic = self._compute_heuristic_score(
            prefix_result, new_washout, new_feed, action, has_dosed, action_bias
        )

        # Create successor node
        successor = BeamNode(
            t_step=node.t_step + 1,
            schedule=new_schedule,
            action_type="CONTINUE",
            is_terminal=False,
            washout_count=new_washout,
            feed_count=new_feed,
            heuristic_score=heuristic,
            commit_utility=None
        )

        self._populate_node_from_prefix(successor, prefix_result)
        return successor

    def _compute_heuristic_score(
        self,
        prefix_result,
        washout_count: int,
        feed_count: int,
        action: Action,
        has_dosed: bool,
        action_bias: Dict[ActionIntent, float]
    ) -> float:
        """Compute exploration heuristic with optional governance bias."""
        viability_bonus = prefix_result.viability
        confidence_bonus = prefix_result.classifier_margin
        ops_penalty = washout_count + feed_count

        heuristic = (
            self.w_mechanism * confidence_bonus +
            self.w_viability * viability_bonus -
            self.w_interventions * ops_penalty
        )

        # Apply governance bias if active
        if action_bias:
            intent = classify_action_intent(action, has_dosed)
            bias_multiplier = action_bias.get(intent, 1.0)
            heuristic *= bias_multiplier

        return heuristic

    def _generate_terminal_successors(self, node: BeamNode) -> List[BeamNode]:
        """Generate terminal successors (COMMIT/NO_DETECTION) if governance allows."""
        if node.t_step == 0:
            return []  # Can't commit at root

        successors = []
        gov_decision = self._apply_governance_contract(node)

        if gov_decision.action == GovernanceAction.COMMIT:
            commit_node = self._create_commit_node(node, gov_decision)
            successors.append(commit_node)
        elif gov_decision.action == GovernanceAction.NO_DETECTION:
            no_det_node = self._create_no_detection_node(node)
            successors.append(no_det_node)
        # else: NO_COMMIT - continue exploring

        return successors

    def _create_commit_node(self, node: BeamNode, gov_decision: GovernanceDecision) -> BeamNode:
        """Create a COMMIT terminal node."""
        elapsed_time_h = node.t_step * self.runner.step_h
        ops_penalty = node.washout_count + node.feed_count
        cal_conf = node.calibrated_confidence_current

        commit_util = self._compute_commit_utility(
            calibrated_conf=cal_conf,
            elapsed_time_h=elapsed_time_h,
            ops_penalty=ops_penalty,
            viability=node.viability_current
        )

        commit_node = BeamNode(
            t_step=node.t_step,
            schedule=node.schedule,
            action_type="COMMIT",
            is_terminal=True,
            washout_count=node.washout_count,
            feed_count=node.feed_count,
            commit_utility=commit_util,
            commit_target=gov_decision.mechanism,
            heuristic_score=0.0
        )

        self._copy_belief_state(commit_node, node)
        self._log_commit_decision(node, commit_util)

        return commit_node

    def _create_no_detection_node(self, node: BeamNode) -> BeamNode:
        """Create a NO_DETECTION terminal node."""
        elapsed_time_h = node.t_step * self.runner.step_h
        ops_penalty = node.washout_count + node.feed_count
        cal_conf = node.calibrated_confidence_current

        no_det_util = self._compute_no_detection_utility(
            calibrated_conf=cal_conf,
            elapsed_time_h=elapsed_time_h,
            ops_penalty=ops_penalty
        )

        no_det_node = BeamNode(
            t_step=node.t_step,
            schedule=node.schedule,
            action_type="NO_DETECTION",
            is_terminal=True,
            washout_count=node.washout_count,
            feed_count=node.feed_count,
            no_detection_utility=no_det_util,
            heuristic_score=0.0
        )

        self._copy_belief_state(no_det_node, node)
        self._log_no_detection_decision(node, no_det_util)

        return no_det_node

    def _copy_belief_state(self, target: BeamNode, source: BeamNode):
        """Copy belief state fields from source to target node."""
        target.viability_current = source.viability_current
        target.actin_fold_current = source.actin_fold_current
        target.confidence_margin_current = source.confidence_margin_current
        target.posterior_top_prob_current = source.posterior_top_prob_current
        target.posterior_margin_current = source.posterior_margin_current
        target.nuisance_frac_current = source.nuisance_frac_current
        target.calibrated_confidence_current = source.calibrated_confidence_current
        target.predicted_axis_current = source.predicted_axis_current
        target.nuisance_mean_shift_mag_current = source.nuisance_mean_shift_mag_current
        target.nuisance_var_inflation_current = source.nuisance_var_inflation_current

    def _log_commit_decision(self, node: BeamNode, commit_util: float):
        """Log forensic details of COMMIT decision."""
        if not getattr(self, 'debug_commit_decisions', False):
            return

        import logging
        logger = logging.getLogger(__name__)
        elapsed_time_h = node.t_step * self.runner.step_h

        logger.info(
            f"COMMIT node created at t={node.t_step} ({elapsed_time_h:.1f}h): "
            f"predicted_axis={node.predicted_axis_current} "
            f"is_concrete_mech=True "
            f"posterior_top_prob={node.posterior_top_prob_current:.3f} "
            f"posterior_margin={node.posterior_margin_current:.3f} "
            f"nuisance_frac={node.nuisance_frac_current:.3f} "
            f"nuisance_mean_shift_mag={node.nuisance_mean_shift_mag_current:.3f} "
            f"nuisance_var_inflation={node.nuisance_var_inflation_current:.3f} "
            f"calibrated_conf={node.calibrated_confidence_current:.3f} "
            f"commit_utility={commit_util:.3f}"
        )

    def _log_no_detection_decision(self, node: BeamNode, no_det_util: float):
        """Log forensic details of NO_DETECTION decision."""
        if not getattr(self, 'debug_commit_decisions', False):
            return

        import logging
        logger = logging.getLogger(__name__)
        elapsed_time_h = node.t_step * self.runner.step_h

        logger.info(
            f"NO_DETECTION node created at t={node.t_step} ({elapsed_time_h:.1f}h): "
            f"predicted_axis={node.predicted_axis_current} "
            f"posterior_top_prob={node.posterior_top_prob_current:.3f} "
            f"nuisance_frac={node.nuisance_frac_current:.3f} "
            f"calibrated_conf={node.calibrated_confidence_current:.3f} "
            f"no_detection_utility={no_det_util:.3f}"
        )

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
