"""
POSH Screen Simulation Wrapper.

Simulates the execution of a POSH screen from a banked library.
Generates synthetic Cell Painting morphological phenotype data.
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA

from cell_os.workflows import Workflow, WorkflowBuilder
from cell_os.unit_ops.parametric import ParametricOps
from cell_os.unit_ops.base import VesselLibrary
from cell_os.inventory import Inventory
from cell_os.cellpaint_panels import get_posh_cellpaint_panel, CellPaintPanel


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
    raw_measurements: pd.DataFrame  # Segmentation outputs
    channel_intensities: pd.DataFrame  # Raw channel data (what microscope sees)
    embeddings: pd.DataFrame  # NEW: High-dimensional embeddings (128-d)
    projection_2d: pd.DataFrame  # NEW: 2D coordinates (PCA/UMAP)
    
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


def _get_channel_baseline_intensities(cell_line: str) -> dict:
    """
    Get baseline channel intensities for untreated cells.
    
    These represent what the microscope actually sees (fluorescence intensity).
    Units are arbitrary fluorescence units (AFU).
    
    Args:
        cell_line: Cell line name
        
    Returns:
        Dict with baseline intensities for each channel
    """
    baselines = {
        "U2OS": {
            "Hoechst": 28000,      # Nuclear DNA
            "ConA": 15000,         # ER
            "Phalloidin": 12000,   # Actin
            "WGA": 10000,          # Golgi/membrane
            "MitoProbe": 35000,    # Mitochondria
        },
        "A549": {
            "Hoechst": 27000,
            "ConA": 14000,
            "Phalloidin": 11000,
            "WGA": 9500,
            "MitoProbe": 33000,
        },
        "HepG2": {
            "Hoechst": 29000,
            "ConA": 16000,
            "Phalloidin": 13000,
            "WGA": 11000,
            "MitoProbe": 36000,
        },
        "iPSC": {
            "Hoechst": 30000,      # Higher nuclear staining (dense chromatin)
            "ConA": 13000,
            "Phalloidin": 10000,
            "WGA": 8500,
            "MitoProbe": 32000,
        }
    }
    return baselines.get(cell_line, baselines["U2OS"])


def _apply_treatment_to_channels(baseline: dict, treatment: str, dose_uM: float) -> dict:
    """
    Apply treatment effects to channel intensities.
    
    Simulates how different treatments affect dye fluorescence.
    
    Args:
        baseline: Baseline channel intensities
        treatment: Treatment name
        dose_uM: Treatment dose
        
    Returns:
        Modified channel intensities
    """
    modified = baseline.copy()
    
    if treatment == "tBHP":  # Oxidative stress
        # Mitochondria: depolarization reduces intensity
        modified["MitoProbe"] = baseline["MitoProbe"] * 0.7
        # Nucleus: slight condensation increases intensity
        modified["Hoechst"] = baseline["Hoechst"] * 1.15
        # ER: moderate stress response
        modified["ConA"] = baseline["ConA"] * 1.1
        # Actin: slight disruption
        modified["Phalloidin"] = baseline["Phalloidin"] * 0.9
        # Golgi: mild effect
        modified["WGA"] = baseline["WGA"] * 0.95
        
    elif treatment == "Staurosporine":  # Apoptosis
        # Mitochondria: severe depolarization
        modified["MitoProbe"] = baseline["MitoProbe"] * 0.5
        # Nucleus: strong condensation
        modified["Hoechst"] = baseline["Hoechst"] * 1.6
        # ER: stress response
        modified["ConA"] = baseline["ConA"] * 1.2
        # Actin: major disruption (rounding)
        modified["Phalloidin"] = baseline["Phalloidin"] * 0.6
        # Golgi: fragmentation
        modified["WGA"] = baseline["WGA"] * 0.7
        
    elif treatment == "Tunicamycin":  # ER stress
        # ER: strong stress response (swelling, increased staining)
        modified["ConA"] = baseline["ConA"] * 1.4
        # Mitochondria: moderate effect
        modified["MitoProbe"] = baseline["MitoProbe"] * 0.85
        # Nucleus: mild stress
        modified["Hoechst"] = baseline["Hoechst"] * 1.07
        # Golgi: major disruption (ER-Golgi connection)
        modified["WGA"] = baseline["WGA"] * 0.8
        # Actin: mild disruption
        modified["Phalloidin"] = baseline["Phalloidin"] * 0.9
    
    return modified


def _segment_nucleus_from_hoechst(hoechst_intensity: float, cell_line: str) -> dict:
    """
    Simulate nuclear segmentation from Hoechst channel.
    
    In real Cell Painting, CellProfiler segments nuclei from DAPI/Hoechst.
    We simulate the outputs of that segmentation.
    
    Args:
        hoechst_intensity: Hoechst channel intensity
        cell_line: Cell line name
        
    Returns:
        Dict with nuclear measurements
    """
    # Get baseline nuclear size for this cell line
    baseline_areas = {
        "U2OS": 160,
        "A549": 120,
        "HepG2": 105,
        "iPSC": 85
    }
    baseline_area = baseline_areas.get(cell_line, 160)
    
    # Higher Hoechst intensity suggests condensation → smaller area
    # Lower intensity suggests decondensation → larger area
    intensity_factor = hoechst_intensity / 28000  # Normalize to ~1.0 at baseline
    area_modifier = 1.0 / (intensity_factor ** 0.3)  # Inverse relationship
    
    nucleus_area = baseline_area * area_modifier
    
    # Derive other nuclear metrics from area
    nucleus_perimeter = 2 * np.pi * np.sqrt(nucleus_area / np.pi) * (1 + np.random.normal(0, 0.05))
    
    # Form factor: how circular (1.0 = perfect circle)
    # Condensation/stress reduces circularity
    form_factor = 0.85 * (1.0 / intensity_factor ** 0.1) + np.random.normal(0, 0.03)
    form_factor = np.clip(form_factor, 0.4, 0.95)
    
    # Eccentricity: elongation (0 = circle, 1 = line)
    eccentricity = 0.25 + (1.0 - form_factor) * 0.4 + np.random.normal(0, 0.05)
    eccentricity = np.clip(eccentricity, 0.1, 0.8)
    
    return {
        "Nucleus_Area": max(50, nucleus_area + np.random.normal(0, nucleus_area * 0.1)),
        "Nucleus_Perimeter": max(20, nucleus_perimeter),
        "Nucleus_Mean_Intensity": hoechst_intensity,
        "Nucleus_Form_Factor": form_factor,
        "Nucleus_Eccentricity": eccentricity
    }


def _segment_mitochondria_from_mitoprobe(mitoprobe_intensity: float, cell_line: str) -> dict:
    """
    Simulate mitochondrial segmentation from MitoProbe channel.
    
    Args:
        mitoprobe_intensity: MitoProbe channel intensity
        cell_line: Cell line name
        
    Returns:
        Dict with mitochondrial measurements
    """
    # Lower intensity = dysfunctional mito = more fragmentation
    # Higher intensity = healthy mito = tubular network
    
    intensity_factor = mitoprobe_intensity / 35000  # Normalize
    
    # Object count: inverse relationship with health
    # Healthy = few large objects, Fragmented = many small objects
    baseline_objects = 20
    object_count = baseline_objects * (1.0 / intensity_factor ** 0.8) + np.random.normal(0, 3)
    object_count = int(max(5, object_count))
    
    # Total area: reduces with dysfunction/loss
    baseline_area = 10000
    mito_area = baseline_area * (intensity_factor ** 0.5) + np.random.normal(0, 1000)
    mito_area = max(2000, mito_area)
    
    # Texture variance: increases with heterogeneity/dysfunction
    baseline_texture = 800
    texture = baseline_texture * (1.0 / intensity_factor ** 0.6) + np.random.normal(0, 150)
    texture = max(300, texture)
    
    return {
        "Mito_Mean_Intensity": mitoprobe_intensity,
        "Mito_Object_Count": object_count,
        "Mito_Total_Area": mito_area,
        "Mito_Texture_Variance": texture
    }


def _generate_embeddings(df_raw: pd.DataFrame, n_components: int = 128, random_seed: int = 42) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Generate synthetic deep learning embeddings from raw measurements.
    
    Simulates the output of a Deep Learning model (e.g. DINO/ResNet) processing the images.
    
    Args:
        df_raw: DataFrame with raw measurements (channels + segmentation)
        n_components: Dimension of embedding space
        random_seed: Random seed
        
    Returns:
        Tuple of (embeddings DataFrame, 2D projection DataFrame)
    """
    np.random.seed(random_seed)
    
    # 1. Select numeric features for embedding
    # We use both channel intensities and derived metrics
    # Filter out non-numeric or derived score columns to avoid leakage/duplication
    feature_cols = [c for c in df_raw.columns if c not in ["Gene", "ER_Stress_Score", "Fragmentation_Index", "Nuclear_Condensation", "Nuclear_Shape_Irregularity"] and pd.api.types.is_numeric_dtype(df_raw[c])]
    
    if not feature_cols:
        # Fallback if something goes wrong
        return pd.DataFrame(), pd.DataFrame()
        
    # 2. Normalize features (StandardScaler)
    X = df_raw[feature_cols].values
    scaler = StandardScaler()
    try:
        X_scaled = scaler.fit_transform(X)
    except:
        X_scaled = X # Fallback
    
    # 3. Project to high-dimensional space (Random Projection)
    # This simulates the "black box" transformation of a neural network
    # We create a random projection matrix (n_features x n_components)
    n_features = X_scaled.shape[1]
    projection_matrix = np.random.normal(0, 1.0 / np.sqrt(n_features), (n_features, n_components))
    
    embeddings = X_scaled @ projection_matrix
    
    # Add some non-linearity (ReLU-like)
    embeddings = np.maximum(0, embeddings)
    
    # Add noise to simulate biological variation captured by DL but not by our explicit features
    embeddings += np.random.normal(0, 0.05, embeddings.shape)
    
    # Create DataFrame
    embed_cols = [f"DIM_{i+1}" for i in range(n_components)]
    df_embeddings = pd.DataFrame(embeddings, columns=embed_cols)
    df_embeddings.insert(0, "Gene", df_raw["Gene"])
    
    # 4. Compute 2D projection (PCA) for visualization
    # In real life we'd use UMAP, but PCA is faster and robust for this simulation
    # It will naturally separate the clusters we created
    pca = PCA(n_components=2)
    coords = pca.fit_transform(embeddings)
    
    df_proj = pd.DataFrame(coords, columns=["UMAP_1", "UMAP_2"]) # Label as UMAP for familiarity
    df_proj.insert(0, "Gene", df_raw["Gene"])
    
    return df_embeddings, df_proj


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
        
        
        # 2. Simulate Cell Painting Channels (what microscope sees)
        genes = [f"GENE_{i:04d}" for i in range(library_size)]
        
        # Get panel (POSH uses MitoProbe)
        panel = get_posh_cellpaint_panel(include_mitoprobe=True)
        
        # Get baseline channel intensities for this cell line
        baseline_channels = _get_channel_baseline_intensities(cell_line)
        
        # Apply treatment effects to channels
        treated_channels = _apply_treatment_to_channels(baseline_channels, treatment, dose_uM)
        
        # Generate channel data for each gene
        channel_data = []
        raw_data = []
        
        for gene in genes:
            # Simulate channel intensities (with biological noise)
            hoechst = np.random.normal(treated_channels["Hoechst"], treated_channels["Hoechst"] * 0.1)
            cona = np.random.normal(treated_channels["ConA"], treated_channels["ConA"] * 0.12)
            phalloidin = np.random.normal(treated_channels["Phalloidin"], treated_channels["Phalloidin"] * 0.1)
            wga = np.random.normal(treated_channels["WGA"], treated_channels["WGA"] * 0.12)
            mitoprobe = np.random.normal(treated_channels["MitoProbe"], treated_channels["MitoProbe"] * 0.15)
            
            channel_data.append({
                "Gene": gene,
                "Hoechst": max(0, hoechst),
                "ConA": max(0, cona),
                "Phalloidin": max(0, phalloidin),
                "WGA": max(0, wga),
                "MitoProbe": max(0, mitoprobe)
            })
            
            # 3. Derive segmentation outputs from channels
            # Segment nucleus from Hoechst
            nuclear_metrics = _segment_nucleus_from_hoechst(hoechst, cell_line)
            
            # Segment mitochondria from MitoProbe
            mito_metrics = _segment_mitochondria_from_mitoprobe(mitoprobe, cell_line)
            
            # Combine all measurements
            raw_data.append({
                "Gene": gene,
                # Nuclear (from Hoechst)
                **nuclear_metrics,
                # Mitochondrial (from MitoProbe)
                **mito_metrics
            })
        
        df_channels = pd.DataFrame(channel_data)
        df_raw = pd.DataFrame(raw_data)
        
        # Calculate baseline metrics for reference (using same logic as loop)
        # This represents the "average" treated cell without genetic perturbation
        baseline_nuc = _segment_nucleus_from_hoechst(treated_channels["Hoechst"], cell_line)
        baseline_mito = _segment_mitochondria_from_mitoprobe(treated_channels["MitoProbe"], cell_line)
        baseline_metrics = {**baseline_nuc, **baseline_mito}
        
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
        
        # 4. Generate Embeddings (Deep Learning Simulation)
        # Combine channel data and segmentation data for embedding generation
        df_combined = pd.merge(df_channels, df_raw, on="Gene")
        df_embeddings, df_proj = _generate_embeddings(df_combined, random_seed=random_seed)

        # 5. Calculate Derived Features from Raw Measurements
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
        # Select which feature to use for analysis
        if feature == "mitochondrial_fragmentation":
            derived_values = df_raw["Fragmentation_Index"].values
            baseline_value = _calculate_fragmentation_from_raw(
                baseline_metrics["Mito_Object_Count"],
                baseline_metrics["Mito_Total_Area"]
            )
        elif feature == "nuclear_size":
            derived_values = df_raw["Nucleus_Area"].values
            baseline_value = baseline_metrics["Nucleus_Area"]
        elif feature == "er_stress_score":
            # Composite score: Texture Variance + Nuclear Intensity
            # Normalize to baseline
            mito_tex_norm = df_raw["Mito_Texture_Variance"] / baseline_metrics["Mito_Texture_Variance"]
            nuc_int_norm = df_raw["Nucleus_Mean_Intensity"] / baseline_metrics["Nucleus_Mean_Intensity"]
            
            # ER Stress Score = (Texture + Intensity) / 2
            df_raw["ER_Stress_Score"] = (mito_tex_norm + nuc_int_norm) / 2.0
            derived_values = df_raw["ER_Stress_Score"].values
            baseline_value = 1.0
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
            channel_intensities=df_channels,
            embeddings=df_embeddings,
            projection_2d=df_proj,
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
            channel_intensities=pd.DataFrame(),
            embeddings=pd.DataFrame(),
            projection_2d=pd.DataFrame(),
            success=False,
            error_message=str(e)
        )
