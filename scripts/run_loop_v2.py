"""
Modernized Autonomous Experiment Loop

This is a refactored version of scripts/run_loop.py that uses the production
execution infrastructure (AutonomousExecutor, WorkflowExecutor, JobQueue).

Key Improvements:
- Uses production-ready execution engine
- Unified job scheduling with manual experiments
- Crash recovery through persistent state
- Better resource management
- Cleaner separation of concerns

Usage:
    python scripts/run_loop_v2.py --config config/autonomous_campaign.yaml
"""

import argparse
import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

from cell_os.autonomous_executor import AutonomousExecutor, ExperimentProposal, ExperimentResult
from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from cell_os.job_queue import JobPriority


@dataclass
class CampaignConfig:
    """Configuration for an autonomous campaign."""
    campaign_id: str
    max_iterations: int = 20
    batch_size: int = 8
    initial_budget: float = 10000.0
    
    # Experimental design
    cell_lines: List[str] = field(default_factory=lambda: ["U2OS"])
    compounds: List[str] = field(default_factory=lambda: ["staurosporine"])
    dose_range: tuple = (0.001, 10.0)  # uM
    assay_type: str = "viability"
    
    # Optimization settings
    exploration_weight: float = 0.1
    convergence_threshold: float = 0.01
    
    # Output
    output_dir: str = "results/autonomous_campaigns"
    
    @classmethod
    def from_yaml(cls, path: str) -> "CampaignConfig":
        """Load configuration from YAML file."""
        import yaml
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls(**data)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CampaignConfig":
        """Create from dictionary."""
        return cls(**data)


class SimpleLearner:
    """
    Simplified learner for demonstration.
    
    In production, this would be replaced with:
    - Gaussian Process models
    - Bayesian optimization
    - Multi-fidelity learning
    """
    
    def __init__(self):
        self.history: List[ExperimentResult] = []
        self.iteration = 0
    
    def update(self, results: List[ExperimentResult]):
        """Update model with new experimental data."""
        self.history.extend(results)
        self.iteration += 1
        
        print(f"\n=== Iteration {self.iteration} ===")
        print(f"Collected {len(results)} new data points")
        print(f"Total data points: {len(self.history)}")
        
        # Simple statistics
        if results:
            measurements = [r.measurement for r in results]
            print(f"Measurements: min={min(measurements):.3f}, max={max(measurements):.3f}, mean={sum(measurements)/len(measurements):.3f}")
    
    def propose_experiments(
        self,
        n: int,
        config: CampaignConfig
    ) -> List[ExperimentProposal]:
        """
        Propose next batch of experiments.
        
        This is a simple random/grid strategy for demonstration.
        In production, use acquisition functions (EI, UCB, etc.)
        """
        import numpy as np
        
        proposals = []
        
        # Simple strategy: random sampling with some exploitation
        for i in range(n):
            # Select cell line and compound
            cell_line = np.random.choice(config.cell_lines)
            compound = np.random.choice(config.compounds)
            
            # Select dose (log-uniform sampling)
            log_dose = np.random.uniform(
                np.log10(config.dose_range[0]),
                np.log10(config.dose_range[1])
            )
            dose = 10 ** log_dose
            
            proposal = ExperimentProposal(
                proposal_id=f"prop_{self.iteration}_{i}",
                cell_line=cell_line,
                compound=compound,
                dose=dose,
                assay_type=config.assay_type,
                metadata={
                    "iteration": self.iteration,
                    "strategy": "random_sampling"
                }
            )
            
            proposals.append(proposal)
        
        return proposals
    
    def check_convergence(self, config: CampaignConfig) -> bool:
        """Check if optimization has converged."""
        # Simple convergence: check if we've hit max iterations
        return self.iteration >= config.max_iterations
    
    def get_best_result(self) -> Optional[ExperimentResult]:
        """Get the best result found so far."""
        if not self.history:
            return None
        
        # For viability, higher is better (assuming we're looking for non-toxic doses)
        # For other assays, this logic would differ
        return max(self.history, key=lambda r: r.measurement)


