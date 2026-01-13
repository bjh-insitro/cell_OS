"""End-to-end POSH campaign demo.

This script demonstrates the complete autonomous workflow:
1. Perturbation selection (which genes to screen)
2. Simulated execution (fake POSH screen)
3. Phenotype aggregation (morphology-based hit calling)

The output is a ranked hit table showing which genes are most phenotypically shifted.
"""

import os
import argparse
import pandas as pd

from cell_os.lab_world_model import LabWorldModel
from cell_os.perturbation_goal import PerturbationPosterior, PerturbationGoal
from cell_os.perturbation_loop import PerturbationAcquisitionLoop
from cell_os.simulation.simulated_perturbation_executor import SimulatedPerturbationExecutor


def main(profile_name: str = "balanced"):
    """Run a complete simulated POSH campaign.
    
    Parameters
    ----------
    profile_name : str
        Acquisition profile to use (default: "balanced")
    """
    print("=" * 60)
    print("POSH Campaign Demo - End-to-End Autonomous Workflow")
    print("=" * 60)
    print(f"\nUsing acquisition profile: {profile_name}")
    
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
    
    # Step 2: Set up perturbation loop with profile
    print("\nStep 2: Set up perturbation acquisition loop...")
    executor = SimulatedPerturbationExecutor()
    
    goal = PerturbationGoal(
        objective="maximize_diversity",
        max_perturbations=10,
        min_guides_per_gene=3,
        min_replicates=2,
        profile_name=profile_name,
    )
    print(f"   Goal: {goal.objective}")
    print(f"   Max perturbations: {goal.max_perturbations}")
    print(f"   Diversity weight: {goal.profile.diversity_weight}")
    
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
    
    # Add profile metadata to results for comparison across runs
    phenotype_table_with_meta = phenotype_table.copy()
    phenotype_table_with_meta.insert(0, "profile", profile_name)
    
    output_path = os.path.join(output_dir, "posh_demo_hits.csv")
    phenotype_table_with_meta.to_csv(output_path, index=False)
    print(f"   Results written to: {output_path}")
    print(f"   Profile '{profile_name}' logged in CSV for run comparison")
    
    # Step 6: Cluster hits and write clustered results
    print("\nStep 6: Cluster hits by morphological similarity...")
    n_clusters = 3
    clustered_table = posterior.cluster_hits(n_clusters=n_clusters)
    cluster_summaries = posterior.cluster_summaries(n_clusters=n_clusters)
    
    # Write clustered table
    clustered_output_path = os.path.join(output_dir, "posh_demo_hits_with_clusters.csv")
    clustered_table.to_csv(clustered_output_path, index=False)
    print(f"   Clustered results written to: {clustered_output_path}")
    
    # Display cluster summaries
    if not cluster_summaries.empty:
        print(f"\n   Cluster summaries ({n_clusters} clusters):")
        for _, row in cluster_summaries.iterrows():
            print(f"      Cluster {row['cluster_id']}: "
                  f"{row['n_genes']:.0f} genes, "
                  f"mean distance {row['mean_distance_to_centroid']:.3f}, "
                  f"mean viability {row['mean_phenotype_score']:.3f}")
    
    print("\n" * 60)
    print("Demo complete!")
    print("=" * 60)
    print(f"\nView results: cat {output_path}")
    print(f"View clusters: cat {clustered_output_path}")
    print(f"Top {len(top_hits)} hits: {', '.join(top_hits[:10])}")
    
    return output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run POSH campaign demo with configurable profile")
    parser.add_argument(
        "--profile",
        type=str,
        default="balanced",
        choices=["balanced", "ambitious_postdoc", "cautious_operator", "wise_pi"],
        help="Acquisition profile (default: balanced)",
    )
    args = parser.parse_args()
    
    main(profile_name=args.profile)
