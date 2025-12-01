"""
Modernized Autonomous Experiment Loop

This is a refactored version of scripts/demos/run_loop.py that uses the production
execution infrastructure (AutonomousExecutor, WorkflowExecutor, JobQueue).

Key Improvements:
- Uses production-ready execution engine
- Unified job scheduling with manual experiments
- Crash recovery through persistent state
- Better resource management
- Cleaner separation of concerns

Usage:
    python scripts/demos/run_loop_v2.py --config config/autonomous_campaign.yaml
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
from cell_os.campaign_db import CampaignDatabase, Campaign, CampaignIteration, Experiment


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
            hardware=BiologicalVirtualMachine()
        )
        self.learner = SimpleLearner()
        self.iteration = 0
        self.history: List[ExperimentResult] = []
        self.total_cost = 0.0
        
        # Initialize database
        self.db = CampaignDatabase()
        
        # Create output directory
        self.output_dir = Path(config.output_dir) / config.campaign_id
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Save config
        with open(self.output_dir / "config.yaml", "w") as f:
            yaml.dump(asdict(config), f)

    def run(self):
        """Run the autonomous campaign."""
        logger.info(f"Starting campaign {self.config.campaign_id}")
        
        # Create campaign in DB
        self.db.create_campaign(Campaign(
            campaign_id=self.config.campaign_id,
            campaign_type="autonomous",
            goal="optimization",
            status="running",
            config=asdict(self.config),
            start_date=datetime.now().isoformat()
        ))
        
        start_time = time.time()
        
        try:
            while self.iteration < self.config.max_iterations:
                self.iteration += 1
                logger.info(f"Iteration {self.iteration}/{self.config.max_iterations}")
                
                # 1. Propose experiments
                proposals = self.learner.propose_experiments(
                    self.config.batch_size,
                    self.config
                )
                logger.info(f"Proposed {len(proposals)} experiments")
                
                # 2. Execute experiments
                results = self.executor.execute_batch(
                    proposals,
                    priority=JobPriority.NORMAL,
                    wait=True
                )
                logger.info(f"Completed {len(results)} experiments")
                
                # 3. Update model
                self.learner.update(results)
                self.history.extend(results)
                
                # 4. Check convergence
                if self.learner.check_convergence(self.config):
                    logger.info("Convergence reached!")
                    break
                
                # 5. Save checkpoint
                self._save_checkpoint(results)
                
        except KeyboardInterrupt:
            logger.warning("Campaign interrupted by user")
            self.db.update_campaign_status(self.config.campaign_id, "cancelled")
        except Exception as e:
            logger.error(f"Campaign failed: {e}")
            self.db.update_campaign_status(self.config.campaign_id, "failed")
            raise
        finally:
            self._finalize_campaign()
            duration = time.time() - start_time
            logger.info(f"Campaign finished in {duration:.2f}s")
            self.executor.shutdown()

    def _save_checkpoint(self, results: List[ExperimentResult]):
        """Save campaign checkpoint."""
        # Save to JSON (legacy backup)
        checkpoint = {
            "iteration": self.iteration,
            "timestamp": datetime.now().isoformat(),
            "results": [r.to_dict() for r in results],
            "total_experiments": len(self.history),
            "queue_stats": self.executor.get_queue_stats()
        }
        
        checkpoint_path = self.output_dir / f"checkpoint_iter_{self.iteration:03d}.json"
        with open(checkpoint_path, "w") as f:
            json.dump(checkpoint, f, indent=2)
            
        # Save to Database
        self.db.add_iteration(CampaignIteration(
            campaign_id=self.config.campaign_id,
            iteration_number=self.iteration,
            results=[r.to_dict() for r in results],
            metrics={
                "total_experiments": len(self.history),
                "queue_stats": self.executor.get_queue_stats()
            }
        ))
        
        # Save individual experiments to DB
        for res in results:
            exp_id = res.execution_id or f"exp_{self.config.campaign_id}_{self.iteration}_{res.proposal_id}"
            
            # Create experiment record if it doesn't exist
            # (In a real system, Executor would create this, but we do it here for now)
            try:
                self.db.create_experiment(Experiment(
                    experiment_id=exp_id,
                    campaign_id=self.config.campaign_id,
                    experiment_type=res.assay_type,
                    cell_line_id=res.cell_line,
                    status=res.status,
                    metadata=res.metadata
                ))
            except Exception:
                pass # Ignore if already exists
            
            # Link to campaign
            self.db.link_experiment_to_campaign(
                self.config.campaign_id,
                exp_id,
                iteration_number=self.iteration
            )

    def _finalize_campaign(self):
        """Finalize campaign and generate report."""
        best_result = self.learner.get_best_result()
        
        report = {
            "campaign_id": self.config.campaign_id,
            "status": "completed",
            "config": asdict(self.config),
            "results": {
                "total_iterations": self.iteration,
                "total_experiments": len(self.history),
                "best_result": best_result.to_dict() if best_result else None,
                "total_cost": self.total_cost
            },
            "all_results": [r.to_dict() for r in self.history]
        }
        
        # Save JSON report
        with open(self.output_dir / "campaign_report.json", "w") as f:
            json.dump(report, f, indent=2)
            
        # Update Database status
        self.db.update_campaign_status(
            self.config.campaign_id,
            "completed",
            results_summary=report["results"]
        )
        
        logger.info(f"Campaign report saved to {self.output_dir}")
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
