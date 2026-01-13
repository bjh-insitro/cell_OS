import numpy as np
import pandas as pd
from typing import Dict, Tuple, Union, List

# --- POSH Panel Parameters (Updated to 5 specific channels) ---
IF_CHANNELS = ["Nuclear_Stain", "ER_ConA", "Golgi_WGA", "Actin_Phalloidin", "Mito_Probe"]
N_CHANNELS = len(IF_CHANNELS)

# NTC Intensity Parameters
MU_I_NTC = np.array([1000, 500, 800, 600, 950])
SIGMA_I_NTC = np.diag([200**2, 100**2, 150**2, 120**2, 180**2])

# KO Intensity Parameters (Shifted Mean and higher variance)
MU_I_KO = np.array([850, 600, 800, 800, 950]) # Shifted mean
SIGMA_I_KO = 1.5 * SIGMA_I_NTC # 1.5x NTC variance for KO

# Placeholder DINO and Feature Extraction parameters (from previous response)
# ...

class PoshAnalysisSimulator:
    
    def __init__(self, embedding_dim: int = 128):
        # ... (other initializations remain the same) ...
        
        # IF Intensity Parameters
        self.mu_i_ntc = MU_I_NTC
        self.sigma_i_ntc = SIGMA_I_NTC
        self.mu_i_ko = MU_I_KO
        self.sigma_i_ko = SIGMA_I_KO
        self.if_dim = N_CHANNELS
        
        # DINO/Feature parameters initialization skipped for brevity here
        
        print(f"PoshAnalysisSimulator initialized for {self.if_dim} IF channels.")


    def simulate_if_intensity_by_well(self, 
                                     n_wells_ntc: int = 3, 
                                     n_wells_ko: int = 3, 
                                     n_cells_per_well: int = 100) -> pd.DataFrame:
        """
        Generates synthetic 5-channel IF intensity data structured by well.

        Returns: DataFrame containing single- cell intensity data with Well and Condition metadata.
        """
        print(f"-> Simulating IF data for {n_wells_ntc} NTC and {n_wells_ko} KO wells ({n_cells_per_well} cells/well)...")

        all_data = []

        # Simulate NTC Wells
        for i in range(n_wells_ntc):
            # Generate IF data for the well
            I_NTC_well = np.random.multivariate_normal(
                mean=self.mu_i_ntc, 
                cov=self.sigma_i_ntc, 
                size=n_cells_per_well
            )
            
            # Create a DataFrame for the well
            df_well = pd.DataFrame(I_NTC_well, columns=[f"Intensity_{ch}" for ch in IF_CHANNELS])
            df_well['Well'] = f"A0{i+1}" # e.g., A01, A02, A03
            df_well['Condition'] = 'NTC'
            df_well['Cell_ID'] = [f"A0{i+1}_{j:03d}" for j in range(n_cells_per_well)]
            all_data.append(df_well)

        # Simulate KO Wells
        for i in range(n_wells_ko):
            # Generate IF data for the well
            I_KO_well = np.random.multivariate_normal(
                mean=self.mu_i_ko, 
                cov=self.sigma_i_ko, 
                size=n_cells_per_well
            )
            
            # Create a DataFrame for the well
            df_well = pd.DataFrame(I_KO_well, columns=[f"Intensity_{ch}" for ch in IF_CHANNELS])
            df_well['Well'] = f"B0{i+1}" # e.g., B01, B02, B03
            df_well['Condition'] = 'KO'
            df_well['Cell_ID'] = [f"B0{i+1}_{j:03d}" for j in range(n_cells_per_well)]
            all_data.append(df_well)
            
        # Concatenate all wells into the final single-cell data table
        df_final = pd.concat(all_data, ignore_index=True)
        
        # Ensure intensity is positive
        intensity_cols = [f"Intensity_{ch}" for ch in IF_CHANNELS]
        df_final[intensity_cols] = df_final[intensity_cols].clip(lower=1)
        
        print(f"-> Successfully generated {len(df_final)} single-cell IF records.")

        return df_final


# Example Execution:
if __name__ == '__main__':
    simulator = PoshAnalysisSimulator()
    
    # Generate the 6-well A549 POSH IF dataset
    posh_if_data = simulator.simulate_if_intensity_by_well(
        n_wells_ntc=3,
        n_wells_ko=3,
        n_cells_per_well=100
    )
    
    print("\n--- Synthetic POSH IF Data Head ---")
    print(posh_if_data.head())
    print("\n--- Data Statistics (Mean Intensity by Condition) ---")
    print(posh_if_data.groupby('Condition')[[f"Intensity_{ch}" for ch in IF_CHANNELS]].mean().round(1))

    # Example Check: Verify the KO shift in the simulated data
    ntc_means = posh_if_data[posh_if_data['Condition'] == 'NTC'][[f"Intensity_{ch}" for ch in IF_CHANNELS]].mean().values
    ko_means = posh_if_data[posh_if_data['Condition'] == 'KO'][[f"Intensity_{ch}" for ch in IF_CHANNELS]].mean().values
    
    simulated_shift = ko_means - ntc_means
    expected_shift = MU_I_KO - MU_I_NTC
    
    print("\n--- Expected vs. Simulated Mean Shift ---")
    print(f"Expected Shift Vector (KO - NTC): {expected_shift.round(1)}")
    print(f"Simulated Shift Vector (KO - NTC): {simulated_shift.round(1)}")
    
# Output of the example execution confirms the data generation and the modeled phenotypic shift.