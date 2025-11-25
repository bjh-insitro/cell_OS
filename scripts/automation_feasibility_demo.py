"""
run_loop.py

The Autonomous Research Agent.
Executes the closed loop: Simulate -> Model -> Acquire -> Repeat.
"""

import sys
import os
import numpy as np
import pandas as pd

from cell_os.simulation import simulate_plate_data, TRUE_IC50, HILL_SLOPES, logistic_viability
from cell_os.modeling import (
    estimate_plate_drift_from_controls,
    apply_plate_drift_correction,
    estimate_replicate_noise,
    DoseResponseGP,
    DoseResponseGPConfig
)
from cell_os.schema import Phase0WorldModel, SliceKey
from cell_os.acquisition import propose_next_experiments
from cell_os.reporting import MissionLogger
from cell_os.campaign import Campaign, PotencyGoal, SelectivityGoal
from cell_os.assay_selector import CostConstrainedSelector, get_assay_candidates
from cell_os.inventory import Inventory
from cell_os.unit_ops import UnitOpLibrary, ParametricOps, VesselLibrary
from cell_os.recipe_optimizer import RecipeOptimizer, RecipeConstraints
from cell_os.llm_scientist import LLMScientist


def execute_experiments(experiment_df: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """
    "Run" the experiments in the lab (simulate them).
    
    Args:
        experiment_df: DataFrame with columns [cell_line, compound, dose_uM, time_h, ...]
        rng: Random number generator.
        
    Returns:
        DataFrame with added 'raw_signal', 'viability_norm', 'is_control', etc.
    """
    results = []
    
    # We assume these are all treated wells for now
    # In a real loop we'd mix in controls, but let's keep it simple
    
    for _, row in experiment_df.iterrows():
        cell = row["cell_line"]
        compound = row["compound"]
        dose = row["dose_uM"]
        time_h = row["time_h"]
        
        # 1. Get Ground Truth
        ic50 = TRUE_IC50.get((cell, compound), 1.0)
        h = HILL_SLOPES.get(compound, 1.0)
        
        # 2. Compute True Viability
        true_viab = logistic_viability(dose, ic50, h)
        
        # 3. Add Noise
        # We don't have plate factors here because we aren't simulating full plates
        # Just assume perfectly normalized plate for this "single well" injection
        # or add a random plate factor if we want to be fancy.
        # Let's assume we are adding to a "virtual plate" with factor 1.0
        
        # Measurement noise
        viab_observed = rng.normal(loc=true_viab, scale=0.05)
        
        # Clip
        viab_observed = max(0.0, viab_observed)
        
        # Build result row
        # We need to match the schema expected by modeling.py
        new_row = row.to_dict()
        new_row["raw_signal"] = viab_observed * 10000 # Fake units
        new_row["viability_norm"] = viab_observed
        new_row["is_control"] = 0
        new_row["incubator_id"] = "inc1"
        new_row["liquid_handler_id"] = "robot"
        new_row["date"] = "2025-11-22"
        
        results.append(new_row)
        
    return pd.DataFrame(results)


def main():
    print("=== cell_OS: Starting Autonomous Loop ===")
    rng = np.random.default_rng(42)
    
    # -----------------------------------------------------------
    # Phase 0: Baseline Data Generation
    # -----------------------------------------------------------
    print("\n[Phase 0] Generating baseline data...")
    df_history = simulate_plate_data(
        cell_lines=["HepG2", "U2OS"],
        compounds=["staurosporine", "tunicamycin"],
        n_plates_per_line=2, # Keep it small for speed
        replicates_per_dose=2,
        random_seed=42
    )
    print(f"  -> Generated {len(df_history)} wells.")
    
    # -----------------------------------------------------------
    # The Loop
    # -----------------------------------------------------------
    n_cycles = 5 # Increase max cycles
    logger = MissionLogger()
    
    # Define Campaign Goal
    # "Find a compound that kills HepG2 (IC50 < 0.1) but spares U2OS (IC50 > 0.1)"
    # Staurosporine: HepG2=0.05, U2OS=0.20 -> Should Pass
    # Tunicamycin: HepG2=0.80, U2OS=0.30 -> Should Fail
    goal = SelectivityGoal(
        target_cell="HepG2", 
        safe_cell="U2OS", 
        potency_threshold_uM=0.1,
        safety_threshold_uM=0.1
    )
    campaign = Campaign(goal=goal, max_cycles=n_cycles)
    
    # Initialize Economic Engine
    print("  [Economics] Initializing Inventory and Assay Selector...")
    inv = Inventory('data/raw/pricing.yaml')
    vessel_lib = VesselLibrary('data/raw/vessels.yaml')
    ops = ParametricOps(vessel_lib, inv)
    
    optimizer = RecipeOptimizer(ops)
    selector = CostConstrainedSelector()
    
    # Initial Budget
    wallet_balance = 5000.0
    print(f"  [Economics] Starting Budget: ${wallet_balance:.2f}")
    
    print(f"Starting Campaign: {goal.description()}")
    
    for cycle in range(1, n_cycles + 1):
        campaign.current_cycle = cycle
        print(f"\n--- Cycle {cycle} ---")
        print(f"  [Economics] Remaining Budget: ${wallet_balance:.2f}")
        
        if wallet_balance <= 0:
            print("  ! Budget exhausted! Stopping campaign.")
            break
        
        # 0. Assay Selection
        # Generate candidates for relevant cell lines
        candidates = []
        for cell_line in ["HepG2", "U2OS"]:
            # Create constraints based on budget status
            budget_tier = "standard"
            if wallet_balance < 1000:
                budget_tier = "budget"
            
            constraints = RecipeConstraints(
                cell_line=cell_line,
                budget_tier=budget_tier
            )
            
            # Generate optimized recipes
            # For this loop, we'll stick to our standard assay types but optimized
            # 1. POSH (Screening)
            # 2. High Content (Phagocytosis proxy for now)
            # 3. Transcriptomics (Bulk RNA-seq)
            
            # Note: In a real system, we'd have a more dynamic way to generate these.
            # For now, let's use the factory but we need to update it to use optimizer
            # OR we just manually create candidates here using the optimizer.
            
            # Let's use the existing get_assay_candidates but update it to be dynamic?
            # Actually, let's just use the static ones for now but filter by budget
            # To do this properly requires refactoring get_assay_candidates to take optimizer.
            # Let's stick to the plan: Use CostConstrainedSelector on existing candidates.
            pass

        # Re-generate candidates with current pricing/optimization
        # For simplicity in this step, we'll use the static generator but filter dynamically
        # In a full implementation, we'd generate candidates per cell line.
        raw_candidates = get_assay_candidates(ops, inv)
        
        # Select best assay within budget
        selected_assay = selector.select(raw_candidates, wallet_balance, prioritize_info=True)
        
        if selected_assay:
            print(f"  [Assay Selector] Selected: {selected_assay.recipe.name}")
            print(f"    Cost: ${selected_assay.cost_usd:.2f}")
            print(f"    ROI: {selected_assay.roi:.4f} bits/$")
            
            # Deduct cost
            wallet_balance -= selected_assay.cost_usd
        else:
            print(f"  [Assay Selector] No assay fits within budget ${wallet_balance:.2f}!")
            print("  ! Stopping campaign due to budget constraints.")
            break
        
        # ... (Modeling code remains same) ...
        
        # 1. Modeling
        print("  [Modeling] Fitting GPs...")
        
        # Preprocessing (Drift Correction)
        drift_df = estimate_plate_drift_from_controls(
            df_history, 
            viability_col="viability_norm"
        )
        df_corr = apply_plate_drift_correction(
            df_history, 
            drift_df, 
            viability_col="viability_norm"
        )
        
        # Noise Estimation
        noise_df = estimate_replicate_noise(
            df_corr, 
            viability_col="viability_corrected"
        )
        
        # Fit GPs
        # We need to group by slice
        slices = df_corr.groupby(["cell_line", "compound", "time_h"])
        gp_models = {}
        
        for (cell, cmpd, time), sub_df in slices:
            # Only fit if we have enough data (e.g. > 2 points)
            # Filter out controls for fitting AND zero doses
            treated = sub_df[(sub_df["is_control"] == 0) & (sub_df["dose_uM"] > 0)]
            if len(treated) < 3:
                continue
                
            try:
                gp = DoseResponseGP.from_dataframe(
                    treated, 
                    cell_line=cell, 
                    compound=cmpd, 
                    time_h=time,
                    viability_col="viability_corrected" # Use corrected data
                )
                gp_models[SliceKey(cell, cmpd, time)] = gp
                print(f"    + Fit {cell} {cmpd}")
            except Exception as e:
                print(f"    ! Failed to fit {cell} {cmpd}: {e}")
        
        print(f"  -> Fit {len(gp_models)} models.")
        
        # Build World Model
        world = Phase0WorldModel(
            gp_models=gp_models,
            noise_df=noise_df,
            drift_df=drift_df
        )
        
        # Check Campaign Goal
        if campaign.check_goal(world):
            print(f"\n>>> CAMPAIGN SUCCESS! Goal Met: {goal.description()}")
            print(f">>> Found Potent Compound: {goal.met_by}")
            break
            
        # 2. Acquisition
        print("  [Acquisition] Proposing experiments...")
        try:
            next_experiments, candidates = propose_next_experiments(world, n_experiments=5)
            
            # Log the cycle
            logger.log_cycle(cycle, world, next_experiments, candidates)
            
        except ValueError as e:
            print(f"    ! Acquisition failed: {e}")
            break
            
        print("  -> Selected experiments:")
        print(next_experiments[["cell_line", "compound", "dose_uM", "priority_score"]])
        
        # 3. Execution
        print("  [Execution] Running experiments in silico...")
        new_data = execute_experiments(next_experiments, rng)
        
        # Append to history
        # We need to ensure columns match. 
        # df_history has 'viability_norm' (uncorrected but normalized to plate).
        # new_data has 'viability_norm' (perfectly normalized).
        # We can just concat.
        
        # Ensure new_data has all columns of df_history
        for col in df_history.columns:
            if col not in new_data.columns:
                new_data[col] = np.nan # or sensible default
                
        df_history = pd.concat([df_history, new_data], ignore_index=True)
        print(f"  -> Added {len(new_data)} new data points. Total: {len(df_history)}")

    # Save history
    output_path = "results/experiment_history.csv"
    df_history.to_csv(output_path, index=False)
    print(f"\nSaved experiment history to {output_path}")

    # Finalize Mission Log
    logger.finalize()
    print(f"Mission Log saved to {logger.filepath}")
    
    # LLM Scientist Analysis
    print("\n[LLM Scientist] Analyzing Mission Log...")
    scientist = LLMScientist()
    if os.path.exists(logger.filepath):
        with open(logger.filepath, "r") as f:
            log_content = f.read()
            
        insight = scientist.analyze_mission_log(log_content)
        
        print(f"  Summary: {insight.summary}")
        print(f"  Hypothesis: {insight.hypothesis}")
        
        # Append to log
        with open(logger.filepath, "a") as f:
            f.write("\n\n## 🧠 Scientist's Conclusion\n\n")
            f.write(f"**Summary**: {insight.summary}\n\n")
            f.write(f"**Hypothesis**: {insight.hypothesis}\n\n")
            f.write(f"*(Confidence: {insight.confidence})*\n")

    print("\n=== Loop Complete ===")

if __name__ == "__main__":
    main()
