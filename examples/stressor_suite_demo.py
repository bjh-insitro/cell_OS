
import pandas as pd
import numpy as np
from src.lab_world_model import LabWorldModel
from src.posteriors import DoseResponsePosterior
from src.campaign import Campaign, StressWindowGoal, summarize_portfolio

def create_synthetic_data():
    """Create a synthetic dataset with multiple stressors and readouts."""
    rows = []
    
    # 2 Cell lines x 2 Stressors x 2 Readoutsimport os
import sys

# Make the repo root importable as `src` when running this script directly
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import numpy as np
import pandas as pd

from src.lab_world_model import LabWorldModel
from src.posteriors import DoseResponsePosterior
from src.campaign import Campaign, StressWindowGoal, summarize_portfolio


def create_synthetic_data() -> pd.DataFrame:
    """Create a synthetic dataset with multiple stressors and readouts (long format)."""
    rows = []

    # 2 cell lines x 2 stressors x 2 readouts
    cell_lines = ["U2OS", "HepG2"]
    stressors = ["TBHP", "Tunicamycin"]
    readouts = ["viability", "posh_score"]

    doses = [0.01, 0.1, 1.0, 10.0]

    rng = np.random.default_rng(42)

    for cell in cell_lines:
        for stressor in stressors:
            for dose in doses:
                # Synthetic response
                # TBHP is more potent than Tunicamycin
                potency = 1.0 if stressor == "TBHP" else 5.0

                # Viability drops with dose (simple Hill-like curve)
                viability = 1.0 / (1.0 + (dose / potency) ** 2)

                # POSH score goes up with dose (stress response proxy)
                posh_score = 1.0 - viability

                # Add rows for both readouts in long format
                rows.append(
                    {
                        "campaign_id": "DEMO",
                        "cell_line": cell,
                        "compound": stressor,
                        "dose_uM": dose,
                        "time_h": 24.0,
                        "readout_name": "viability",
                        "readout_value": viability + rng.normal(0, 0.05),
                        "plate_id": "P1",
                        "replicate": 1,
                    }
                )
                rows.append(
                    {
                        "campaign_id": "DEMO",
                        "cell_line": cell,
                        "compound": stressor,
                        "dose_uM": dose,
                        "time_h": 24.0,
                        "readout_name": "posh_score",
                        "readout_value": posh_score + rng.normal(0, 0.05),
                        "plate_id": "P1",
                        "replicate": 1,
                    }
                )

    return pd.DataFrame(rows)


def main() -> None:
    print("Generating synthetic data...")
    df = create_synthetic_data()

    print("Building LabWorldModel...")
    wm = LabWorldModel.empty()
    wm.add_experiments(df)

    print("Building posterior belief state...")
    # Model both viability and POSH score for all slices
    posterior = DoseResponsePosterior.from_world(
        world=wm,
        campaign_id="DEMO",
        readout_names=["viability", "posh_score"],
        time_h=24.0,
    )

    print(f"Fitted {len(posterior.gp_models)} GP slices.")

    # Define a goal:
    # Find a dose of TBHP in U2OS where POSH score is in [0.4, 0.6]
    goal = StressWindowGoal(
        cell_line="U2OS",
        stressor="TBHP",
        readout="posh_score",
        min_val=0.4,
        max_val=0.6,
    )

    print(f"Goal: {goal.description()}")

    campaign = Campaign(goal, max_cycles=3)

    print("\n--- Running campaign cycle 1 ---")

    # Run one acquisition cycle from the current posterior
    # Adjust this line if your Campaign.run_cycle signature differs
    proposals = campaign.run_cycle(posterior, n_experiments=5)

    print(f"Cycle 1 proposed {len(proposals)} experiments:")

    cols_to_show = [c for c in ["cell_line", "compound", "readout", "dose_uM", "priority_score"] if c in proposals.columns]
    print(proposals[cols_to_show])

    # Check whether the goal is already satisfied by the current posterior
    if campaign.check_goal(posterior):
        if getattr(goal, "met_by_dose", None) is not None:
            print(f"\nSUCCESS: goal met at dose {goal.met_by_dose:.4f} µM")
        else:
            print("\nSUCCESS: goal met (dose window found)")
    else:
        print("\nGoal not yet met.")

    print("\n--- Portfolio summary ---")
    summary = summarize_portfolio(posterior)
    print(summary)


if __name__ == "__main__":
    main()

    cell_lines = ["U2OS", "HepG2"]
    stressors = ["TBHP", "Tunicamycin"]
    readouts = ["viability", "posh_score"]
    
    doses = [0.01, 0.1, 1.0, 10.0]
    
    for cell in cell_lines:
        for stressor in stressors:
            for dose in doses:
                # Synthetic response
                # TBHP is more potent than Tunicamycin
                potency = 1.0 if stressor == "TBHP" else 5.0
                
                # Viability drops with dose
                viability = 1.0 / (1.0 + (dose / potency)**2)
                
                # POSH score goes up with dose (stress response)
                posh_score = 1.0 - viability
                
                # Add rows for both readouts (long format)
                rows.append({
                    "campaign_id": "DEMO",
                    "cell_line": cell,
                    "compound": stressor,
                    "dose_uM": dose,
                    "time_h": 24.0,
                    "readout_name": "viability",
                    "readout_value": viability + np.random.normal(0, 0.05),
                    "plate_id": "P1",
                    "replicate": 1
                })
                rows.append({
                    "campaign_id": "DEMO",
                    "cell_line": cell,
                    "compound": stressor,
                    "dose_uM": dose,
                    "time_h": 24.0,
                    "readout_name": "posh_score",
                    "readout_value": posh_score + np.random.normal(0, 0.05),
                    "plate_id": "P1",
                    "replicate": 1
                })
                
    return pd.DataFrame(rows)

def main():
    print("Generating synthetic data...")
    df = create_synthetic_data()
    
    print("Building LabWorldModel...")
    wm = LabWorldModel.empty()
    wm.add_experiments(df)
    
    print("Building Posterior (Belief State)...")
    # We want to model BOTH viability and POSH score
    posterior = DoseResponsePosterior.from_world(
        wm, 
        campaign_id="DEMO", 
        readout_names=["viability", "posh_score"]
    )
    
    print(f"Fitted {len(posterior.gp_models)} GP slices.")
    
    # Define a goal: Find a dose of TBHP in U2OS where POSH score is 0.4-0.6
    goal = StressWindowGoal(
        cell_line="U2OS",
        stressor="TBHP",
        readout="posh_score",
        min_val=0.4,
        max_val=0.6
    )
    
    print(f"Goal: {goal.description()}")
    
    campaign = Campaign(goal, max_cycles=3)
    
    print("\n--- Running Campaign ---")
    
    # Run one cycle
    proposals = campaign.run_cycle(posterior, n_experiments=5)
    
    print(f"Cycle 1 proposed {len(proposals)} experiments:")
    print(proposals[["cell_line", "compound", "readout", "dose_uM", "priority_score"]])
    
    # Check if goal is met (it might be already met by initial data)
    if campaign.check_goal(posterior):
        print(f"\nSUCCESS! Goal met by dose: {goal.met_by_dose:.4f} uM")
    else:
        print("\nGoal not yet met.")
        
    print("\n--- Portfolio Summary ---")
    summary = summarize_portfolio(posterior)
    print(summary)

if __name__ == "__main__":
    main()
