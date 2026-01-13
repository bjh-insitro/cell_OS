#!/usr/bin/env python3
"""Run a predefined experimental scenario.

Usage:
    python -m src.run_scenario --name cheap_pilot
    python -m src.run_scenario --name posh_window_finding
    python -m src.run_scenario --name high_risk_morphology
    python -m src.run_scenario --list
"""

import argparse
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from cell_os.scenarios import get_scenario, list_scenarios, apply_scenario
from cell_os.perturbation_goal import PerturbationPosterior, PerturbationGoal
from cell_os.perturbation_loop import PerturbationAcquisitionLoop
from cell_os.simulation.simulated_perturbation_executor import SimulatedPerturbationExecutor
from cell_os.reporting import summarize_campaign
from cell_os.inventory import OutOfStockError


def run_scenario(scenario_name: str):
    """Run a complete scenario.
    
    Parameters
    ----------
    scenario_name : str
        Name of scenario to run
    """
    print(f"\n{'='*70}")
    print(f"RUNNING SCENARIO: {scenario_name}")
    print(f"{'='*70}\n")
    
    # Load scenario
    scenario = get_scenario(scenario_name)
    print(f"Description: {scenario.description}")
    print(f"Budget: ${scenario.budget_usd:,.2f}")
    print(f"Max Perturbations: {scenario.max_perturbations}")
    print(f"Failure Mode: {scenario.failure_mode}")
    print()
    
    # Apply scenario configuration
    inventory, morphology_engine, campaign_config = apply_scenario(scenario)
    
    # Track initial inventory for reporting
    initial_inventory = {
        resource_id: qty 
        for resource_id, qty in scenario.initial_inventory.items()
    }
    
    # Create posterior and executor
    posterior = PerturbationPosterior()
    executor = SimulatedPerturbationExecutor(inventory=inventory)
    
    # Create goal
    goal = PerturbationGoal(
        max_perturbations=scenario.max_perturbations,
        profile_name=scenario.acquisition_profile,
    )
    
    # Create loop
    loop = PerturbationAcquisitionLoop(
        posterior=posterior,
        executor=executor,
        goal=goal,
    )
    
    # Define candidate genes
    candidate_genes = [
        "TP53", "MDM2", "KRAS", "EGFR", "PTEN",
        "AKT1", "PIK3CA", "BRAF", "NRAS", "MYC",
        "CDKN2A", "RB1", "ATM", "BRCA1", "BRCA2",
        "ERBB2", "FGFR1", "MET", "ALK", "RET",
    ]
    
    # Run campaign
    print("Starting campaign...")
    termination_reason = "completed"
    results = None
    
    try:
        # Run one cycle
        print("  Proposing perturbations...")
        batch = loop.propose(candidate_genes)
        print(f"  Proposed {len(batch.plans)} perturbations")
        
        # Track cost
        total_cost = batch.total_cost_usd
        print(f"  Estimated cost: ${total_cost:.2f}")
        
        print("  Executing experiments...")
        results = executor.run_batch(batch)
        print(f"  Generated {len(results)} result rows")
        
        print("  Updating posterior...")
        posterior.update_with_results(results)
        print(f"  Posterior now has {len(posterior.embeddings)} gene embeddings")
        
        termination_reason = "completed"
        
    except OutOfStockError as e:
        print(f"\n  ⚠️  Out of stock: {e}")
        termination_reason = f"out_of_stock: {str(e)}"
        
    except ValueError as e:
        if "budget" in str(e).lower():
            print(f"\n  ⚠️  Budget exceeded: {e}")
            termination_reason = f"budget_exceeded: {str(e)}"
        else:
            raise
    
    except Exception as e:
        print(f"\n  ❌ Error: {e}")
        termination_reason = f"error: {str(e)}"
        raise
    
    print("\nCampaign finished.")
    print()
    
    # Create mock campaign for reporting
    from cell_os.campaign import Campaign
    
    class MockGoal:
        def is_met(self, world_model):
            return False
    
    campaign = Campaign(
        MockGoal(),
        max_cycles=scenario.max_cycles,
        budget_total_usd=scenario.budget_usd,
        failure_mode=scenario.failure_mode,
    )
    campaign.current_cycle = 1
    campaign.budget_spent_usd = total_cost if 'total_cost' in locals() else 0.0
    
    # Generate report
    summary = summarize_campaign(
        campaign=campaign,
        inventory=inventory,
        results=results,
        initial_inventory=initial_inventory,
        termination_reason=termination_reason,
    )
    
    print(summary)

    # ------------------------------------------------------------------
    # Cost Accounting (Tier 7)
    # ------------------------------------------------------------------
    try:
        from cell_os.lab_world_model import LabWorldModel
        
        # Create a transient LabWorldModel to use its accounting capabilities
        # We initialize it with the current inventory state (pricing)
        lwm = LabWorldModel.from_static_tables(
            pricing=inventory.to_dataframe()
        )
        
        # Compute costs from the inventory usage log
        if hasattr(inventory, 'usage_log'):
            cost_report = lwm.compute_cost(inventory.usage_log)
            
            print("\n" + "=" * 70)
            print("COST ACCOUNTING REPORT (Tier 7)")
            print("=" * 70)
            print(f"Total Cost: ${cost_report['total_cost_usd']:,.2f}")
            print("-" * 70)
            print("Breakdown:")
            
            # Sort breakdown by cost descending
            sorted_breakdown = sorted(
                cost_report['breakdown'].items(), 
                key=lambda x: x[1], 
                reverse=True
            )
            
            for rid, cost in sorted_breakdown:
                try:
                    rname = inventory.get_resource(rid).name
                    print(f"  {rname:<40} ${cost:,.2f}")
                except:
                    print(f"  {rid:<40} ${cost:,.2f}")
            print("=" * 70 + "\n")
            
    except Exception as e:
        print(f"\n⚠️  Could not generate cost report: {e}")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Run predefined experimental scenarios",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m src.run_scenario --name cheap_pilot
  python -m src.run_scenario --name posh_window_finding
  python -m src.run_scenario --list
        """
    )
    
    parser.add_argument(
        "--name",
        type=str,
        help="Scenario name to run"
    )
    
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available scenarios"
    )
    
    args = parser.parse_args()
    
    if args.list:
        print("\nAvailable Scenarios:")
        print("=" * 70)
        for name, description in list_scenarios().items():
            print(f"\n  {name}")
            print(f"    {description}")
        print()
        return
    
    if not args.name:
        parser.print_help()
        sys.exit(1)
    
    try:
        run_scenario(args.name)
    except KeyError as e:
        print(f"\nError: {e}")
        print("\nUse --list to see available scenarios")
        sys.exit(1)
    except Exception as e:
        print(f"\nError running scenario: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
