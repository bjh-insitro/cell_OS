"""
POSH Screen Simulation Wrapper.

Simulates the execution of a POSH screen from a banked library.
Generates synthetic Cell Painting morphological phenotype data.
"""

import pandas as pd
import numpy as np
import math
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA

from cell_os.workflows import Workflow, WorkflowBuilder
from cell_os.unit_ops.parametric import ParametricOps
from cell_os.unit_ops.base import VesselLibrary
from cell_os.inventory import Inventory
from cell_os.cellpaint_panels import get_posh_cellpaint_panel, CellPaintPanel


# ===================================================================
# SIMULATION CONFIGURATION
# ===================================================================

# Channel normalization values for visualization (typical saturation points in AFU)
CHANNEL_MAX_VALUES = {
    "Hoechst": 45000,      # Nuclear DNA staining saturation
    "ConA": 25000,         # ER marker saturation  
    "Phalloidin": 20000,   # Actin staining saturation
    "WGA": 18000,          # Golgi/membrane marker saturation
    "MitoProbe": 50000,    # Mitochondrial probe saturation
}

# Cell line-specific nuclear size ranges (µm²)
# Based on literature values for typical morphology
NUCLEAR_SIZE_RANGES = {
    "U2OS": (120, 200),    # Osteosarcoma cells - large nuclei
    "A549": (90, 150),     # Lung carcinoma - medium nuclei
    "HepG2": (80, 130),    # Hepatocellular carcinoma - compact nuclei
    "iPSC": (60, 110),     # Induced pluripotent stem cells - small, dense nuclei
}

# Nuclear size baselines (center of range, µm²)
NUCLEAR_SIZE_BASELINES = {
    "U2OS": 160,
    "A549": 120,
    "HepG2": 105,
    "iPSC": 85,
}

# Embedding configuration
EMBEDDING_DIMENSIONS = 128                    # High-dimensional embedding space
EMBEDDING_PROJECTION_METHOD = "random_projection"  # Simulates neural network
PCA_COMPONENTS = 2                            # For 2D visualization (UMAP-like)

# MoA classification thresholds
MOA_ALIGNMENT_THRESHOLD = 0.3                 # Cosine similarity threshold for classification

# Hit injection parameters
HIT_RATE = 0.05                               # 5% of library are hits
SUPPRESSOR_PROBABILITY = 0.5                  # 50% of hits are suppressors, 50% enhancers

# Biological noise levels (coefficient of variation)
CHANNEL_NOISE_CV = {
    "Hoechst": 0.10,       # 10% CV for nuclear staining
    "ConA": 0.12,          # 12% CV for ER marker
    "Phalloidin": 0.10,    # 10% CV for actin
    "WGA": 0.12,           # 12% CV for Golgi
    "MitoProbe": 0.15,     # 15% CV for mitochondria (more variable)
}

# Statistical thresholds
P_VALUE_THRESHOLD = 0.05                      # Significance threshold for hit calling
LOG2FC_THRESHOLD = 1.0                        # Fold-change threshold for hit calling

# ===================================================================


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
    baseline_area = NUCLEAR_SIZE_BASELINES.get(cell_line, NUCLEAR_SIZE_BASELINES["U2OS"])
    
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


def generate_embeddings(df_raw: pd.DataFrame, n_components: int = EMBEDDING_DIMENSIONS, random_seed: int = 42) -> tuple[pd.DataFrame, pd.DataFrame]:
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
    
    # 4. Compute 2D projection using UMAP for visualization
    # UMAP preserves both local and global structure better than PCA
    # This creates more biologically meaningful clusters
    try:
        from umap import UMAP
        reducer = UMAP(
            n_neighbors=15,
            min_dist=0.1,
            n_components=2,
            metric='cosine',
            random_state=random_seed,
            verbose=False
        )
        coords = reducer.fit_transform(embeddings)
    except Exception as e:
        # Fallback to PCA if UMAP fails (e.g., too few samples)
        print(f"UMAP failed ({e}), falling back to PCA")
        pca = PCA(n_components=PCA_COMPONENTS)
        coords = pca.fit_transform(embeddings)
    
    df_proj = pd.DataFrame(coords, columns=["UMAP_1", "UMAP_2"])
    df_proj.insert(0, "Gene", df_raw["Gene"])
    
    return df_embeddings, df_proj


