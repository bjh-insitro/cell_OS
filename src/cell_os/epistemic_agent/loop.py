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
from datetime import datetime
from pathlib import Path
from typing import Optional

from .world import ExperimentalWorld
from .agent.policy_rules import RuleBasedPolicy
from .schemas import Observation, Proposal, WellSpec
from .beliefs.ledger import append_events_jsonl, append_decisions_jsonl, append_noise_diagnostics_jsonl, DecisionEvent
from .exceptions import InvalidDesignError
from .controller_integration import EpistemicIntegration
from .design_quality import DesignQualityChecker


class EpistemicLoop:
    """Main loop for epistemic agency experiments."""

    def __init__(
        self,
        budget: int = 384,
        max_cycles: int = 20,
        log_dir: Optional[Path] = None,
        seed: int = 0,
        strict_quality: bool = True,
        strict_provenance: bool = True
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

        # Initialize world and agent
        self.world = ExperimentalWorld(budget_wells=budget, seed=seed)
        self.agent = RuleBasedPolicy(budget=budget)

        # v0.5.1: Epistemic integration (Task 3 - real epistemic claims)
        self.epistemic = EpistemicIntegration(enable=True)

        # NEW: Design quality checker (scientific heuristics, not physics)
        self.quality_checker = DesignQualityChecker(strict_mode=strict_quality)

        # Run history
        self.history = []
        self.abort_reason = None

    def run(self):
        """Run the full experiment loop."""
        self._log_header()

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

            # v0.4.2: Begin cycle for evidence tracking
            # Covenant 7: Snapshot beliefs before cycle for mutation tracking
            beliefs_before = self.agent.beliefs.snapshot()
            self.agent.beliefs.begin_cycle(cycle)

            # Agent proposes experiment
            try:
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

            if should_refuse:
                self._log("\n" + "="*60)
                self._log(f"EPISTEMIC DEBT REFUSAL: {refusal_reason}")
                self._log("="*60)
                self._log(f"  Debt accumulated: {refusal_context['debt_bits']:.3f} bits")
                self._log(f"  Base cost: {refusal_context['base_cost_wells']} wells")
                self._log(f"  Inflated cost: {refusal_context['inflated_cost_wells']} wells")
                self._log(f"  Budget remaining: {refusal_context['budget_remaining']} wells")

                if refusal_context['blocked_by_cost']:
                    self._log(f"  → Cost inflation from debt exceeds budget")
                if refusal_context['blocked_by_threshold']:
                    self._log(f"  → Debt threshold ({refusal_context['debt_threshold']:.1f} bits) exceeded for non-calibration action")

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
                observation = self.world.run_experiment(proposal)
                elapsed = time.time() - start_time

                self._log_observation(observation, elapsed)

                # Agent updates beliefs
                self.agent.update_from_observation(observation)

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

                # Save incremental JSON
                self._save_json()

            except Exception as e:
                self._log(f"\n❌ ERROR: {e}")
                self.abort_reason = f"Exception: {e}"
                break

        self._log_summary()

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
        }

        if integrity_warnings:
            output['integrity_warnings'] = integrity_warnings

        with open(self.json_file, 'w') as f:
            json.dump(output, f, indent=2)
