#!/usr/bin/env python3
"""
Probe Mechanism Recovery from Morphology - Mid-Dose Analysis

Key insight from initial analysis: High doses + late timepoints converge to
universal death signature, washing out class-specific signals in PCA.

This script focuses on MID-DOSE (around 1×EC50) at 12h, where adaptive stress
responses should be maximal and death-related confounds minimal.

Question: Can we recover stress class from morphology at mid-dose 12h?
"""

import sqlite3
import numpy as np
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from collections import defaultdict

DESIGN_ID = '204a9d65-d240-4123-bf65-99405b86a5b8'
DB_PATH = '/Users/bjh/cell_OS/data/cell_thalamus.db'

# Stress axis mapping
STRESS_AXES = {
    'tBHQ': 'oxidative',
    'H2O2': 'oxidative',
    'tunicamycin': 'er_stress',
    'thapsigargin': 'er_stress',
    'CCCP': 'mitochondrial',
    'oligomycin': 'mitochondrial',
    'etoposide': 'dna_damage',
    'MG132': 'proteasome',
    'nocodazole': 'microtubule',
    'paclitaxel': 'microtubule',
    'DMSO': 'vehicle',
}

# EC50 values for dose stratification
EC50_MAP = {
    'tBHQ': 30.0,
    'H2O2': 100.0,
    'tunicamycin': 1.0,
    'thapsigargin': 0.5,
    'CCCP': 5.0,
    'oligomycin': 1.0,
    'etoposide': 10.0,
    'MG132': 1.0,
    'nocodazole': 0.5,
    'paclitaxel': 0.01,
}

print("=" * 80)
print("MECHANISM RECOVERY - MID-DOSE ANALYSIS")
print("=" * 80)

# Load data
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute("""
    SELECT compound, cell_line, timepoint_h, dose_uM,
           morph_er, morph_mito, morph_nucleus, morph_actin, morph_rna
    FROM thalamus_results
    WHERE design_id = ? AND is_sentinel = 0
""", (DESIGN_ID,))

rows = cursor.fetchall()
conn.close()

print(f"\nLoaded {len(rows)} experimental wells")

# Filter for mid-dose (0.5× to 2× EC50) at 12h
mid_dose_data = []
metadata = []

for row in rows:
    compound, cell_line, timepoint, dose, er, mito, nucleus, actin, rna = row

    # Skip vehicle controls
    if compound == 'DMSO' or dose == 0:
        continue

    # Skip non-12h
    if timepoint != 12.0:
        continue

    # Filter for mid-dose range
    ec50 = EC50_MAP.get(compound)
    if ec50 is None:
        continue

    dose_ratio = dose / ec50
    if dose_ratio < 0.5 or dose_ratio > 2.0:
        continue

    stress_axis = STRESS_AXES.get(compound, 'unknown')
    morph_vector = np.array([er, mito, nucleus, actin, rna])

    mid_dose_data.append(morph_vector)
    metadata.append({
        'compound': compound,
        'stress_axis': stress_axis,
        'cell_line': cell_line,
        'dose_uM': dose,
        'dose_ratio': dose_ratio
    })

X = np.array(mid_dose_data)
print(f"Filtered to {len(X)} mid-dose (0.5-2× EC50) wells at 12h")

# ============================================================================
# PCA on mid-dose morphology
# ============================================================================
print("\n" + "=" * 80)
print("PCA on Mid-Dose Morphology (12h)")
print("=" * 80)

# Standardize features
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

# PCA
pca = PCA(n_components=5)
X_pca = pca.fit_transform(X_scaled)

print(f"\nPCA Explained Variance:")
for i, var in enumerate(pca.explained_variance_ratio_):
    cumsum = pca.explained_variance_ratio_[:i+1].sum()
    print(f"  PC{i+1}: {var*100:5.1f}%  (cumulative: {cumsum*100:5.1f}%)")

