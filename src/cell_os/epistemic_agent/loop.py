"""
Main orchestration loop: the "movie" we want to watch.

This runs cycles of:
1. Agent proposes experiment (with hypothesis/reasoning)
2. World executes and returns observations
3. Agent updates beliefs
4. Log everything for narrative

The logging is crucial - this is how we watch the agent learn.
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from .world import ExperimentalWorld
from .agent.policy_rules import RuleBasedPolicy
from .schemas import Observation


class EpistemicLoop:
    """Main loop for epistemic agency experiments."""

    def __init__(
        self,
        budget: int = 384,
        max_cycles: int = 20,
        log_dir: Optional[Path] = None,
        seed: int = 0
    ):
        self.budget = budget
        self.max_cycles = max_cycles
        self.seed = seed

        # Setup logging
        if log_dir is None:
            log_dir = Path("results/epistemic_agent")
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Create run-specific log file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self.log_dir / f"run_{timestamp}.log"
        self.json_file = self.log_dir / f"run_{timestamp}.json"

        # Initialize world and agent
        self.world = ExperimentalWorld(budget_wells=budget, seed=seed)
        self.agent = RuleBasedPolicy(budget=budget)

        # Run history
        self.history = []

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

            # Agent proposes experiment
            proposal = self.agent.propose_next_experiment(
                capabilities,
                previous_observation=self.history[-1] if self.history else None
            )

            self._log_proposal(proposal)

            # World executes
            start_time = time.time()
            try:
                observation = self.world.run_experiment(proposal)
                elapsed = time.time() - start_time

                self._log_observation(observation, elapsed)

                # Agent updates
                self.agent.update_from_observation(observation)

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

        # What did the agent learn?
        self._log("\n" + "-"*60)
        self._log("AGENT STATE (What It Learned)")
        self._log("-"*60)
        self._log(f"Baseline measured: {self.agent.baseline_measured}")
        self._log(f"Edge effects tested: {self.agent.edge_tested}")
        self._log(f"Time effects tested: {self.agent.time_tested}")
        self._log(f"Dose-response curves: {len(self.agent.dose_responses)} compounds")

        # Success metrics
        self._log("\n" + "-"*60)
        self._log("SUCCESS METRICS (To Be Evaluated)")
        self._log("-"*60)
        self._log("[ ] Calibration: Estimated baseline CV within 20% error?")
        self._log("[ ] Edge detection: Detected edge bias with confidence?")
        self._log("[ ] Sample efficiency: Used <384 wells to learn?")
        self._log("[ ] Mid-dose discovery: Allocated >60% to mid-dose range?")

        self._log(f"\nFull log: {self.log_file}")
        self._log(f"JSON data: {self.json_file}")

    def _save_json(self):
        """Save history to JSON for analysis."""
        with open(self.json_file, 'w') as f:
            json.dump({
                'budget': self.budget,
                'max_cycles': self.max_cycles,
                'seed': self.seed,
                'history': self.history,
            }, f, indent=2)
