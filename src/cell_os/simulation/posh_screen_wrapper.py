"""
POSH Screen Simulation Wrapper.

Simulates the execution of a POSH screen from a banked library.
Generates synthetic Cell Painting morphological phenotype data.
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from cell_os.workflows import Workflow, WorkflowBuilder
from cell_os.unit_ops.parametric import ParametricOps
from cell_os.unit_ops.base import VesselLibrary
from cell_os.inventory import Inventory


@dataclass
class POSHScreenResult:
    """Result of a POSH screen simulation."""
    cell_line: str
    treatment: str
    dose_uM: float
    library_size: int
    selected_feature: str
    
    # Results
    hit_list: pd.DataFrame
    volcano_data: pd.DataFrame
    raw_measurements: pd.DataFrame  # NEW: Raw imaging data
    
    # Operational
    workflow: Optional[Workflow] = None
    success: bool = True
    error_message: str = ""


# Cell Painting feature definitions
CELL_PAINTING_FEATURES = {
    "mitochondrial_fragmentation": {
        "name": "Mitochondrial Fragmentation",
        "unit": "Fragmentation Index",
        "description": "Degree of mitochondrial network fragmentation (0=tubular, 1=fragmented)"
    },
    "nuclear_size": {
        "name": "Nuclear Size",
        "unit": "µm²",
        "description": "Average nuclear area"
    },
    "er_stress_score": {
        "name": "ER Stress Score",
        "unit": "Stress Index",
        "description": "ER morphology disruption score (0=normal, 1=severe stress)"
    },
    "cell_count": {
        "name": "Cell Count",
        "unit": "Cells/Well",
        "description": "Number of viable cells (viability proxy)"
    }
}


def _get_treatment_raw_measurement_effects(treatment: str) -> dict:
    """
    Get baseline effects of treatment on raw imaging measurements.
    
    Returns dict with mean and std for each raw measurement.
    """
    treatment_effects = {
        "tBHP": {  # Oxidative stress
            # Mitochondria
            "mito_mean_intensity": (25000, 5000),  # Reduced (depolarization)
            "mito_object_count": (45, 10),  # High (fragmentation)
            "mito_total_area": (8000, 1500),  # Slightly reduced
            "mito_texture_variance": (1200, 300),  # High (heterogeneous)
            # Nucleus
            "nucleus_area": (180, 30),  # Slight shrinkage
            "nucleus_perimeter": (55, 8),
            "nucleus_mean_intensity": (32000, 4000),  # Moderate condensation
            "nucleus_form_factor": (0.75, 0.1),  # Slightly irregular
            "nucleus_eccentricity": (0.4, 0.1),  # Slight elongation
        },
        "Staurosporine": {  # Apoptosis
            # Mitochondria
            "mito_mean_intensity": (18000, 4000),  # Very low (strong depolarization)
            "mito_object_count": (40, 8),  # High (fragmentation)
            "mito_total_area": (6000, 1200),  # Reduced (loss)
            "mito_texture_variance": (1000, 250),
            # Nucleus
            "nucleus_area": (120, 25),  # Strong shrinkage (apoptosis)
            "nucleus_perimeter": (42, 7),
            "nucleus_mean_intensity": (45000, 5000),  # High condensation
            "nucleus_form_factor": (0.55, 0.12),  # Very irregular (fragmentation)
            "nucleus_eccentricity": (0.65, 0.12),  # Elongated/irregular
        },
        "Tunicamycin": {  # ER stress
            # Mitochondria
            "mito_mean_intensity": (30000, 5000),  # Less affected
            "mito_object_count": (35, 8),  # Moderate fragmentation
            "mito_total_area": (7500, 1500),
            "mito_texture_variance": (1300, 300),  # High (stress response)
            # Nucleus
            "nucleus_area": (190, 30),  # Slight swelling (stress)
            "nucleus_perimeter": (56, 8),
            "nucleus_mean_intensity": (30000, 4000),  # Mild condensation
            "nucleus_form_factor": (0.78, 0.08),  # Mostly regular
            "nucleus_eccentricity": (0.35, 0.08),  # Mostly round
        }
    }
    
    # Default (untreated baseline)
    default = {
        # Mitochondria
        "mito_mean_intensity": (35000, 4000),
        "mito_object_count": (20, 5),  # Tubular network
        "mito_total_area": (10000, 2000),
        "mito_texture_variance": (800, 200),
        # Nucleus
        "nucleus_area": (200, 30),  # Healthy size
        "nucleus_perimeter": (58, 8),
        "nucleus_mean_intensity": (28000, 3000),  # Normal chromatin
        "nucleus_form_factor": (0.85, 0.05),  # Round/regular
        "nucleus_eccentricity": (0.25, 0.08),  # Nearly circular
    }
    
    return treatment_effects.get(treatment, default)


def _calculate_fragmentation_from_raw(mito_object_count: float, mito_total_area: float) -> float:
    """
    Calculate fragmentation index from raw measurements.
    
    Formula: object_count / (total_area / 100)
    - Healthy tubular network: ~20 objects / 100 area units = 0.2
    - Fragmented: ~45 objects / 80 area units = 0.56
    """
    if mito_total_area == 0:
        return 0.0
    return mito_object_count / (mito_total_area / 100.0)


def _calculate_nuclear_condensation(nucleus_mean_intensity: float, nucleus_form_factor: float) -> float:
    """
    Calculate nuclear condensation index from raw measurements.
    
    Combines intensity (chromatin condensation) and shape (regularity).
    Higher intensity + lower form factor = more condensed (apoptotic).
    
    Normalized to 0-1 scale.
    """
    # Normalize intensity (baseline ~28000, condensed ~45000)
    intensity_norm = min(1.0, (nucleus_mean_intensity - 20000) / 30000)
    
    # Invert form factor (lower = more irregular = more condensed)
    shape_score = 1.0 - nucleus_form_factor
    
    # Combine (weighted average)
    condensation = (intensity_norm * 0.7) + (shape_score * 0.3)
    return max(0.0, min(1.0, condensation))


def _calculate_nuclear_shape_irregularity(nucleus_form_factor: float, nucleus_eccentricity: float) -> float:
    """
    Calculate nuclear shape irregularity from raw measurements.
    
    Combines form factor (circularity) and eccentricity (elongation).
    Lower form factor + higher eccentricity = more irregular.
    
    Normalized to 0-1 scale.
    """
    # Invert form factor (1.0 = perfect circle, lower = irregular)
    irregularity_from_form = 1.0 - nucleus_form_factor
    
    # Eccentricity (0 = circle, 1 = line)
    irregularity_from_ecc = nucleus_eccentricity
    
    # Combine
    irregularity = (irregularity_from_form * 0.6) + (irregularity_from_ecc * 0.4)
    return max(0.0, min(1.0, irregularity))


def simulate_posh_screen(
    cell_line: str,
    treatment: str,
    dose_uM: float,
    library_size: int = 1000,
    coverage: int = 500,
    num_replicates: int = 3,
    feature: str = "mitochondrial_fragmentation",
    random_seed: int = 42
) -> POSHScreenResult:
    """
    Simulate a POSH screen execution with Cell Painting phenotyping.
    
    Args:
        cell_line: Cell line name (e.g., "A549")
        treatment: Treatment name (e.g., "tBHP")
        dose_uM: Treatment dose in uM
        library_size: Number of genes in library
        coverage: Cells per gene per replicate
        num_replicates: Number of biological replicates
        feature: Morphological feature to analyze
        random_seed: Random seed
        
    Returns:
        POSHScreenResult with synthetic Cell Painting data and workflow
    """
    try:
        np.random.seed(random_seed)
        
        # 1. Build Workflow (for resource tracking)
        inv = Inventory(pricing_path="data/raw/pricing.yaml")
        vessels = VesselLibrary()
        ops = ParametricOps(vessels, inv)
        builder = WorkflowBuilder(ops)
        
        workflow = builder.build_posh_screen_from_bank(
            cell_line=cell_line,
            treatment=treatment,
            dose_uM=dose_uM,
            num_replicates=num_replicates,
            library_size=library_size,
            coverage=coverage
        )
        
        # 2. Generate Raw Imaging Measurements
        # Generate gene names
        genes = [f"GENE_{i:04d}" for i in range(library_size)]
        
        # Get baseline raw measurements for this treatment
        baseline_raw = _get_treatment_raw_measurement_effects(treatment)
        
        # Generate raw measurements for each gene
        raw_data = []
        for gene in genes:
            # Mitochondria measurements
            mito_intensity = np.random.normal(
                baseline_raw["mito_mean_intensity"][0],
                baseline_raw["mito_mean_intensity"][1]
            )
            mito_obj_count = int(np.random.normal(
                baseline_raw["mito_object_count"][0],
                baseline_raw["mito_object_count"][1]
            ))
            mito_area = np.random.normal(
                baseline_raw["mito_total_area"][0],
                baseline_raw["mito_total_area"][1]
            )
            mito_texture = np.random.normal(
                baseline_raw["mito_texture_variance"][0],
                baseline_raw["mito_texture_variance"][1]
            )
            
            # Nuclear measurements
            nucleus_area = np.random.normal(
                baseline_raw["nucleus_area"][0],
                baseline_raw["nucleus_area"][1]
            )
            nucleus_perimeter = np.random.normal(
                baseline_raw["nucleus_perimeter"][0],
                baseline_raw["nucleus_perimeter"][1]
            )
            nucleus_intensity = np.random.normal(
                baseline_raw["nucleus_mean_intensity"][0],
                baseline_raw["nucleus_mean_intensity"][1]
            )
            nucleus_form_factor = np.random.normal(
                baseline_raw["nucleus_form_factor"][0],
                baseline_raw["nucleus_form_factor"][1]
            )
            nucleus_eccentricity = np.random.normal(
                baseline_raw["nucleus_eccentricity"][0],
                baseline_raw["nucleus_eccentricity"][1]
            )
            
            raw_data.append({
                "Gene": gene,
                # Mitochondria
                "Mito_Mean_Intensity": max(0, mito_intensity),
                "Mito_Object_Count": max(1, mito_obj_count),
                "Mito_Total_Area": max(100, mito_area),
                "Mito_Texture_Variance": max(0, mito_texture),
                # Nucleus
                "Nucleus_Area": max(50, nucleus_area),
                "Nucleus_Perimeter": max(20, nucleus_perimeter),
                "Nucleus_Mean_Intensity": max(0, nucleus_intensity),
                "Nucleus_Form_Factor": max(0.1, min(1.0, nucleus_form_factor)),
                "Nucleus_Eccentricity": max(0.0, min(1.0, nucleus_eccentricity))
            })
        
        df_raw = pd.DataFrame(raw_data)
        
        # Inject gene-specific modulators (hits)
        num_hits = int(library_size * 0.05)  # 5% hits
        hit_indices = np.random.choice(library_size, num_hits, replace=False)
        
        for idx in hit_indices:
            if np.random.random() < 0.5:
                # Suppressor: reduces stress phenotypes
                # Mitochondria: less fragmentation
                df_raw.loc[idx, "Mito_Object_Count"] *= 0.5
                df_raw.loc[idx, "Mito_Total_Area"] *= 1.3
                df_raw.loc[idx, "Mito_Mean_Intensity"] *= 1.2
                # Nucleus: less condensation/irregularity
                df_raw.loc[idx, "Nucleus_Mean_Intensity"] *= 0.85
                df_raw.loc[idx, "Nucleus_Form_Factor"] *= 1.1
                df_raw.loc[idx, "Nucleus_Eccentricity"] *= 0.8
            else:
                # Enhancer: amplifies stress phenotypes
                # Mitochondria: more fragmentation
                df_raw.loc[idx, "Mito_Object_Count"] *= 1.8
                df_raw.loc[idx, "Mito_Total_Area"] *= 0.7
                df_raw.loc[idx, "Mito_Mean_Intensity"] *= 0.8
                # Nucleus: more condensation/irregularity
                df_raw.loc[idx, "Nucleus_Mean_Intensity"] *= 1.15
                df_raw.loc[idx, "Nucleus_Form_Factor"] *= 0.85
                df_raw.loc[idx, "Nucleus_Eccentricity"] *= 1.2
        
        # 3. Calculate Derived Features from Raw Measurements
        # Mitochondrial fragmentation
        df_raw["Fragmentation_Index"] = df_raw.apply(
            lambda row: _calculate_fragmentation_from_raw(
                row["Mito_Object_Count"],
                row["Mito_Total_Area"]
            ),
            axis=1
        )
        
        # Nuclear condensation
        df_raw["Nuclear_Condensation"] = df_raw.apply(
            lambda row: _calculate_nuclear_condensation(
                row["Nucleus_Mean_Intensity"],
                row["Nucleus_Form_Factor"]
            ),
            axis=1
        )
        
        # Nuclear shape irregularity
        df_raw["Nuclear_Shape_Irregularity"] = df_raw.apply(
            lambda row: _calculate_nuclear_shape_irregularity(
                row["Nucleus_Form_Factor"],
                row["Nucleus_Eccentricity"]
            ),
            axis=1
        )
        
        # Select which feature to use for analysis
        if feature == "mitochondrial_fragmentation":
            derived_values = df_raw["Fragmentation_Index"].values
            baseline_value = _calculate_fragmentation_from_raw(
                baseline_raw["mito_object_count"][0],
                baseline_raw["mito_total_area"][0]
            )
        elif feature == "nuclear_size":
            derived_values = df_raw["Nucleus_Area"].values
            baseline_value = baseline_raw["nucleus_area"][0]
        else:
            # For other features, use placeholder (not implemented yet)
            derived_values = np.random.normal(0, 0.5, library_size)
            baseline_value = 0.0
        
        # Calculate p-values based on deviation from baseline
        deviation_from_baseline = np.abs(derived_values - baseline_value)
        log_p = deviation_from_baseline * 5.0 + np.random.exponential(0.8, library_size)
        p_values = 10**(-log_p)
        p_values = np.clip(p_values, 1e-10, 1.0)
        
        # Create volcano plot DataFrame
        df_volcano = pd.DataFrame({
            "Gene": genes,
            "Log2FoldChange": derived_values,
            "P_Value": p_values,
            "NegLog10P": -np.log10(p_values)
        })
        
        # Identify hits (significant deviation from baseline)
        threshold = 0.15  # Threshold for meaningful effect
        df_volcano["IsHit"] = (df_volcano["P_Value"] < 0.05) & \
                              (np.abs(df_volcano["Log2FoldChange"] - baseline_value) > threshold)
        
        # Categorize hits
        df_volcano["Category"] = "Non-targeting"
        df_volcano.loc[df_volcano["IsHit"] & (df_volcano["Log2FoldChange"] > baseline_value), "Category"] = "Enhancer"
        df_volcano.loc[df_volcano["IsHit"] & (df_volcano["Log2FoldChange"] < baseline_value), "Category"] = "Suppressor"
        
        hit_list = df_volcano[df_volcano["IsHit"]].sort_values("P_Value")
        
        return POSHScreenResult(
            cell_line=cell_line,
            treatment=treatment,
            dose_uM=dose_uM,
            library_size=library_size,
            selected_feature=feature,
            hit_list=hit_list,
            volcano_data=df_volcano,
            raw_measurements=df_raw,
            workflow=workflow,
            success=True
        )
        
    except Exception as e:
        return POSHScreenResult(
            cell_line=cell_line,
            treatment=treatment,
            dose_uM=dose_uM,
            library_size=library_size,
            selected_feature=feature,
            hit_list=pd.DataFrame(),
            volcano_data=pd.DataFrame(),
            raw_measurements=pd.DataFrame(),
            success=False,
            error_message=str(e)
        )