# PC loadings (which morphology features drive each PC)
print(f"\nPC Loadings (top contributors to each PC):")
print(f"{'PC':<6} {'Feature':<12} {'Loading':<10}")
print("-" * 30)
channels = ['er', 'mito', 'nucleus', 'actin', 'rna']
for pc_idx in range(3):  # Show first 3 PCs
    loadings = pca.components_[pc_idx]
    sorted_idx = np.argsort(np.abs(loadings))[::-1]
    for rank, idx in enumerate(sorted_idx[:3]):  # Top 3 features
        print(f"PC{pc_idx+1:<5} {channels[idx]:<12} {loadings[idx]:>+8.3f}")

# Check if stress classes cluster in PC1-PC2 space
print(f"\nStress Class Centroids in PC1-PC2 Space:")
print(f"{'Stress Axis':<20} {'PC1 Mean':<12} {'PC2 Mean':<12} {'N Wells':<10}")
print("-" * 60)

centroids = defaultdict(lambda: {'pc1': [], 'pc2': [], 'count': 0})
for i, meta in enumerate(metadata):
    stress_axis = meta['stress_axis']
    centroids[stress_axis]['pc1'].append(X_pca[i, 0])
    centroids[stress_axis]['pc2'].append(X_pca[i, 1])
    centroids[stress_axis]['count'] += 1

for stress_axis in sorted(centroids.keys()):
    data = centroids[stress_axis]
    pc1_mean = np.mean(data['pc1'])
    pc2_mean = np.mean(data['pc2'])
    count = data['count']
    print(f"{stress_axis:<20} {pc1_mean:>10.2f}  {pc2_mean:>10.2f}  {count:>6}")

# Check separation: within-class vs between-class variance
within_var = 0
between_var = 0
global_centroid = X_pca[:, :2].mean(axis=0)

for stress_axis, data in centroids.items():
    class_centroid = np.array([np.mean(data['pc1']), np.mean(data['pc2'])])
    between_var += data['count'] * np.sum((class_centroid - global_centroid)**2)

    for i, meta in enumerate(metadata):
        if meta['stress_axis'] == stress_axis:
            point = X_pca[i, :2]
            within_var += np.sum((point - class_centroid)**2)

separation_ratio = between_var / (within_var + 1e-9)
print(f"\nClass Separation Metric (between/within variance): {separation_ratio:.3f}")
if separation_ratio > 0.5:
    print("✓ Stress classes ARE separable in mid-dose morphology space")
elif separation_ratio > 0.2:
    print("~ Stress classes show MODERATE separation")
else:
    print("✗ Stress classes still overlap significantly")

# Show example compounds per class
print(f"\nExample Compound Signatures (mid-dose 12h):")
print(f"{'Compound':<15} {'Stress Axis':<15} {'ER':<8} {'Mito':<8} {'Nucleus':<8} {'Actin':<8} {'RNA':<8}")
print("-" * 80)

# Pick representative compounds
representatives = {
    'tunicamycin': 'er_stress',
    'MG132': 'proteasome',
    'CCCP': 'mitochondrial',
    'tBHQ': 'oxidative',
    'etoposide': 'dna_damage',
    'paclitaxel': 'microtubule',
}

for compound, stress_axis in representatives.items():
    # Find wells matching this compound
    compound_data = []
    for i, meta in enumerate(metadata):
        if meta['compound'] == compound:
            compound_data.append(X[i])

    if compound_data:
        avg_morph = np.mean(compound_data, axis=0)
        print(f"{compound:<15} {stress_axis:<15} {avg_morph[0]:>6.2f}  {avg_morph[1]:>6.2f}  "
              f"{avg_morph[2]:>6.2f}  {avg_morph[3]:>6.2f}  {avg_morph[4]:>6.2f}")

print("\n" + "=" * 80)
print("INTERPRETATION")
print("=" * 80)
print("""
If separation_ratio > 0.5:
  Stress classes ARE recoverable from morphology at mid-dose 12h.
  The original Q1 failure was due to mixing mid-dose signals with high-dose death.

If separation_ratio < 0.2:
  Even at optimal conditions (mid-dose adaptive response), morphology classes overlap.
  This could mean:
  1. Noise levels too high relative to between-class differences
  2. Morphology features not discriminative enough (need higher-order features)
  3. Biological reality: stress responses share common pathways at this resolution
""")
print("=" * 80)