def simulate_screen_data(
    cell_line: str,
    treatment: str,
    dose_uM: float,
    library_size: int = 1000,
    random_seed: int = 42,
    add_batch_effects: bool = False,
    add_edge_effects: bool = False
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Simulate raw screen data (channels and segmentation).
    
    Args:
        cell_line: Cell line name
        treatment: Treatment name
        dose_uM: Dose in uM
        library_size: Number of genes
        random_seed: Random seed
        add_batch_effects: If True, adds plate-to-plate variation
        add_edge_effects: If True, adds edge well artifacts
        
    Returns:
        Tuple of (df_raw, df_channels)
    """
    np.random.seed(random_seed)
    
    # 1. Setup Library
    genes = [f"GENE_{i:04d}" for i in range(1, library_size + 1)]
    
    # Plate layout constants
    WELLS_PER_PLATE = 384
    ROWS = 16
    COLS = 24
    
    # Generate plate biases if needed
    num_plates = (library_size + WELLS_PER_PLATE - 1) // WELLS_PER_PLATE
    plate_biases = {}
    if add_batch_effects:
        for p in range(num_plates):
            # Random bias between 0.9 and 1.1 (10% variation)
            plate_biases[p] = np.random.uniform(0.9, 1.1)
    
    # 2. Simulate Channel Intensities (Microscopy)
    # Get baseline for this cell line
    baseline_channels = _get_channel_baseline_intensities(cell_line)
    
    # Apply treatment effects to channels
    treated_channels = _apply_treatment_to_channels(baseline_channels, treatment, dose_uM)
    
    channel_data = []
    raw_data = []
    
    for i, gene in enumerate(genes):
        # Calculate plate position
        plate = i // WELLS_PER_PLATE
        well = i % WELLS_PER_PLATE
        row = well // COLS
        col = well % COLS
        
        # Calculate technical multiplier
        multiplier = 1.0
        
        # Batch effect (plate-level)
        if add_batch_effects:
            multiplier *= plate_biases.get(plate, 1.0)
            
        # Edge effect (well-level)
        if add_edge_effects:
            is_edge = (row == 0 or row == ROWS - 1 or col == 0 or col == COLS - 1)
            if is_edge:
                # Edge wells often have higher evaporation / concentration -> higher intensity
                multiplier *= 1.15
        
        # Simulate channel intensities (with biological noise + technical artifacts)
        hoechst = np.random.normal(treated_channels["Hoechst"], treated_channels["Hoechst"] * CHANNEL_NOISE_CV["Hoechst"]) * multiplier
        cona = np.random.normal(treated_channels["ConA"], treated_channels["ConA"] * CHANNEL_NOISE_CV["ConA"]) * multiplier
        phalloidin = np.random.normal(treated_channels["Phalloidin"], treated_channels["Phalloidin"] * CHANNEL_NOISE_CV["Phalloidin"]) * multiplier
        wga = np.random.normal(treated_channels["WGA"], treated_channels["WGA"] * CHANNEL_NOISE_CV["WGA"]) * multiplier
        mitoprobe = np.random.normal(treated_channels["MitoProbe"], treated_channels["MitoProbe"] * CHANNEL_NOISE_CV["MitoProbe"]) * multiplier
        
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
            # Mitochondria (from MitoProbe)
            **mito_metrics,
            # ER (from ConA) - simplified proxy
            "ER_Mean_Intensity": cona,
            "ER_Texture_Entropy": np.random.normal(5.0, 0.5) * (cona / 15000),
            # Actin (from Phalloidin) - simplified proxy
            "Actin_Mean_Intensity": phalloidin,
            "Cell_Area": nuclear_metrics["Nucleus_Area"] * np.random.normal(3.0, 0.3),
            # Golgi (from WGA) - simplified proxy
            "Golgi_Mean_Intensity": wga,
        })
    
    df_channels = pd.DataFrame(channel_data)
    df_raw = pd.DataFrame(raw_data)
    
    # Inject gene-specific modulators (hits)
    num_hits = int(library_size * HIT_RATE)
    hit_indices = np.random.choice(library_size, num_hits, replace=False)
    
    for idx in hit_indices:
        if np.random.random() < SUPPRESSOR_PROBABILITY:
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
            
    return df_raw, df_channels


def analyze_screen_results(
    df_raw: pd.DataFrame,
    df_channels: pd.DataFrame,
    df_embeddings: pd.DataFrame,
    df_proj: pd.DataFrame,
    cell_line: str,
    treatment: str,
    dose_uM: float,
    library_size: int,
    feature: str
) -> POSHScreenResult:
    """
    Analyze screen data to identify hits and package results.
    
    Args:
        df_raw: Raw measurements
        df_channels: Channel intensities
        df_embeddings: Embeddings
        df_proj: 2D projection
        cell_line: Cell line name
        treatment: Treatment name
        dose_uM: Dose
        library_size: Library size
        feature: Selected feature for hit calling
        
    Returns:
        POSHScreenResult object
    """
    try:
        # 5. Calculate Derived Features
        # Mitochondrial Fragmentation
        df_raw["Mitochondrial_Fragmentation"] = df_raw.apply(
            lambda row: _calculate_fragmentation_from_raw(row["Mito_Object_Count"], row["Mito_Total_Area"]), 
            axis=1
        )
        
        # Nuclear Condensation
        df_raw["Nuclear_Condensation"] = df_raw.apply(
            lambda row: _calculate_nuclear_condensation(row["Nucleus_Mean_Intensity"], row["Nucleus_Form_Factor"]),
            axis=1
        )
        
        # Nuclear Shape Irregularity
        df_raw["Nuclear_Shape_Irregularity"] = df_raw.apply(
            lambda row: _calculate_nuclear_shape_irregularity(row["Nucleus_Form_Factor"], row["Nucleus_Eccentricity"]),
            axis=1
        )
        
        # ER Stress Score (derived from intensity and texture)
        df_raw["ER_Stress_Score"] = (df_raw["ER_Mean_Intensity"] / 20000) * (df_raw["ER_Texture_Entropy"] / 6.0)
        df_raw["ER_Stress_Score"] = df_raw["ER_Stress_Score"].clip(0, 1)
        
        # 6. Identify Hits (Volcano Plot Logic)
        # Map friendly feature name to column name
        feature_map = {
            "mitochondrial_fragmentation": "Mitochondrial_Fragmentation",
            "nuclear_size": "Nucleus_Area",
            "er_stress_score": "ER_Stress_Score",
            "cell_count": "Cell_Area" # Proxy
        }
        col_name = feature_map.get(feature, "Mitochondrial_Fragmentation")
        
        # Calculate Z-scores or Log2FC relative to median
        median_val = df_raw[col_name].median()
        std_val = df_raw[col_name].std()
        
        volcano_data = []
        for _, row in df_raw.iterrows():
            val = row[col_name]
            # Simulated p-value based on distance from median (Z-score approach)
            z_score = (val - median_val) / (std_val + 1e-9)
            p_val = 2 * (1 - pd.Series([abs(z_score)]).apply(lambda x: 0.5 * (1 + math.erf(x/math.sqrt(2)))).iloc[0])
            # Log2 Fold Change
            log2fc = np.log2((val + 1e-9) / (median_val + 1e-9))
            
            # Determine category
            category = "Non-targeting"
            if p_val < P_VALUE_THRESHOLD:
                if log2fc > LOG2FC_THRESHOLD:
                    category = "Enhancer"
                elif log2fc < -LOG2FC_THRESHOLD:
                    category = "Suppressor"
            
            volcano_data.append({
                "Gene": row["Gene"],
                "Value": val,
                "Log2FoldChange": log2fc,
                "P_Value": p_val,
                "NegLog10P": -np.log10(p_val + 1e-10),
                "Z_Score": z_score,
                "Category": category
            })
            
        df_volcano = pd.DataFrame(volcano_data)
        
        # Define hits
        hits = df_volcano[
            (df_volcano["P_Value"] < P_VALUE_THRESHOLD) & 
            (abs(df_volcano["Log2FoldChange"]) > LOG2FC_THRESHOLD)
        ]
        
        return POSHScreenResult(
            cell_line=cell_line,
            treatment=treatment,
            dose_uM=dose_uM,
            library_size=library_size,
            selected_feature=feature,
            hit_list=hits,
            volcano_data=df_volcano,
            raw_measurements=df_raw,
            channel_intensities=df_channels,
            embeddings=df_embeddings,
            projection_2d=df_proj,
            success=True
        )
        
    except Exception as e:
        import traceback
        traceback.print_exc()
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


def simulate_posh_screen(
    cell_line: str,
    treatment: str,
    dose_uM: float,
    library_size: int = 1000,
    coverage: int = 500,
    num_replicates: int = 3,
    feature: str = "mitochondrial_fragmentation",
    random_seed: int = 42,
    add_batch_effects: bool = False,
    add_edge_effects: bool = False
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
        add_batch_effects: If True, adds plate-to-plate variation
        add_edge_effects: If True, adds edge well artifacts
        
    Returns:
        POSHScreenResult object containing all data and analysis
    """
    # 1. Generate Raw Data
    df_raw, df_channels = simulate_screen_data(
        cell_line=cell_line,
        treatment=treatment,
        dose_uM=dose_uM,
        library_size=library_size,
        random_seed=random_seed,
        add_batch_effects=add_batch_effects,
        add_edge_effects=add_edge_effects
    )
    
    # 2. Generate Embeddings
    # Combine channels and raw measurements for embedding generation
    df_combined = pd.merge(df_channels, df_raw, on="Gene")
    df_embeddings, df_proj = generate_embeddings(df_combined, random_seed=random_seed)
    
    # 3. Analyze Results
    return analyze_screen_results(
        df_raw=df_raw,
        df_channels=df_channels,
        df_embeddings=df_embeddings,
        df_proj=df_proj,
        cell_line=cell_line,
        treatment=treatment,
        dose_uM=dose_uM,
        library_size=library_size,
        feature=feature
    )


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


