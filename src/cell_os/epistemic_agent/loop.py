"""
Main orchestration loop: the "movie" we want to watch.

This runs cycles of:
1. Agent proposes experiment (with hypothesis/reasoning)
2. World executes and returns observations
3. Agent updates beliefs
4. Log everything for narrative

The logging is crucial - this is how we watch the agent learn.

v0.4.2: Evidence ledgers (evidence.jsonl, decisions.jsonl, diagnostics.jsonl)
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .world import ExperimentalWorld
from .agent.policy_rules import RuleBasedPolicy
from .schemas import Observation, Proposal, WellSpec
from .beliefs.ledger import append_events_jsonl, append_decisions_jsonl, append_noise_diagnostics_jsonl, DecisionEvent
from .exceptions import InvalidDesignError
from .controller_integration import EpistemicIntegration
from .design_quality import DesignQualityChecker
from .observation_aggregator import aggregate_observation
from .episode_summary import (
    EpisodeSummary,
    BudgetSpending,
    EpistemicLearning,
    HealthSacrifices,
    MitigationEvent,
    InstrumentHealthTimeSeries,
)
from .loop_timing import LoopTimer, LoopTimingStats
from .data_engine import DataEngine, ObservationRecord
from ..hardware.safety_constraints import SafetyConstraints
from .automation_readiness import AutomationReadinessTracker


class EpistemicLoop:
    """Main loop for epistemic agency experiments."""

    def __init__(
        self,
        budget: int = 384,
        max_cycles: int = 20,
        log_dir: Optional[Path] = None,
        seed: int = 0,
        strict_quality: bool = True,
        strict_provenance: bool = True,
        gain_aggressiveness: float = 1.0  # >1.0 = overclaim (triggers debt enforcement)
    ):
        self.budget = budget
        self.max_cycles = max_cycles
        self.seed = seed
        self.strict_provenance = strict_provenance

        # Setup logging
        if log_dir is None:
            log_dir = Path("results/epistemic_agent")
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Create run-specific log file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_id = f"run_{timestamp}"
        self.log_file = self.log_dir / f"{self.run_id}.log"
        self.json_file = self.log_dir / f"{self.run_id}.json"

        # v0.4.2: Evidence ledgers
        self.evidence_file = self.log_dir / f"{self.run_id}_evidence.jsonl"
        self.decisions_file = self.log_dir / f"{self.run_id}_decisions.jsonl"
        self.diagnostics_file = self.log_dir / f"{self.run_id}_diagnostics.jsonl"
        self.refusals_file = self.log_dir / f"{self.run_id}_refusals.jsonl"
        self.mitigation_file = self.log_dir / f"{self.run_id}_mitigation.jsonl"
        self.epistemic_file = self.log_dir / f"{self.run_id}_epistemic.jsonl"

        # Initialize world and agent
        self.world = ExperimentalWorld(budget_wells=budget, seed=seed)
        self.agent = RuleBasedPolicy(budget=budget, seed=seed)

        # Apply gain aggressiveness (>1.0 causes overclaiming, triggers debt)
        self.gain_aggressiveness = gain_aggressiveness
        if gain_aggressiveness != 1.0:
            self.agent.beliefs.gain_estimate_multiplier = gain_aggressiveness

        # v0.5.1: Epistemic integration (Task 3 - real epistemic claims)
        self.epistemic = EpistemicIntegration(enable=True)

        # NEW: Design quality checker (scientific heuristics, not physics)
        self.quality_checker = DesignQualityChecker(strict_mode=strict_quality)

        # Run history
        self.history = []
        self.abort_reason = None

        # Mitigation state (pending mitigation consumes next integer cycle)
        self._pending_mitigation = None
        self._last_proposal = None

        # Loop timing (Feala: shrink loop times by orders of magnitude)
        self.loop_timer = LoopTimer()

        # Data engine (Feala: growing dataset as asset)
        data_engine_path = self.log_dir / "data_engine.db"
        self.data_engine = DataEngine(db_path=data_engine_path)

        # Safety constraints (Feala: safety as first-class Pareto constraint)
        self.safety_constraints = SafetyConstraints()

        # Automation readiness tracker (Feala: automate at the right time)
        self.automation_tracker = AutomationReadinessTracker()

        # Epistemic action state (pending epistemic action consumes next integer cycle)
        self._pending_epistemic_action = None

        # Calibration state (pending calibration consumes next integer cycle)
        self._pending_calibration = None

        # Episode summary (aggregated metrics for system-level closure)
        self.episode_summary: Optional[EpisodeSummary] = None
        self.episode_start_time: Optional[str] = None

    def run(self):
        """Run the full experiment loop."""
        self._log_header()

        # Initialize episode summary (system-level closure)
        self.episode_start_time = datetime.now().isoformat()
        self.episode_summary = EpisodeSummary(
            run_id=self.run_id,
            seed=self.seed,
            cycles_completed=0,
            start_time=self.episode_start_time,
            end_time="",  # Set at episode end
        )

        # Track initial calibration state for learning metrics
        initial_calibration_entropy = self.agent.beliefs.calibration_entropy_bits
        initial_noise_rel_width = self.agent.beliefs.noise_rel_width

        # Write contamination warning if enforcement is disabled
        if self.epistemic.controller.is_contaminated:
            contamination_event = {
                "timestamp": datetime.now().isoformat(),
                "contamination_type": self.epistemic.controller.contamination_reason,
                "message": "Epistemic debt enforcement is disabled. This run does not enforce honesty constraints.",
                "severity": "CRITICAL",
            }
            append_noise_diagnostics_jsonl(self.diagnostics_file, [contamination_event])
            self._log("\n" + "="*60)
            self._log("⚠️  CONTAMINATED RUN WARNING")
            self._log("="*60)
            self._log(f"  Reason: {self.epistemic.controller.contamination_reason}")
            self._log("  This run does not enforce epistemic debt constraints.")
            self._log("  Results are not comparable to enforced runs.")
            self._log("="*60 + "\n")

        capabilities = self.world.get_capabilities()
        self._log_capabilities(capabilities)

        for cycle in range(1, self.max_cycles + 1):
            if self.world.budget_remaining <= 0:
                self._log("\n" + "="*60)
                self._log("BUDGET EXHAUSTED")
                self._log("="*60)
                break

            self._log("\n" + "="*60)
            self._log(f"CYCLE {cycle}/{self.max_cycles}")
            self._log("="*60)

            # Start cycle timing (Feala: measure to optimize)
            self.loop_timer.start_cycle(cycle)

            # v0.4.2: Begin cycle for evidence tracking
            # Covenant 7: Snapshot beliefs before cycle for mutation tracking
            # GUARDRAIL: Ensure cycle is integer (prevent temporal provenance violations)
            # NOTE: Do not rely on asserts in optimized mode (-O flag disables them).
            # Primary enforcement is in BeliefState.begin_cycle() which raises TypeError.
            assert isinstance(cycle, int), f"Cycle must be int, got {type(cycle)}: {cycle}"

            beliefs_before = self.agent.beliefs.snapshot()
            self.agent.beliefs.begin_cycle(cycle)

            # EPISTEMIC ACTION: Snapshot uncertainty at START of cycle (before belief update)
            # This is the "before" measurement for epistemic reward calculation
            uncertainty_at_cycle_start = self.agent.beliefs.estimate_calibration_uncertainty()

            # MITIGATION: If pending from previous cycle, execute mitigation instead of science
            # SEMANTIC CONTRACT:
            # - Mitigation consumes a full integer cycle (not a subcycle)
            # - If cycle k is flagged, mitigation executes at cycle k+1
            # - Science resumes at cycle k+2
            # - No floats, no cycle reuse, strict monotonic progression
            if self._pending_mitigation is not None:
                self._execute_mitigation_cycle(cycle, self._pending_mitigation, capabilities)
                self._pending_mitigation = None
                continue  # Mitigation consumed this integer cycle

            # EPISTEMIC ACTION: If pending from previous cycle, execute epistemic action instead of science
            # SEMANTIC CONTRACT (identical to mitigation):
            # - Epistemic action consumes a full integer cycle (not a subcycle)
            # - If cycle k has high uncertainty, epistemic action executes at cycle k+1
            # - Science resumes at cycle k+2
            # - No floats, no cycle reuse, strict monotonic progression
            if self._pending_epistemic_action is not None:
                self._execute_epistemic_cycle(cycle, self._pending_epistemic_action, capabilities)
                self._pending_epistemic_action = None
                continue  # Epistemic action consumed this integer cycle

            # CALIBRATION: If pending from previous cycle, execute calibration instead of science
            # SEMANTIC CONTRACT (identical to mitigation and epistemic):
            # - Calibration consumes a full integer cycle (not a subcycle)
            # - If cycle k has high uncertainty or debt, calibration executes at cycle k+1
            # - Science resumes at cycle k+2
            # - No floats, no cycle reuse, strict monotonic progression
            if self._pending_calibration is not None:
                self._execute_calibration_cycle(cycle, self._pending_calibration, capabilities)
                self._pending_calibration = None
                continue  # Calibration consumed this integer cycle

            # Agent proposes experiment (timed for bottleneck analysis)
            try:
                with self.loop_timer.phase('proposal'):
                    proposal = self.agent.propose_next_experiment(
                        capabilities,
                        previous_observation=self.history[-1] if self.history else None
                    )

                # v0.5.0: Write canonical Decision (no side-channel, no hasattr checks)
                if self.agent.last_decision is not None:
                    append_decisions_jsonl(self.decisions_file, [self.agent.last_decision])

            except RuntimeError as e:
                # Handle abort from policy (e.g., insufficient budget)
                if "ABORT" in str(e):
                    self._log(f"\n⛔ POLICY ABORT: {e}")
                    self.abort_reason = str(e)

                    # v0.5.0: Write canonical Decision (no side-channel, no hasattr checks)
                    if self.agent.last_decision is not None:
                        append_decisions_jsonl(self.decisions_file, [self.agent.last_decision])
                    else:
                            # Fallback: create minimal abort Decision if chooser didn't set one
                            from cell_os.core import Decision, DecisionRationale
                            abort_decision = Decision(
                                decision_id=f"abort-cycle-{cycle}",
                                cycle=cycle,
                                timestamp_utc=Decision.now_utc(),
                                kind="abort",
                                chosen_template=None,
                                chosen_kwargs={"reason": str(e)},
                                rationale=DecisionRationale(
                                    summary=f"Runtime abort: {str(e)}",
                                    rules_fired=("runtime_error",),
                                ),
                                inputs_fingerprint=f"abort_{cycle}",
                            )
                            append_decisions_jsonl(self.decisions_file, [abort_decision])

                    # Save JSON metadata before exiting
                    self._save_json()
                    break
                else:
                    raise

            self._log_proposal(proposal)

            # EPISTEMIC DEBT ENFORCEMENT: Check if action can be afforded
            # This is the forcing function - debt accumulation blocks execution
            template_name = proposal.design_id.split('_')[0]  # Extract template name
            should_refuse, refusal_reason, refusal_context = self.epistemic.should_refuse_action(
                template_name=template_name,
                base_cost_wells=len(proposal.wells),
                budget_remaining=self.world.budget_remaining,
                debt_hard_threshold=2.0,  # Hard threshold: 2 bits of overclaim
                calibration_templates={"baseline", "calibration", "dmso"}
            )

            # Write per-cycle debt diagnostic (always, even if not refused)
            debt_diagnostic = {
                "event_type": "epistemic_debt_status",
                "timestamp": datetime.now().isoformat(),
                "cycle": cycle,
                "debt_bits": refusal_context.get('debt_bits', 0.0),
                "threshold": refusal_context.get('debt_threshold', 2.0),
                "action_proposed": template_name,
                "action_allowed": not should_refuse,
                "action_is_calibration": refusal_context.get('is_calibration', False),
                "base_cost_wells": refusal_context.get('base_cost_wells', 0),
                "inflated_cost_wells": refusal_context.get('inflated_cost_wells', 0),
                "inflation_factor": (refusal_context.get('inflated_cost_wells', 0) / max(1, refusal_context.get('base_cost_wells', 1))),
                "budget_remaining": self.world.budget_remaining,
                "refusal_reason": refusal_reason if should_refuse else None,
                "epistemic_insolvent": self.agent.beliefs.epistemic_insolvent,
                "consecutive_refusals": self.agent.beliefs.consecutive_refusals,
            }
            # Write directly to diagnostics file (plain dict, not EvidenceEvent)
            with open(self.diagnostics_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(debt_diagnostic) + '\n')

            if should_refuse:
                self._log("\n" + "="*60)
                self._log(f"EPISTEMIC DEBT REFUSAL: {refusal_reason}")
                self._log("="*60)
                self._log(f"  Debt accumulated: {refusal_context['debt_bits']:.3f} bits")
                self._log(f"  Base cost: {refusal_context['base_cost_wells']} wells")
                self._log(f"  Inflated cost: {refusal_context['inflated_cost_wells']} wells")
                self._log(f"  Budget remaining: {refusal_context['budget_remaining']} wells")

                # Agent 3 Deadlock Fix: Report all refusal reasons with priority
                if refusal_context.get('is_deadlocked', False):
                    self._log(f"  → EPISTEMIC DEADLOCK: Debt requires calibration but calibration unaffordable")
                    self._log(f"  → Debt: {refusal_context['debt_bits']:.3f} bits > {refusal_context['debt_threshold']:.1f} threshold")
                    self._log(f"  → Budget remaining: {refusal_context['budget_remaining']} wells")
                    self._log(f"  → Minimum calibration cost (inflated): ~{int(refusal_context['required_reserve'] * 1.5)} wells")
                    self._log(f"  → TERMINAL: Agent cannot recover")
                elif refusal_context.get('blocked_by_threshold', False):
                    self._log(f"  → Debt threshold ({refusal_context['debt_threshold']:.1f} bits) exceeded for non-calibration action")
                elif refusal_context.get('blocked_by_reserve', False):
                    self._log(f"  → Budget reserve violation: would leave only {refusal_context['budget_after_action']} wells")
                    self._log(f"  → Minimum {refusal_context['required_reserve']} wells required for epistemic recovery (deadlock prevention)")
                elif refusal_context.get('blocked_by_cost', False):
                    self._log(f"  → Cost inflation from debt exceeds budget")

                # Write refusal to permanent log
                from .beliefs.ledger import RefusalEvent, append_refusals_jsonl
                refusal_event = RefusalEvent(
                    cycle=cycle,
                    timestamp=datetime.now().isoformat(),
                    refusal_reason=refusal_reason,
                    proposed_template=template_name,
                    proposed_hypothesis=proposal.hypothesis,
                    proposed_wells=len(proposal.wells),
                    design_id=proposal.design_id,
                    **refusal_context
                )
                append_refusals_jsonl(self.refusals_file, [refusal_event])

                # Update agent beliefs with refusal (agent learns "I am insolvent")
                self.agent.beliefs.record_refusal(
                    refusal_reason=refusal_reason,
                    debt_bits=refusal_context['debt_bits'],
                    debt_threshold=refusal_context['debt_threshold']
                )

                self._log(f"\n  Refusal logged to: {self.refusals_file.name}")

                # Agent 3 Deadlock Fix: Terminal abort on deadlock
                if refusal_context.get('is_deadlocked', False):
                    self._log(f"\n{'='*60}")
                    self._log(f"EPISTEMIC DEADLOCK ABORT")
                    self._log(f"{'='*60}")
                    self._log(f"Agent cannot recover from debt without calibration,")
                    self._log(f"but calibration is unaffordable. Terminal failure.")
                    self._log(f"\nFinal state:")
                    self._log(f"  Debt: {refusal_context['debt_bits']:.3f} bits")
                    self._log(f"  Budget: {refusal_context['budget_remaining']} wells")
                    self._log(f"  Cycles completed: {cycle}")
                    break  # Terminal abort

                self._log(f"  Agent marked as epistemically insolvent (consecutive refusals: {self.agent.beliefs.consecutive_refusals})")
                self._log(f"  System must propose calibration to restore solvency")

                # Skip this cycle - agent must propose calibration next
                continue

            # v0.5.1: Epistemic claim (Task 3 - real epistemic claims)
            # Estimate expected gain BEFORE execution
            prior_entropy = self.agent.beliefs.entropy
            modalities = tuple(set(w.assay for w in proposal.wells))  # Deduplicate assays
            expected_gain = self.agent.beliefs.estimate_expected_gain(
                template_name=template_name,
                n_wells=len(proposal.wells),
                modalities=modalities
            )

            # Claim design with expected gain
            claim_id = self.epistemic.claim_design(
                design_id=proposal.design_id,
                cycle=cycle,
                expected_gain_bits=expected_gain,
                hypothesis=proposal.hypothesis,
                modalities=modalities,
                wells_count=len(proposal.wells),
                estimated_cost_usd=len(proposal.wells) * 5.0,  # Rough estimate: $5/well
                prior_modalities=None  # TODO: Track cumulative modalities
            )

            self._log(f"  Expected gain: {expected_gain:.3f} bits (prior entropy: {prior_entropy:.2f})")

            # NEW: Check design quality BEFORE execution
            quality_report = self.quality_checker.check(proposal)

            self._log(f"\nDesign Quality Check:")
            self._log(f"  {quality_report.summary()}")
            if quality_report.has_warnings:
                for warning in quality_report.warnings:
                    self._log(f"    {warning}")

            # NEW: Policy decision - refuse if quality blocks
            if quality_report.blocks_execution:
                self._log("\n" + "="*60)
                self._log("DESIGN REJECTED: High-severity quality issues")
                self._log("="*60)

                # Log refusal reason
                self._log_refusal(proposal, quality_report, cycle)

                # Agent could revise here, but for now we skip cycle
                continue  # Skip to next cycle

            # World executes (no validation - world doesn't care about quality)
            start_time = time.time()
            try:
                # World execution (timed for bottleneck analysis)
                with self.loop_timer.phase('execution'):
                    raw_results = self.world.run_experiment(proposal)

                # Observation aggregation (timed separately)
                with self.loop_timer.phase('observation'):
                    observation = aggregate_observation(
                        proposal=proposal,
                        raw_results=raw_results,
                        budget_remaining=self.world.budget_remaining,
                        strategy="default_per_channel"
                    )

                elapsed = time.time() - start_time

                self._log_observation(observation, elapsed)

                # Safety constraint check (Feala: safety as first-class constraint)
                # Estimate death fraction from viability data
                min_viability = min((c.mean for c in observation.conditions), default=1.0)
                death_fraction = max(0.0, 1.0 - min_viability)

                hard_violations = self.safety_constraints.check_hard_constraints(
                    death_fraction=death_fraction,
                    viability=min_viability
                )
                if hard_violations:
                    self._log(f"\n  ⚠️  SAFETY VIOLATIONS:")
                    for v in hard_violations:
                        self._log(f"    [{v.level.value.upper()}] {v.description}")

                soft_penalty, soft_violations = self.safety_constraints.compute_soft_penalty(
                    death_fraction=death_fraction,
                    viability=min_viability
                )
                if soft_penalty > 0:
                    self._log(f"  📊 Safety penalty: {soft_penalty:.2f} (margin: {self.safety_constraints.safety_margin(death_fraction):.1%})")

                # CYCLE 0 INTEGRATION: Instrument shape learning from calibration plate
                # Check if this was a Cycle 0 calibration run
                if self.agent.last_decision is not None:
                    last_rationale = self.agent.last_decision.rationale
                    last_kwargs = self.agent.last_decision.chosen_kwargs

                    # Check if this was instrument shape learning
                    is_cycle0 = (last_kwargs and last_kwargs.get("purpose") == "instrument_shape_learning")

                    # Alternative check: look at selected_candidate in decision event
                    if not is_cycle0 and hasattr(self.agent.chooser, 'last_decision_event'):
                        dec_ev = self.agent.chooser.last_decision_event
                        if dec_ev and isinstance(dec_ev.selected_candidate, dict):
                            is_cycle0 = dec_ev.selected_candidate.get("purpose") == "instrument_shape_learning"

                    if is_cycle0:
                        self._log("\n" + "="*60)
                        self._log("CYCLE 0: INSTRUMENT SHAPE LEARNING")
                        self._log("="*60)

                        # Compute instrument shape summary from observation
                        from .instrument_shape import compute_instrument_shape_summary
                        from .calibration_constants import CYCLE0_PLATE_ID

                        try:
                            shape_summary = compute_instrument_shape_summary(
                                observation=observation,
                                plate_id=CYCLE0_PLATE_ID
                            )

                            self._log(f"\nInstrument Shape Summary:")
                            self._log(f"  Noise sigma: {shape_summary.noise_sigma:.4f}")
                            self._log(f"  Edge effect: {shape_summary.edge_effect_strength:.4f}")
                            self._log(f"  Spatial residual: {shape_summary.spatial_residual_metric:.4f}")
                            self._log(f"  Replicate precision: {shape_summary.replicate_precision_score:.4f}")
                            self._log(f"  Channel coupling: {shape_summary.channel_coupling_score:.4f}")
                            self._log(f"\n  Gate Status: {'✓ PASS' if shape_summary.noise_gate_pass else '✗ FAIL'}")

                            if shape_summary.failed_checks:
                                self._log(f"  Failed checks: {', '.join(shape_summary.failed_checks)}")

                            # Update beliefs with instrument shape (emits events 2 & 3)
                            self.agent.beliefs.update_from_instrument_shape(shape_summary, cycle=cycle)

                            if shape_summary.noise_gate_pass:
                                self._log(f"\n  🎯 NOISE GATE EARNED via instrument shape learning")
                            else:
                                self._log(f"\n  ⚠️  Noise gate NOT earned - must recalibrate")

                        except Exception as e:
                            self._log(f"\n  ⚠️  Error computing instrument shape: {e}")
                            import traceback
                            self._log(traceback.format_exc())

                # Agent updates beliefs (normal pathway, timed for bottleneck analysis)
                with self.loop_timer.phase('belief_update'):
                    self.agent.update_from_observation(observation)

                # EPISTEMIC ACTION: Snapshot uncertainty AFTER belief update
                # This is the post-update uncertainty for epistemic action decision
                uncertainty_post_update = self.agent.beliefs.estimate_calibration_uncertainty()

                # v0.4.2: Extract evidence and diagnostics from beliefs
                events = self.agent.beliefs.end_cycle()
                diagnostics = self.agent.last_diagnostics or []

                # Covenant 7: Assert no undocumented mutations (if strict_provenance enabled)
                if self.strict_provenance:
                    beliefs_after = self.agent.beliefs.snapshot()
                    self.agent.beliefs.assert_no_undocumented_mutation(
                        beliefs_before, beliefs_after, cycle=cycle
                    )

                # v0.5.1: Epistemic resolution (Task 3 - real epistemic claims)
                # Measure actual gain AFTER observation
                posterior_entropy = self.agent.beliefs.entropy
                realized_gain = prior_entropy - posterior_entropy

                # Create dummy posteriors for resolution (Phase 1: entropy-only)
                # TODO (Task 6): Replace with real MechanismPosterior objects
                class DummyPosterior:
                    def __init__(self, entropy_val):
                        self.entropy = entropy_val

                # Resolve claim and track debt
                resolution = self.epistemic.resolve_design(
                    claim_id=claim_id,
                    prior_posterior=DummyPosterior(prior_entropy),
                    posterior=DummyPosterior(posterior_entropy)
                )

                self._log(
                    f"  Realized gain: {realized_gain:.3f} bits "
                    f"(posterior entropy: {posterior_entropy:.2f}), "
                    f"debt_increment: {resolution['debt_increment']:.3f}, "
                    f"total_debt: {resolution['total_debt']:.3f}"
                )

                # Compute debt repayment for calibration actions
                is_calibration = template_name in {"baseline", "calibration", "dmso"}
                if is_calibration and resolution['total_debt'] > 0:
                    # Measure noise improvement (if any)
                    noise_rel_width_after = self.agent.beliefs.noise_rel_width
                    noise_rel_width_before = beliefs_before.get("noise_rel_width")

                    noise_improvement = None
                    if noise_rel_width_before is not None and noise_rel_width_after is not None:
                        # Improvement = reduction in uncertainty
                        noise_improvement = max(0.0, noise_rel_width_before - noise_rel_width_after)

                    # Compute and apply repayment
                    repayment = self.epistemic.compute_repayment(
                        action_id=claim_id,
                        action_type=template_name,
                        is_calibration=True,
                        noise_improvement=noise_improvement
                    )

                    if repayment > 0:
                        self._log(f"  Debt repayment: {repayment:.3f} bits earned from calibration")

                # Update agent's knowledge of current debt (after repayment)
                current_debt = self.epistemic.controller.get_total_debt()
                self.agent.beliefs.update_debt_level(current_debt)

                # Record that action executed successfully (may clear insolvency)
                self.agent.beliefs.record_action_executed(was_calibration=is_calibration)

                # Write to ledgers
                if events:
                    append_events_jsonl(self.evidence_file, events)
                if diagnostics:
                    append_noise_diagnostics_jsonl(self.diagnostics_file, diagnostics)

                # Save to history
                self.history.append({
                    'cycle': cycle,
                    'proposal': {
                        'design_id': proposal.design_id,
                        'hypothesis': proposal.hypothesis,
                        'n_wells': len(proposal.wells),
                    },
                    'observation': {
                        'design_id': observation.design_id,
                        'n_conditions': len(observation.conditions),
                        'wells_spent': observation.wells_spent,
                        'budget_remaining': observation.budget_remaining,
                        'qc_flags': observation.qc_flags,
                    },
                    'elapsed_seconds': elapsed,
                })

                # Record to data engine (Feala: growing dataset)
                for cond in observation.conditions:
                    obs_record = ObservationRecord(
                        run_id=self.run_id,
                        cycle=cycle,
                        timestamp=datetime.now().isoformat(),
                        cell_line=cond.cell_line,
                        compound=cond.compound,
                        dose_um=cond.dose_uM,
                        time_h=cond.time_h,
                        viability=cond.mean,  # Use mean as primary metric
                        morphology_mean=cond.mean,
                        morphology_std=cond.std,
                        n_wells=cond.n_wells
                    )
                    self.data_engine.record_observation(obs_record)

                # Store last proposal for potential mitigation
                self._last_proposal = proposal

                # MITIGATION: Check for QC flags and set pending mitigation
                # Check if agent has mitigation enabled
                mitigation_enabled = (
                    hasattr(self.agent, 'accountability') and
                    self.agent.accountability is not None and
                    self.agent.accountability.enabled
                )

                if mitigation_enabled:
                    from .mitigation import get_spatial_qc_summary, MitigationContext
                    from .accountability import MitigationAction

                    flagged, morans_i_max, details = get_spatial_qc_summary(observation)

                    if flagged:
                        # Agent chooses mitigation action
                        budget_plates = self.world.budget_remaining / 96.0
                        action, rationale = self.agent.choose_mitigation_action(
                            observation=observation,
                            budget_plates_remaining=budget_plates,
                            previous_proposal=proposal
                        )

                        self._log(f"\n  ⚠️  QC flag detected (Moran's I={morans_i_max:.3f})")
                        self._log(f"  Next cycle will execute {action.value} mitigation")

                        # Set pending if action requires execution
                        if action in {MitigationAction.REPLATE, MitigationAction.REPLICATE}:
                            self._pending_mitigation = MitigationContext(
                                cycle_flagged=cycle,
                                morans_i_before=morans_i_max,
                                action=action,
                                previous_proposal=proposal,
                                rationale=rationale,
                                qc_details_before=details
                            )

                # EPISTEMIC ACTION: Check calibration uncertainty and decide next action
                # This generalizes mitigation from "QC flag → act" to "uncertainty state → decide"
                epistemic_enabled = True  # Could be config flag later
                if epistemic_enabled:
                    from .epistemic_actions import EpistemicAction, EpistemicContext

                    budget_plates = self.world.budget_remaining / 96.0

                    # Convert observation to dict for EXPAND determinism
                    from dataclasses import asdict
                    observation_dict = asdict(observation)

                    action, rationale = self.agent.choose_epistemic_action(
                        observation=observation,
                        budget_plates_remaining=budget_plates,
                        previous_proposal=proposal,
                        previous_observation_dict=observation_dict
                    )

                    self._log(f"\n  📊 Epistemic action check:")
                    self._log(f"     Uncertainty: {uncertainty_post_update:.2f} bits")
                    self._log(f"     Decision: {action.value}")

                    # Set pending if action requires execution
                    if action in {EpistemicAction.REPLICATE, EpistemicAction.EXPAND}:
                        self._pending_epistemic_action = EpistemicContext(
                            cycle_flagged=cycle,
                            uncertainty_before=uncertainty_post_update,  # Store post-update uncertainty that triggered decision
                            action=action,
                            previous_proposal=proposal,
                            previous_observation=observation_dict,
                            rationale=rationale,
                            consecutive_replications=self.agent.consecutive_epistemic_replications
                        )

                        self._log(f"  Next cycle will execute {action.value} epistemic action")
                        self._log(f"  Rationale: {rationale}")

                    elif action == EpistemicAction.CALIBRATE:
                        # Calibration action chosen by EIV decision
                        from .epistemic_actions import EpistemicContext as CalibrationContext

                        self._pending_calibration = CalibrationContext(
                            cycle_flagged=cycle,
                            uncertainty_before=uncertainty_post_update,
                            action=action,
                            previous_proposal=proposal,
                            previous_observation=observation_dict,
                            rationale=rationale,
                            consecutive_replications=0  # Not used for calibration
                        )

                        self._log(f"  Next cycle will execute CALIBRATION")
                        self._log(f"  Rationale: {rationale}")

                # End cycle timing (Feala: track iteration speed)
                wells_this_cycle = observation.wells_spent if observation else 0
                self.loop_timer.end_cycle(wells_processed=wells_this_cycle)

                # Log cycle timing
                ct = self.loop_timer.stats.cycle_timings[-1] if self.loop_timer.stats.cycle_timings else None
                if ct:
                    self._log(f"\n  ⏱️  Cycle timing: {ct.total_cycle_time:.3f}s (bottleneck: {ct.bottleneck})")

                    # Track automation readiness (Feala: automate at the right time)
                    self.automation_tracker.record_execution(
                        process_name="science_cycle",
                        success=True,
                        duration_sec=ct.total_cycle_time
                    )
                    # Track individual phases
                    phase_times = {
                        'proposal': ct.proposal_time,
                        'execution': ct.execution_time,
                        'observation': ct.observation_time,
                        'belief_update': ct.belief_update_time,
                    }
                    for phase, dur in phase_times.items():
                        if dur > 0:
                            self.automation_tracker.record_execution(
                                process_name=f"phase_{phase}",
                                success=True,
                                duration_sec=dur
                            )

                # Save incremental JSON
                self._save_json()

            except Exception as e:
                self._log(f"\n❌ ERROR: {e}")
                self.abort_reason = f"Exception: {e}"
                break

        # Finalize episode summary (system-level closure)
        self._finalize_episode_summary(initial_calibration_entropy, initial_noise_rel_width)

        # Set bits learned for timing stats (Feala: bits/hour metric)
        if self.episode_summary:
            self.loop_timer.stats.set_bits_learned(
                self.episode_summary.learning.total_gain_bits
            )

        # Log timing summary (Feala: shrink loop times)
        self._log("\n" + "="*60)
        self._log("LOOP TIMING ANALYSIS (Feala Metrics)")
        self._log("="*60)
        self._log(self.loop_timer.stats.format_summary())

        # Write timing to file
        timing_file = self.log_dir / f"{self.run_id}_timing.json"
        try:
            with open(timing_file, 'w') as f:
                json.dump({
                    'summary': self.loop_timer.stats.summary(),
                    'cycles': [ct.to_dict() for ct in self.loop_timer.stats.cycle_timings]
                }, f, indent=2)
        except Exception:
            pass  # Don't fail on timing write

        self._log_summary()
        self._update_runs_manifest()

    def _update_runs_manifest(self) -> None:
        """
        Append/update this run in runs_manifest.json for UI discovery.

        Writes atomically and dedupes by run_id.
        """
        manifest_path = self.log_dir / "runs_manifest.json"

        # Load existing
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text())
            except Exception:
                manifest = {"runs": []}
        else:
            manifest = {"runs": []}

        runs = manifest.get("runs", [])
        by_id = {r.get("run_id"): r for r in runs if isinstance(r, dict) and r.get("run_id")}

        # Parse timestamp from run_id (format: run_YYYYMMDD_HHMMSS)
        ts = None
        try:
            raw = self.run_id.replace("run_", "")
            dt = datetime.strptime(raw, "%Y%m%d_%H%M%S").replace(tzinfo=timezone.utc)
            ts = dt.isoformat()
        except Exception:
            ts = datetime.now(timezone.utc).isoformat()

        record = {
            "run_id": self.run_id,
            "timestamp": ts,
            "budget": getattr(self, "budget", None) or getattr(self, "budget_wells", None),
            "max_cycles": self.max_cycles,
            "cycles_completed": self.cycle if hasattr(self, 'cycle') else 0,
            "seed": self.seed,
        }

        by_id[self.run_id] = record
        manifest["runs"] = list(by_id.values())

        # Sort by timestamp
        def _key(r):
            return r.get("timestamp") or ""
        manifest["runs"].sort(key=_key)

        # Atomic write
        tmp = manifest_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(manifest, indent=2))
        tmp.replace(manifest_path)

    def _log(self, message: str):
        """Write to both stdout and log file."""
        print(message)
        with open(self.log_file, 'a') as f:
            f.write(message + '\n')

    def _log_header(self):
        """Log session header."""
        self._log("="*60)
        self._log("EPISTEMIC AGENCY - AUTONOMOUS SCIENTIST")
        self._log("="*60)
        self._log(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self._log(f"Budget: {self.budget} wells")
        self._log(f"Max cycles: {self.max_cycles}")
        self._log(f"Seed: {self.seed}")
        self._log(f"Log file: {self.log_file}")

        # Log data engine stats (Feala: prior knowledge from growing dataset)
        de_stats = self.data_engine.get_stats()
        if de_stats['total_observations'] > 0:
            self._log(f"\n" + "-"*60)
            self._log("DATA ENGINE (Historical Knowledge)")
            self._log("-"*60)
            self._log(f"Prior observations: {de_stats['total_observations']}")
            self._log(f"Prior runs: {de_stats['unique_runs']}")
            self._log(f"Compounds with data: {de_stats['unique_compounds']}")
            self._log(f"Compounds with mechanism: {de_stats['compounds_with_mechanism']}")

    def _log_capabilities(self, cap: dict):
        """Log what the agent knows at t=0."""
        self._log("\n" + "-"*60)
        self._log("STARTING KNOWLEDGE (What Agent Knows)")
        self._log("-"*60)
        self._log(f"Cell lines: {', '.join(cap['cell_lines'])}")
        self._log(f"Compounds: {len(cap['compounds'])} available")
        self._log(f"  {', '.join(cap['compounds'][:5])}...")
        self._log(f"Assays: {', '.join(cap['assays'])}")
        self._log(f"Dose range: {cap['dose_range_uM']} µM")
        self._log(f"Time range: {cap['time_range_h']} hours")
        self._log(f"Position tags: {', '.join(cap['position_tags'])}")

        self._log("\n" + "-"*60)
        self._log("AGENT DOES NOT KNOW (Must Discover)")
        self._log("-"*60)
        self._log("- IC50 values for any compound")
        self._log("- That mid-dose is more informative than high-dose")
        self._log("- That edge effects exist (~12% signal reduction)")
        self._log("- That death signatures converge at high dose")
        self._log("- That 12h is the 'mechanism window'")
        self._log("- That stress classes are separable in morphology space")

    def _log_proposal(self, proposal):
        """Log agent's proposal with reasoning."""
        self._log(f"\n📋 PROPOSAL: {proposal.design_id}")
        self._log(f"Hypothesis: {proposal.hypothesis}")
        self._log(f"Wells requested: {len(proposal.wells)}")
        self._log(f"Budget remaining: {self.world.budget_remaining}")

        # Show well breakdown
        from collections import Counter
        compounds = Counter(w.compound for w in proposal.wells)
        doses = Counter(w.dose_uM for w in proposal.wells)
        times = Counter(w.time_h for w in proposal.wells)
        positions = Counter(w.position_tag for w in proposal.wells)

        self._log(f"  Compounds: {dict(compounds)}")
        self._log(f"  Doses: {dict(doses)}")
        self._log(f"  Times: {dict(times)}")
        self._log(f"  Positions: {dict(positions)}")

    def _log_observation(self, obs: Observation, elapsed: float):
        """Log world's response."""
        self._log(f"\n🔬 OBSERVATION: {obs.design_id}")
        self._log(f"Execution time: {elapsed:.2f}s")
        self._log(f"Conditions tested: {len(obs.conditions)}")
        self._log(f"Wells spent: {obs.wells_spent}")
        self._log(f"Budget remaining: {obs.budget_remaining}")

        # Show summary statistics
        self._log("\n  Condition Summaries:")
        for cond in obs.conditions:
            self._log(
                f"    {cond} → "
                f"mean={cond.mean:.3f}, std={cond.std:.3f}, "
                f"n={cond.n_wells}, CV={cond.cv:.1%}"
            )

        # QC flags
        if obs.qc_flags:
            self._log("\n  ⚠️  QC Flags:")
            for flag in obs.qc_flags:
                self._log(f"    • {flag}")

    def _log_summary(self):
        """Log final summary."""
        self._log("\n" + "="*60)
        self._log("SUMMARY")
        self._log("="*60)
        self._log(f"Cycles completed: {len(self.history)}")
        self._log(f"Total wells used: {self.budget - self.world.budget_remaining}")
        self._log(f"Budget remaining: {self.world.budget_remaining}")

        if self.abort_reason:
            self._log(f"\n⛔ Run aborted: {self.abort_reason}")

        # What did the agent learn? (v0.4.2: use BeliefState)
        beliefs = self.agent.beliefs
        self._log("\n" + "-"*60)
        self._log("AGENT BELIEFS (What It Learned)")
        self._log("-"*60)
        self._log(f"Noise gate earned: {beliefs.noise_sigma_stable}")
        if beliefs.noise_sigma_hat is not None:
            self._log(f"  Pooled sigma: {beliefs.noise_sigma_hat:.4f} (df={beliefs.noise_df_total})")
            if beliefs.noise_rel_width is not None:
                self._log(f"  Rel CI width: {beliefs.noise_rel_width:.4f}")
            if beliefs.noise_drift_metric is not None:
                self._log(f"  Drift metric: {beliefs.noise_drift_metric:.4f}")
        self._log(f"Edge effects confident: {beliefs.edge_effect_confident} (tests={beliefs.edge_tests_run})")
        self._log(f"Dose curvature seen: {beliefs.dose_curvature_seen}")
        self._log(f"Time dependence seen: {beliefs.time_dependence_seen}")
        self._log(f"Compounds tested: {len(beliefs.tested_compounds)}")

        # Success metrics
        self._log("\n" + "-"*60)
        self._log("SUCCESS METRICS (v0.4.2 Pay-for-Calibration)")
        self._log("-"*60)
        self._log(f"[{'✓' if beliefs.noise_sigma_stable else ' '}] Noise gate: rel_width ≤ 0.25")
        self._log(f"[{'✓' if beliefs.edge_effect_confident else ' '}] Edge effects: Detected with confidence")
        self._log(f"[{'✓' if len(beliefs.tested_compounds) >= 2 else ' '}] Exploration: Tested ≥2 compounds")
        self._log(f"[{'✓' if self.world.budget_remaining > 0 else ' '}] Efficiency: Budget remaining")

        # Episode summary (system-level closure)
        if self.episode_summary is not None:
            self._log("\n" + self.episode_summary.summary_text())

        # Data engine summary (Feala: growing dataset asset)
        de_stats = self.data_engine.get_stats()
        self._log("\n" + "-"*60)
        self._log("DATA ENGINE (Accumulated Knowledge)")
        self._log("-"*60)
        self._log(f"Total observations: {de_stats['total_observations']}")
        self._log(f"Total runs: {de_stats['unique_runs']}")
        self._log(f"Compounds tested: {de_stats['unique_compounds']}")
        self._log(f"Compounds with mechanism: {de_stats['compounds_with_mechanism']}")
        self._log(f"Database: {self.data_engine.db_path}")

        # Automation readiness summary (Feala: automate at the right time)
        auto_summary = self.automation_tracker.summary()
        if auto_summary['total_processes'] > 0:
            self._log("\n" + "-"*60)
            self._log("AUTOMATION READINESS (Process Maturity)")
            self._log("-"*60)
            self._log(f"Processes tracked: {auto_summary['total_processes']}")
            self._log(f"Mean readiness: {auto_summary['mean_readiness']:.1%}")
            self._log(f"Ready for automation: {auto_summary['ready_for_automation']}")
            for name, score in self.automation_tracker.get_all_scores().items():
                level = score.recommended_level.value
                self._log(f"  {name}: {score.overall_score:.1%} → {level}")

        self._log(f"\nFull log: {self.log_file}")
        self._log(f"JSON data: {self.json_file}")
        self._log(f"Evidence: {self.evidence_file}")
        self._log(f"Decisions: {self.decisions_file}")
        self._log(f"Diagnostics: {self.diagnostics_file}")

    def _log_refusal(self, proposal: Proposal, quality_report, cycle: int):
        """Log design refusal with full provenance."""
        refusal = {
            'timestamp': datetime.now().isoformat(),
            'cycle': cycle,
            'design_id': proposal.design_id,
            'hypothesis': proposal.hypothesis,
            'quality_score': quality_report.score,
            'warnings': [
                {
                    'category': w.category,
                    'severity': w.severity,
                    'message': w.message,
                    'details': w.details
                }
                for w in quality_report.warnings
            ]
        }

        # Write to refusals log
        with open(self.refusals_file, 'a') as f:
            f.write(json.dumps(refusal) + '\n')

    def _save_json(self):
        """Save history to JSON for analysis.

        v0.4.2: Add beliefs snapshot, paths dict, and integrity checks.
        """
        # Integrity checks: verify evidence files exist if they should
        integrity_warnings = []
        if len(self.history) > 0:
            if not self.evidence_file.exists():
                integrity_warnings.append(f"Missing evidence file: {self.evidence_file.name}")
            if not self.diagnostics_file.exists():
                integrity_warnings.append(f"Missing diagnostics file: {self.diagnostics_file.name}")
            if not self.decisions_file.exists():
                integrity_warnings.append(f"Missing decisions file: {self.decisions_file.name}")

        # Build output
        output = {
            'run_id': self.run_id,
            'budget': self.budget,
            'max_cycles': self.max_cycles,
            'seed': self.seed,
            'cycles_completed': len(self.history),
            'abort_reason': self.abort_reason,
            'history': self.history,
            'beliefs_final': self.agent.beliefs.to_dict(),
            'paths': {
                'log': str(self.log_file.name),
                'json': str(self.json_file.name),
                'evidence': str(self.evidence_file.name),
                'decisions': str(self.decisions_file.name),
                'diagnostics': str(self.diagnostics_file.name),
            },
            'intended_run_context': self.world.get_run_context_dict(),  # v6: batch effect provenance (not yet authoritative)
        }

        if integrity_warnings:
            output['integrity_warnings'] = integrity_warnings

        with open(self.json_file, 'w') as f:
            json.dump(output, f, indent=2)

    def _execute_mitigation_cycle(self, cycle: int, context, capabilities: dict):
        """Execute mitigation using THIS integer cycle number.
        
        CRITICAL: Beliefs already called begin_cycle(cycle) in main loop.
        This method ingests observation at the same cycle.
        
        Args:
            cycle: Integer cycle number (mitigation consumes this cycle)
            context: MitigationContext with action, morans_i_before, etc.
            capabilities: World capabilities
        """
        # Assert temporal ordering
        assert context.cycle_flagged < cycle, (
            f"Mitigation cycle {cycle} must be after flagged cycle {context.cycle_flagged}"
        )
        
        self._log(f"\n{'='*60}")
        self._log(f"MITIGATION CYCLE {cycle}")
        self._log(f"{'='*60}")
        self._log(f"  Triggered by: Cycle {context.cycle_flagged} QC flag")
        self._log(f"  Moran's I before: {context.morans_i_before:.3f}")
        self._log(f"  Action: {context.action.value}")
        self._log(f"  Rationale: {context.rationale}")
        
        # Create mitigation proposal
        proposal = self.agent.create_mitigation_proposal(
            action=context.action,
            previous_proposal=context.previous_proposal,
            capabilities=capabilities
        )
        
        self._log(f"  Wells: {len(proposal.wells)}")
        if proposal.layout_seed:
            self._log(f"  Layout seed: {proposal.layout_seed}")
        
        # Execute
        start_time = time.time()
        raw_results = self.world.run_experiment(proposal)
        observation = aggregate_observation(
            proposal=proposal,
            raw_results=raw_results,
            budget_remaining=self.world.budget_remaining,
            strategy="default_per_channel"
        )
        elapsed = time.time() - start_time
        
        self._log(f"  Execution time: {elapsed:.2f}s")
        self._log(f"  Budget remaining: {self.world.budget_remaining} wells")
        
        # Extract QC after mitigation
        from .mitigation import get_spatial_qc_summary, compute_mitigation_reward
        flagged_after, morans_i_after, details_after = get_spatial_qc_summary(observation)
        
        self._log(f"  Moran's I after: {morans_i_after:.3f}")
        self._log(f"  QC flagged: {flagged_after}")
        
        # Compute reward
        cost = len(proposal.wells) / 96.0
        reward = compute_mitigation_reward(
            action=context.action,
            morans_i_before=context.morans_i_before,
            morans_i_after=morans_i_after,
            flagged_before=True,
            flagged_after=flagged_after,
            cost=cost
        )
        
        self._log(f"  Action cost: {cost:.2f} plates")
        self._log(f"  REWARD: {reward:+.1f} points")
        
        # Update beliefs (cycle already begun in main loop)
        self.agent.update_from_observation(observation)
        
        # End cycle and get events
        events = self.agent.beliefs.end_cycle()
        diagnostics = self.agent.last_diagnostics or []
        
        # Write ledgers
        if events:
            append_events_jsonl(self.evidence_file, events)
        if diagnostics:
            append_noise_diagnostics_jsonl(self.diagnostics_file, diagnostics)
        
        # Log mitigation event
        self._write_mitigation_event({
            "cycle": cycle,
            "cycle_type": "mitigation",
            "flagged_cycle": context.cycle_flagged,
            "seed": self.seed,
            "action": context.action.value,
            "action_cost": cost,
            "budget_plates_remaining": self.world.budget_remaining / 96.0,
            "reward": reward,
            "metrics": {
                "morans_i_before": context.morans_i_before,
                "morans_i_after": morans_i_after,
                "delta_morans_i": context.morans_i_before - morans_i_after,
                "qc_flagged_before": True,
                "qc_flagged_after": flagged_after,
            },
            "rationale": context.rationale,
            "decision_context": {
                "before": context.qc_details_before,
                "after": details_after
            }
        })
        
        # Add to history
        self.history.append({
            'cycle': cycle,
            'proposal': {
                'design_id': proposal.design_id,
                'hypothesis': proposal.hypothesis,
                'n_wells': len(proposal.wells),
            },
            'observation': {
                'design_id': observation.design_id,
                'n_conditions': len(observation.conditions),
                'wells_spent': observation.wells_spent,
                'budget_remaining': observation.budget_remaining,
                'qc_flags': observation.qc_flags,
            },
            'elapsed_seconds': elapsed,
            'is_mitigation': True,
            'reward': reward,
        })
        
        self._save_json()

    def _write_mitigation_event(self, event: dict):
        """Write mitigation event to JSONL."""
        import json
        with open(self.mitigation_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(event) + '\n')

    def _execute_epistemic_cycle(self, cycle: int, context, capabilities: dict):
        """Execute epistemic action using THIS integer cycle number.

        CRITICAL: Beliefs already called begin_cycle(cycle) in main loop.
        This method ingests observation at the same cycle.

        Semantic contract identical to mitigation:
        - Epistemic action consumes a full integer cycle (not a subcycle)
        - If cycle k has high uncertainty, action executes at cycle k+1
        - Science resumes at cycle k+2
        - No floats, no cycle reuse, strict monotonic progression

        Args:
            cycle: Integer cycle number (epistemic action consumes this cycle)
            context: EpistemicContext with action, uncertainty_before, etc.
            capabilities: World capabilities
        """
        # Assert temporal ordering
        assert context.cycle_flagged < cycle, (
            f"Epistemic action cycle {cycle} must be after flagged cycle {context.cycle_flagged}"
        )

        self._log(f"\n{'='*60}")
        self._log(f"EPISTEMIC ACTION CYCLE {cycle}")
        self._log(f"{'='*60}")
        self._log(f"  Triggered by: Cycle {context.cycle_flagged} uncertainty check")
        self._log(f"  Uncertainty before: {context.uncertainty_before:.2f} bits")
        self._log(f"  Action: {context.action.value}")
        self._log(f"  Rationale: {context.rationale}")

        # Create epistemic proposal (budget-aware)
        proposal = self.agent.create_epistemic_proposal(
            action=context.action,
            previous_proposal=context.previous_proposal,
            previous_observation_dict=context.previous_observation,
            capabilities=capabilities,
            remaining_wells=self.world.budget_remaining
        )

        self._log(f"  Wells: {len(proposal.wells)}")

        # Safety check: proposal must respect remaining budget
        assert len(proposal.wells) <= self.world.budget_remaining, (
            f"Proposal budget violation: {len(proposal.wells)} wells requested, "
            f"{self.world.budget_remaining} remaining. This should never happen."
        )

        # Execute
        start_time = time.time()
        raw_results = self.world.run_experiment(proposal)
        observation = aggregate_observation(
            proposal=proposal,
            raw_results=raw_results,
            budget_remaining=self.world.budget_remaining,
            strategy="default_per_channel"
        )
        elapsed = time.time() - start_time

        self._log(f"  Execution time: {elapsed:.2f}s")
        self._log(f"  Budget remaining: {self.world.budget_remaining} wells")

        # Update beliefs from epistemic observation (cycle already begun in main loop)
        self.agent.update_from_observation(observation)

        # Measure uncertainty AFTER epistemic action (post-belief-update)
        # This is u_after for reward calculation
        uncertainty_after = self.agent.beliefs.estimate_calibration_uncertainty()

        self._log(f"  Uncertainty after: {uncertainty_after:.2f} bits")
        self._log(f"  Delta: {context.uncertainty_before - uncertainty_after:+.2f} bits")

        # Compute epistemic reward
        from .epistemic_actions import compute_epistemic_reward
        cost_wells = len(proposal.wells)
        reward = compute_epistemic_reward(
            action=context.action,
            uncertainty_before=context.uncertainty_before,
            uncertainty_after=uncertainty_after,
            cost_wells=cost_wells
        )

        cost_plates = cost_wells / 96.0
        self._log(f"  Action cost: {cost_plates:.2f} plates")
        self._log(f"  EPISTEMIC REWARD: {reward:+.2f} bits/plate")

        # End cycle and get events
        events = self.agent.beliefs.end_cycle()
        diagnostics = self.agent.last_diagnostics or []

        # Write ledgers
        if events:
            append_events_jsonl(self.evidence_file, events)
        if diagnostics:
            append_noise_diagnostics_jsonl(self.diagnostics_file, diagnostics)

        # Detect if cap forced this action
        cap_forced = (
            context.action.value == 'expand' and
            "Max consecutive replications" in context.rationale
        )

        # Log epistemic event (structured for eye-debugging)
        self._write_epistemic_event({
            "cycle": cycle,
            "cycle_type": "epistemic_action",
            "flagged_cycle": context.cycle_flagged,
            "seed": self.seed,
            "action": context.action.value,
            "cost_wells": cost_wells,
            "cost_plates": cost_plates,
            "budget_plates_remaining": self.world.budget_remaining / 96.0,
            "u_before": context.uncertainty_before,
            "u_after": uncertainty_after,
            "delta": context.uncertainty_before - uncertainty_after,
            "reward": reward,
            "cap_forced": cap_forced,
            "consecutive_replications": context.consecutive_replications,
            "rationale": context.rationale,
            # Full metrics for backward compatibility
            "metrics": {
                "uncertainty_before": context.uncertainty_before,
                "uncertainty_after": uncertainty_after,
                "delta_uncertainty": context.uncertainty_before - uncertainty_after,
                "consecutive_replications": context.consecutive_replications,
            },
        })

        # Add to history
        self.history.append({
            'cycle': cycle,
            'proposal': {
                'design_id': proposal.design_id,
                'hypothesis': proposal.hypothesis,
                'n_wells': len(proposal.wells),
            },
            'observation': {
                'design_id': observation.design_id,
                'n_conditions': len(observation.conditions),
                'wells_spent': observation.wells_spent,
                'budget_remaining': observation.budget_remaining,
                'qc_flags': observation.qc_flags,
            },
            'elapsed_seconds': elapsed,
            'is_epistemic_action': True,
            'epistemic_action': context.action.value,
            'reward': reward,
        })

        self._save_json()

    def _write_epistemic_event(self, event: dict):
        """Write epistemic action event to JSONL."""
        import json
        with open(self.epistemic_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(event) + '\n')

    def _finalize_episode_summary(
        self,
        initial_calibration_entropy: float,
        initial_noise_rel_width: Optional[float]
    ):
        """
        Finalize episode summary at end of run.

        Aggregates spending, learning, and sacrifices from episode history.

        Args:
            initial_calibration_entropy: Starting calibration entropy
            initial_noise_rel_width: Starting noise CI width (None if not yet estimated)
        """
        if self.episode_summary is None:
            return  # Safety check

        summary = self.episode_summary
        beliefs = self.agent.beliefs

        # Set end time
        summary.end_time = datetime.now().isoformat()
        summary.cycles_completed = len(self.history)
        summary.abort_reason = self.abort_reason

        # ============ SPENDING ============
        total_wells = self.budget - self.world.budget_remaining
        summary.spending.total_wells = total_wells
        summary.spending.total_plates = total_wells / 96.0

        # Count wells by action type
        calibration_wells = 0
        exploration_wells = 0
        edge_wells = 0
        wells_by_type = {"science": 0, "mitigation": 0, "epistemic": 0}

        for h in self.history:
            n_wells = h['proposal']['n_wells']
            design_id = h['proposal']['design_id']

            # Classify action type
            if h.get('is_mitigation'):
                wells_by_type['mitigation'] += n_wells
            elif h.get('is_epistemic_action'):
                wells_by_type['epistemic'] += n_wells
            else:
                wells_by_type['science'] += n_wells

            # Count calibration vs exploration
            template_name = design_id.split('_')[0].lower()
            if any(cal in template_name for cal in ['baseline', 'calibrate', 'dmso']):
                calibration_wells += n_wells
            else:
                exploration_wells += n_wells

            # Count edge wells (estimate: ~20% of wells are edge wells in typical layout)
            # TODO: More precise tracking from plate layout
            edge_wells += int(n_wells * 0.2)

        summary.spending.wells_by_action_type = wells_by_type
        summary.spending.calibration_wells = calibration_wells
        summary.spending.exploration_wells = exploration_wells
        summary.spending.edge_wells_used = edge_wells

        # ============ LEARNING ============
        # Total epistemic gain (cumulative from controller claims)
        # TODO: Track per-cycle gain and sum (for now, use final - initial entropy as proxy)
        final_entropy = beliefs.calibration_entropy_bits
        summary.learning.total_gain_bits = max(0.0, initial_calibration_entropy - final_entropy)

        # Variance reduction (noise CI width improvement)
        if initial_noise_rel_width is not None and beliefs.noise_rel_width is not None:
            summary.learning.variance_reduction = initial_noise_rel_width - beliefs.noise_rel_width

        # Gates earned/lost
        # Extract from evidence events (look for gate_event:* and gate_loss:*)
        gates_earned = []
        gates_lost = []
        # Read evidence file to extract gate events
        if self.evidence_file.exists():
            try:
                with open(self.evidence_file, 'r') as f:
                    for line in f:
                        if not line.strip():
                            continue
                        try:
                            event = json.loads(line)
                            belief = event.get('belief', '')
                            if belief.startswith('gate_event:'):
                                gate_name = belief.split(':', 1)[1]
                                if gate_name not in gates_earned:
                                    gates_earned.append(gate_name)
                            elif belief.startswith('gate_loss:'):
                                gate_name = belief.split(':', 1)[1]
                                if gate_name not in gates_lost:
                                    gates_lost.append(gate_name)
                        except json.JSONDecodeError:
                            continue
            except Exception:
                pass  # Best effort

        summary.learning.gates_earned = gates_earned
        summary.learning.gates_lost = gates_lost
        summary.learning.final_calibration_entropy = final_entropy
        summary.learning.compounds_tested = len(beliefs.tested_compounds)

        # ============ SACRIFICES ============
        # Health debt (accumulated from QC violations)
        # Extract from health_debt_history
        if beliefs.health_debt_history:
            # Debt accumulated = max debt seen
            summary.sacrifices.health_debt_accumulated = max(beliefs.health_debt_history)
            # Debt repaid = (max - final)
            summary.sacrifices.health_debt_repaid = max(beliefs.health_debt_history) - beliefs.health_debt
        else:
            summary.sacrifices.health_debt_accumulated = 0.0
            summary.sacrifices.health_debt_repaid = 0.0

        # Mitigation timeline (read from mitigation file)
        mitigation_events = []
        if self.mitigation_file.exists():
            try:
                with open(self.mitigation_file, 'r') as f:
                    for line in f:
                        if not line.strip():
                            continue
                        try:
                            event_data = json.loads(line)
                            mitigation_events.append(MitigationEvent(
                                cycle=event_data['cycle'],
                                trigger_cycle=event_data['flagged_cycle'],
                                action=event_data['action'],
                                trigger_reason="spatial_qc_flag",  # Default
                                morans_i_before=event_data.get('metrics', {}).get('morans_i_before'),
                                morans_i_after=event_data.get('metrics', {}).get('morans_i_after'),
                                cost_wells=int(event_data['action_cost'] * 96),
                                reward=event_data.get('reward'),
                                rationale=event_data.get('rationale', ''),
                            ))
                        except (json.JSONDecodeError, KeyError):
                            continue
            except Exception:
                pass

        # Epistemic action events (read from epistemic file)
        if self.epistemic_file.exists():
            try:
                with open(self.epistemic_file, 'r') as f:
                    for line in f:
                        if not line.strip():
                            continue
                        try:
                            event_data = json.loads(line)
                            mitigation_events.append(MitigationEvent(
                                cycle=event_data['cycle'],
                                trigger_cycle=event_data['flagged_cycle'],
                                action=event_data['action'],
                                trigger_reason="high_uncertainty",
                                uncertainty_before=event_data.get('metrics', {}).get('uncertainty_before'),
                                uncertainty_after=event_data.get('metrics', {}).get('uncertainty_after'),
                                cost_wells=event_data.get('action_cost_wells', 0),
                                reward=event_data.get('reward'),
                                rationale=event_data.get('rationale', ''),
                            ))
                        except (json.JSONDecodeError, KeyError):
                            continue
            except Exception:
                pass

        summary.mitigation_timeline = sorted(mitigation_events, key=lambda e: e.cycle)
        summary.sacrifices.mitigation_actions = [
            {
                "cycle": e.cycle,
                "action": e.action,
                "trigger": e.trigger_reason,
                "cost_wells": e.cost_wells,
            }
            for e in mitigation_events
        ]

        # Contract violations (should always be 0)
        summary.sacrifices.contract_violations = 0  # TODO: Track from contract reports

        # Epistemic debt tracking
        # Max debt and refusals
        summary.sacrifices.epistemic_debt_max = beliefs.epistemic_debt_bits
        # Count refusals from refusals file
        if self.refusals_file.exists():
            try:
                with open(self.refusals_file, 'r') as f:
                    summary.sacrifices.epistemic_refusals = sum(1 for line in f if line.strip())
            except Exception:
                summary.sacrifices.epistemic_refusals = 0

        # ============ INSTRUMENT HEALTH TIME SERIES ============
        # Extract QC metrics from observation history
        for h in self.history:
            cycle = h['cycle']
            qc_flags = h['observation'].get('qc_flags', [])

            summary.instrument_health.cycles.append(cycle)

            # Extract metrics from QC flags (best effort parsing)
            # TODO: Store structured QC metrics in observation for better tracking
            morans_i = None
            nuclei_cv = None
            for flag in qc_flags:
                if "Moran's I" in flag:
                    try:
                        # Parse "Moran's I=0.234"
                        morans_i = float(flag.split('=')[1].split()[0].rstrip(',)'))
                    except (IndexError, ValueError):
                        pass
                if "nuclei_cv" in flag.lower():
                    try:
                        nuclei_cv = float(flag.split('=')[1].split()[0].rstrip(',)'))
                    except (IndexError, ValueError):
                        pass

            summary.instrument_health.morans_i_max.append(morans_i if morans_i else 0.0)
            summary.instrument_health.nuclei_cv_max.append(nuclei_cv if nuclei_cv else 0.0)
            summary.instrument_health.segmentation_quality_min.append(1.0)  # Placeholder
            summary.instrument_health.noise_rel_width.append(beliefs.noise_rel_width)

        # ============ COMPUTE AGGREGATE METRICS ============
        summary.compute_aggregate_metrics(total_budget=self.budget)

        # ============ WRITE SUMMARY ============
        summary_file = self.log_dir / f"{self.run_id}_episode_summary.json"
        with open(summary_file, 'w') as f:
            json.dump(summary.to_dict(), f, indent=2)

        self._log(f"\nEpisode summary written to: {summary_file.name}")

    def _execute_calibration_cycle(self, cycle: int, context, capabilities: dict):
        """
        Execute calibration cycle using THIS integer cycle number.

        CRITICAL: Beliefs already called begin_cycle(cycle) in main loop.
        This method generates calibration proposal, executes it, and applies belief updates.

        SEMANTIC CONTRACT (identical to mitigation and epistemic):
        - Calibration consumes a full integer cycle (not a subcycle)
        - If cycle k has high uncertainty/debt, calibration executes at cycle k+1
        - Science resumes at cycle k+2
        - No floats, no cycle reuse, strict monotonic progression

        Args:
            cycle: Integer cycle number (calibration consumes this cycle)
            context: EpistemicContext with action=CALIBRATE, uncertainty_before, rationale
            capabilities: World capabilities

        Returns:
            None (updates beliefs and history in place)
        """
        # Assert temporal ordering
        assert context.cycle_flagged < cycle, (
            f"Calibration cycle {cycle} must be after flagged cycle {context.cycle_flagged}"
        )

        self._log(f"\n{'='*60}")
        self._log(f"CALIBRATION CYCLE {cycle}")
        self._log(f"{'='*60}")
        self._log(f"  Triggered by: Cycle {context.cycle_flagged} decision")
        self._log(f"  Uncertainty before: {context.uncertainty_before:.3f}")
        self._log(f"  Rationale: {context.rationale}")

        # Snapshot state for logging
        uncertainty_before = self.agent.beliefs.calibration_uncertainty
        debt_before = self.agent.beliefs.health_debt

        # Generate calibration proposal (controls only, identity-blind)
        from .calibration_proposal import make_calibration_proposal, get_calibration_statistics
        import random

        # Create seeded RNG for deterministic proposal
        rng = random.Random(self.seed * 1000 + cycle)

        # Extract cell lines from capabilities
        cell_lines = capabilities.get('cell_lines', ['A549', 'HepG2'])

        try:
            proposal = make_calibration_proposal(
                reason=context.rationale,
                cell_lines=cell_lines,
                budget_remaining=self.world.budget_remaining,
                rng=rng
            )
        except ValueError as e:
            # Calibration unaffordable
            self._log(f"  ⚠️  Calibration failed: {e}")
            self._log(f"  Skipping calibration, resuming science")
            return

        # Log proposal statistics
        stats = get_calibration_statistics(proposal)
        self._log(f"  Wells: {stats['total_wells']}")
        self._log(f"  Center fraction: {stats['center_fraction']:.1%}")
        self._log(f"  Compounds: {stats['compounds']}")

        # Execute proposal through normal experiment runner
        start_time = time.time()
        raw_results = self.world.run_experiment(proposal)

        # Aggregate observation
        observation = aggregate_observation(
            proposal=proposal,
            raw_results=raw_results,
            budget_remaining=self.world.budget_remaining,
            strategy="default_per_channel"
        )
        elapsed = time.time() - start_time

        self._log(f"  Execution time: {elapsed:.2f}s")
        self._log(f"  Budget remaining: {self.world.budget_remaining} wells")

        # Extract calibration metrics from observation
        from .calibration_metrics import (
            extract_calibration_metrics_from_observation,
            calibration_metrics_to_dict
        )

        metrics_obj = extract_calibration_metrics_from_observation(observation)
        metrics_dict = calibration_metrics_to_dict(metrics_obj)

        self._log(f"\n  Calibration metrics:")
        self._log(f"    Cleanliness score: {metrics_obj.cleanliness_score:.2f}")
        if metrics_obj.morans_i is not None:
            self._log(f"    Moran's I: {metrics_obj.morans_i:.3f}")
        if metrics_obj.nuclei_cv is not None:
            self._log(f"    Nuclei CV: {metrics_obj.nuclei_cv:.3f}")
        if metrics_obj.segmentation_quality is not None:
            self._log(f"    Segmentation quality: {metrics_obj.segmentation_quality:.3f}")

        # Apply calibration result to beliefs
        self.agent.beliefs.apply_calibration_result(metrics_dict, cycle=cycle)

        # Snapshot state after
        uncertainty_after = self.agent.beliefs.calibration_uncertainty
        debt_after = self.agent.beliefs.health_debt

        self._log(f"\n  Belief updates:")
        self._log(f"    Uncertainty: {uncertainty_before:.3f} → {uncertainty_after:.3f} (Δ={uncertainty_before - uncertainty_after:+.3f})")
        self._log(f"    Health debt: {debt_before:.2f} → {debt_after:.2f} (Δ={debt_before - debt_after:+.2f})")

        # End cycle and get events
        events = self.agent.beliefs.end_cycle()
        diagnostics = self.agent.last_diagnostics or []

        # Write ledgers
        if events:
            append_events_jsonl(self.evidence_file, events)
        if diagnostics:
            append_noise_diagnostics_jsonl(self.diagnostics_file, diagnostics)

        # Log calibration event (for EpisodeSummary aggregation)
        calibration_event = {
            "cycle": cycle,
            "cycle_type": "calibration",
            "flagged_cycle": context.cycle_flagged,
            "seed": self.seed,
            "reason": context.rationale,
            "uncertainty_before": uncertainty_before,
            "uncertainty_after": uncertainty_after,
            "debt_before": debt_before,
            "debt_after": debt_after,
            "metrics": metrics_dict,
            "budget_plates_remaining": self.world.budget_remaining / 96.0,
        }

        # Write to calibration log (new file)
        calibration_file = self.log_dir / f"{self.run_id}_calibration.jsonl"
        with open(calibration_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(calibration_event) + '\n')

        # Add to history
        self.history.append({
            'cycle': cycle,
            'proposal': {
                'design_id': proposal.design_id,
                'hypothesis': proposal.hypothesis,
                'n_wells': len(proposal.wells),
            },
            'observation': {
                'design_id': observation.design_id,
                'n_conditions': len(observation.conditions),
                'wells_spent': observation.wells_spent,
                'budget_remaining': observation.budget_remaining,
                'qc_flags': observation.qc_flags,
            },
            'elapsed_seconds': elapsed,
            'is_calibration': True,
            'calibration_metrics': metrics_dict,
            'uncertainty_reduction': uncertainty_before - uncertainty_after,
        })

        self._save_json()
