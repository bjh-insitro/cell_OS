"""End-to-end POSH campaign demo.

This script demonstrates the complete autonomous workflow:
1. Perturbation selection (which genes to screen)
2. Simulated execution (fake POSH screen)
3. Phenotype aggregation (morphology-based hit calling)

The output is a ranked hit table showing which genes are most phenotypically shifted.
"""

import os
import pandas as pd

from cell_os.lab_world_model import LabWorldModel
from cell_os.perturbation_goal import PerturbationPosterior, PerturbationGoal
from cell_os.perturbation_loop import PerturbationAcquisitionLoop
from cell_os.simulated_perturbation_executor import SimulatedPerturbationExecutor


def main():
    """Run a complete simulated POSH campaign."""
    print("=" * 60)
    print("POSH Campaign Demo - End-to-End Autonomous Workflow")
    print("=" * 60)
    
    # Step 1: Initialize world model and posterior
    print("\nStep 1: Initialize world model and posterior...")
    world_model = LabWorldModel.empty()
    posterior = PerturbationPosterior()
    
    # Define candidate genes for screening
    candidate_genes = [
        "TP53", "MDM2", "KRAS", "EGFR", "PTEN",
        "AKT1", "PIK3CA", "BRAF", "NRAS", "MYC",
        "CDKN2A", "RB1", "ATM", "BRCA1", "BRCA2",
    ]
    print(f"   Candidate genes: {len(candidate_genes)} genes")
    
    # Step 2: Set up perturbation loop
    print("\nStep 2: Set up perturbation acquisition loop...")
    executor = SimulatedPerturbationExecutor()
    
    goal = PerturbationGoal(
        objective="maximize_diversity",
        max_perturbations=10,
        min_guides_per_gene=3,
        min_replicates=2,
    )
    print(f"   Goal: {goal.objective}")
    print(f"   Max perturbations: {goal.max_perturbations}")
    
    loop = PerturbationAcquisitionLoop(
        posterior=posterior,
        executor=executor,
        goal=goal,
    )
    
    # Step 3: Run one acquisition cycle
    print("\nStep 3: Run perturbation acquisition cycle...")
    print("   Proposing perturbation plans...")
    batch = loop.propose(candidate_genes)
    print(f"   Proposed {len(batch.plans)} perturbations")
    print(f"   Total cost: ${batch.total_cost_usd:.2f}")
    
    print("   Executing simulated screen...")
    results = executor.run_batch(batch)
    print(f"   Generated {len(results)} result rows")
    
    print("   Updating posterior with results...")
    posterior.update_with_results(results)
    print(f"   Posterior now has {len(posterior.embeddings)} gene embeddings")
    
    # Step 4: Aggregate phenotypes and rank hits
    print("\nStep 4: Aggregate phenotypes and rank hits...")
    phenotype_table = posterior.gene_phenotype_table()
    top_hits = posterior.top_hits(top_n=20)
    
    print(f"   Phenotype table: {len(phenotype_table)} genes")
    print(f"   Top hits: {len(top_hits)} genes")
    
    # Display top 5 hits
    print("\n   Top 5 hits by phenotypic shift:")
    for i, gene in enumerate(top_hits[:5], 1):
        row = phenotype_table[phenotype_table["gene"] == gene].iloc[0]
        print(f"      {i}. {gene:10s} "
              f"(distance: {row['distance_to_centroid']:.3f}, "
              f"viability: {row['phenotype_score']:.3f})")
    
    # Step 5: Write results
    print("\nStep 5: Write results to CSV...")
    output_dir = "results"
    os.makedirs(output_dir, exist_ok=True)
    
    output_path = os.path.join(output_dir, "posh_demo_hits.csv")
    phenotype_table.to_csv(output_path, index=False)
    print(f"   Results written to: {output_path}")
    
    print("\n" + "=" * 60)
    print("Demo complete!")
    print("=" * 60)
    print(f"\nView results: cat {output_path}")
    print(f"Top {len(top_hits)} hits: {', '.join(top_hits[:10])}")
    
    return output_path


if __name__ == "__main__":
    main()
