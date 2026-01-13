import pandas as pd
from typing import List
from cell_os.titration_loop import TitrationReport
from cell_os.posh.lv_moi import ScreenConfig, ScreenSimulator, LVTransductionModel, TiterPosterior

def generate_screen_manifest(reports: List[TitrationReport], config: ScreenConfig):
    print("\n📦 GENERATING FINAL SCREEN MANIFEST")
    print("="*90)
    print(f"{'Cell Line':<15} | {'Strategy':<15} | {'Vol/Flask':<15} | {'Est. BFP':<10} | {'Notes':<25}")
    print("-" * 90)

    for r in reports:
        strategy = "Standard"
        final_vol = r.final_vol
        est_bfp = config.target_bfp
        note = "Ready"
        
        # 1. Handle Success
        if r.status == "GO":
            pass # Keep defaults
            
        # 2. Handle "NO GO" -> Attempt Dilution Rescue
        else:
            # We assume NO GO is usually due to high sensitivity (Steep Slope).
            # Let's try a virtual 1:10 dilution.
            
            # Virtual Pre-dilution of the Posterior
            diluted_posterior = TiterPosterior(
                grid_titer=r.model.posterior.grid_titer / 10.0,
                probs=r.model.posterior.probs,
                ci_95=(r.model.posterior.ci_95[0]/10, r.model.posterior.ci_95[1]/10)
            )
            
            diluted_model = LVTransductionModel(
                cell_line=f"{r.cell_line} (1:10)",
                titer_tu_ul=r.model.titer_tu_ul / 10.0,
                max_infectivity=r.model.max_infectivity,
                cells_per_well=r.model.cells_per_well,
                r_squared=r.model.r_squared,
                posterior=diluted_posterior
            )
            
            # Recalculate PoS with reduced pipetting error (2% instead of 5%)
            # because we are now pipetting >1mL instead of ~100uL
            diluted_config = ScreenConfig(
                num_guides=config.num_guides,
                coverage_target=config.coverage_target,
                target_bfp=config.target_bfp,
                bfp_tolerance=config.bfp_tolerance,
                cell_counting_error=config.cell_counting_error,
                pipetting_error=0.02 # <--- The Benefit of Dilution
            )
            
            sim = ScreenSimulator(diluted_model, diluted_config)
            new_pos = sim.get_probability_of_success()
            
            if new_pos > 0.90:
                strategy = "Dilute 1:10"
                final_vol = sim.target_vol_ul
                note = f"Rescued (PoS {r.final_pos:.1%} -> {new_pos:.1%})"
            else:
                strategy = "REJECT"
                final_vol = 0.0
                note = f"Unstable (PoS {new_pos:.1%})"

        # Print Row
        print(f"{r.cell_line:<15} | {strategy:<15} | {final_vol:<10.2f} µL    | {est_bfp:.0%}       | {note:<25}")