class AutonomousCampaign:
    """
    Manages an autonomous experimental campaign.
    
    This orchestrates the learning loop:
    1. Propose experiments (acquisition)
    2. Execute experiments (via AutonomousExecutor)
    3. Update model (learning)
    4. Check convergence
    5. Repeat
    """
    
    def __init__(
        self,
        config: CampaignConfig,
        executor: Optional[AutonomousExecutor] = None
    ):
        self.config = config
        self.executor = executor or AutonomousExecutor(
            hardware=BiologicalVirtualMachine(simulation_speed=0.0)
        )
        self.learner = SimpleLearner()
        
        # Setup output directory
        self.output_dir = Path(config.output_dir) / config.campaign_id
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Campaign state
        self.start_time = datetime.now()
        self.total_experiments = 0
        self.total_cost = 0.0
    
    def run(self):
        """Run the autonomous campaign."""
        print(f"\n{'='*60}")
        print(f"Starting Autonomous Campaign: {self.config.campaign_id}")
        print(f"{'='*60}")
        print(f"Max iterations: {self.config.max_iterations}")
        print(f"Batch size: {self.config.batch_size}")
        print(f"Cell lines: {', '.join(self.config.cell_lines)}")
        print(f"Compounds: {', '.join(self.config.compounds)}")
        print(f"Assay: {self.config.assay_type}")
        print(f"{'='*60}\n")
        
        while not self.learner.check_convergence(self.config):
            # 1. Propose experiments
            print(f"\n--- Proposing Experiments (Iteration {self.learner.iteration + 1}) ---")
            proposals = self.learner.propose_experiments(
                n=self.config.batch_size,
                config=self.config
            )
            
            print(f"Proposed {len(proposals)} experiments:")
            for p in proposals:
                print(f"  - {p.cell_line} + {p.compound} @ {p.dose:.3f} uM")
            
            # 2. Execute experiments
            print(f"\n--- Executing Experiments ---")
            start_exec = time.time()
            results = self.executor.execute_batch(
                proposals,
                priority=JobPriority.HIGH,
                wait=True,
                timeout=300.0
            )
            exec_time = time.time() - start_exec
            
            print(f"Executed {len(results)} experiments in {exec_time:.1f}s")
            
            # 3. Update model
            self.learner.update(results)
            
            # 4. Track progress
            self.total_experiments += len(results)
            
            # 5. Save checkpoint
            self._save_checkpoint(results)
            
            # 6. Check budget
            if self.total_cost > self.config.initial_budget:
                print(f"\n⚠️  Budget exceeded: ${self.total_cost:.2f} > ${self.config.initial_budget:.2f}")
                break
        
        # Campaign complete
        self._finalize_campaign()
    
    def _save_checkpoint(self, results: List[ExperimentResult]):
        """Save campaign checkpoint."""
        checkpoint_path = self.output_dir / f"checkpoint_iter_{self.learner.iteration}.json"
        
        checkpoint = {
            "campaign_id": self.config.campaign_id,
            "iteration": self.learner.iteration,
            "timestamp": datetime.now().isoformat(),
            "total_experiments": self.total_experiments,
            "results": [r.to_dict() for r in results],
            "queue_stats": self.executor.get_queue_stats()
        }
        
        with open(checkpoint_path, "w") as f:
            json.dump(checkpoint, f, indent=2)
        
        print(f"Checkpoint saved: {checkpoint_path}")
    
    def _finalize_campaign(self):
        """Finalize campaign and generate report."""
        duration = (datetime.now() - self.start_time).total_seconds()
        
        print(f"\n{'='*60}")
        print(f"Campaign Complete: {self.config.campaign_id}")
        print(f"{'='*60}")
        print(f"Total iterations: {self.learner.iteration}")
        print(f"Total experiments: {self.total_experiments}")
        print(f"Duration: {duration:.1f}s ({duration/60:.1f} min)")
        print(f"Throughput: {self.total_experiments/duration:.2f} exp/sec")
        
        # Get best result
        best = self.learner.get_best_result()
        if best:
            print(f"\nBest Result:")
            print(f"  Cell line: {best.cell_line}")
            print(f"  Compound: {best.compound}")
            print(f"  Dose: {best.dose:.3f} uM")
            print(f"  Measurement: {best.measurement:.3f}")
        
        # Save final report
        report_path = self.output_dir / "campaign_report.json"
        report = {
            "campaign_id": self.config.campaign_id,
            "config": {
                "max_iterations": self.config.max_iterations,
                "batch_size": self.config.batch_size,
                "cell_lines": self.config.cell_lines,
                "compounds": self.config.compounds,
                "assay_type": self.config.assay_type
            },
            "results": {
                "total_iterations": self.learner.iteration,
                "total_experiments": self.total_experiments,
                "duration_seconds": duration,
                "throughput": self.total_experiments / duration
            },
            "best_result": best.to_dict() if best else None,
            "all_results": [r.to_dict() for r in self.learner.history]
        }
        
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)
        
        print(f"\nFinal report saved: {report_path}")
        print(f"{'='*60}\n")
        
        # Cleanup
        self.executor.shutdown()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run autonomous experiment campaign")
    parser.add_argument(
        "--config",
        type=str,
        help="Path to campaign configuration YAML"
    )
    parser.add_argument(
        "--campaign-id",
        type=str,
        default=f"campaign_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        help="Campaign ID"
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=10,
        help="Maximum number of iterations"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=8,
        help="Number of experiments per batch"
    )
    
    args = parser.parse_args()
    
    # Load or create configuration
    if args.config:
        config = CampaignConfig.from_yaml(args.config)
    else:
        # Use default configuration
        config = CampaignConfig(
            campaign_id=args.campaign_id,
            max_iterations=args.max_iterations,
            batch_size=args.batch_size,
            cell_lines=["U2OS", "HEK293T"],
            compounds=["staurosporine", "tunicamycin"],
            assay_type="viability"
        )
    
    # Run campaign
    campaign = AutonomousCampaign(config)
    campaign.run()


if __name__ == "__main__":
    main()
