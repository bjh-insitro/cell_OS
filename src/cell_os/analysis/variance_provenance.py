"""
Variance provenance analysis for detector realism stack.

Decomposes total variance into components (geometry, noise, pathology, residual)
using counterfactual measurements with layer toggles.
"""

import csv
import numpy as np
from pathlib import Path
from typing import Dict, List, Any, Optional


CHANNELS = ['er', 'mito', 'nucleus', 'actin', 'rna']


def load_wells_csv(csv_path: Path) -> List[Dict[str, Any]]:
    """
    Load per-well measurements from CSV.

    Args:
        csv_path: Path to CSV file with columns: well_id, row, col, er, mito, nucleus, actin, rna

    Returns:
        List of well dicts with parsed values
    """
    wells = []
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            well = {
                'well_id': row['well_id'],
                'row': int(row['row']),
                'col': int(row['col']),
            }
            # Parse channel values
            for ch in CHANNELS:
                well[ch] = float(row[ch])

            # Preserve metadata if present
            for key in ['edge_distance', 'realism_config_source', 'realism_config_hash']:
                if key in row:
                    well[key] = row[key]

            wells.append(well)

    return wells


def compute_deltas(
    bio: List[Dict[str, Any]],
    geo: List[Dict[str, Any]],
    noise: List[Dict[str, Any]],
    path: List[Dict[str, Any]],
    obs: List[Dict[str, Any]]
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Compute per-well deltas for each component.

    Deltas are computed as deviations from biology-only baseline:
    - delta_geo   = y_geo - y_bio
    - delta_noise = y_noise - y_bio
    - delta_path  = y_path - y_bio
    - delta_total = y_obs - y_bio
    - delta_resid = delta_total - (delta_geo + delta_noise + delta_path)

    Args:
        bio: Biology-only wells (all realism layers off)
        geo: Geometry-only wells (position effects on)
        noise: Noise-only wells (edge noise inflation on)
        path: Pathology-only wells (outliers on)
        obs: Observed wells (all layers on)

    Returns:
        Dict with keys: 'geo', 'noise', 'path', 'total', 'resid'
        Each value is a list of well dicts with delta values per channel
    """
    n_wells = len(bio)
    assert len(geo) == n_wells, "Geometry wells count mismatch"
    assert len(noise) == n_wells, "Noise wells count mismatch"
    assert len(path) == n_wells, "Pathology wells count mismatch"
    assert len(obs) == n_wells, "Observed wells count mismatch"

    # Compute deltas per well
    delta_geo_wells = []
    delta_noise_wells = []
    delta_path_wells = []
    delta_total_wells = []
    delta_resid_wells = []

    for i in range(n_wells):
        # Verify well IDs match (sanity check)
        well_id = bio[i]['well_id']
        assert geo[i]['well_id'] == well_id
        assert noise[i]['well_id'] == well_id
        assert path[i]['well_id'] == well_id
        assert obs[i]['well_id'] == well_id

        # Compute deltas per channel
        delta_geo = {'well_id': well_id, 'row': bio[i]['row'], 'col': bio[i]['col']}
        delta_noise = {'well_id': well_id, 'row': bio[i]['row'], 'col': bio[i]['col']}
        delta_path = {'well_id': well_id, 'row': bio[i]['row'], 'col': bio[i]['col']}
        delta_total = {'well_id': well_id, 'row': bio[i]['row'], 'col': bio[i]['col']}
        delta_resid = {'well_id': well_id, 'row': bio[i]['row'], 'col': bio[i]['col']}

        for ch in CHANNELS:
            y_bio = bio[i][ch]
            y_geo = geo[i][ch]
            y_noise = noise[i][ch]
            y_path = path[i][ch]
            y_obs = obs[i][ch]

            delta_geo[ch] = y_geo - y_bio
            delta_noise[ch] = y_noise - y_bio
            delta_path[ch] = y_path - y_bio
            delta_total[ch] = y_obs - y_bio

            # Residual: non-additivity / interaction
            delta_resid[ch] = delta_total[ch] - (delta_geo[ch] + delta_noise[ch] + delta_path[ch])

        delta_geo_wells.append(delta_geo)
        delta_noise_wells.append(delta_noise)
        delta_path_wells.append(delta_path)
        delta_total_wells.append(delta_total)
        delta_resid_wells.append(delta_resid)

    return {
        'geo': delta_geo_wells,
        'noise': delta_noise_wells,
        'path': delta_path_wells,
        'total': delta_total_wells,
        'resid': delta_resid_wells,
    }


def compute_variance_budget(
    deltas: Dict[str, List[Dict[str, Any]]]
) -> Dict[str, Any]:
    """
    Compute variance budget per channel.

    Computes:
    - Var_total, Var_geo, Var_noise, Var_path, Var_resid (raw variances)
    - frac_geo, frac_noise, frac_path, frac_resid (variance fractions)

    Fractions sum to ~1.0 if layers are roughly additive (small residual).
    Large residual indicates interaction between layers.

    Args:
        deltas: Dict from compute_deltas() with 'geo', 'noise', 'path', 'total', 'resid' wells

    Returns:
        Dict with per-channel variance budgets and fractions:
        {
            'er': {'Var_total': float, 'Var_geo': float, ..., 'frac_geo': float, ...},
            'mito': {...},
            ...
            'summary': {
                'total_variance_explained': float,  # mean across channels
                'mean_residual_fraction': float,
            }
        }
    """
    budget = {}

    for ch in CHANNELS:
        # Extract delta values for this channel across all wells
        delta_total_vals = np.array([w[ch] for w in deltas['total']])
        delta_geo_vals = np.array([w[ch] for w in deltas['geo']])
        delta_noise_vals = np.array([w[ch] for w in deltas['noise']])
        delta_path_vals = np.array([w[ch] for w in deltas['path']])
        delta_resid_vals = np.array([w[ch] for w in deltas['resid']])

        # Compute variances
        var_total = float(np.var(delta_total_vals))
        var_geo = float(np.var(delta_geo_vals))
        var_noise = float(np.var(delta_noise_vals))
        var_path = float(np.var(delta_path_vals))
        var_resid = float(np.var(delta_resid_vals))

        # Compute variance fractions
        if var_total > 1e-12:  # Non-zero total variance
            frac_geo = var_geo / var_total
            frac_noise = var_noise / var_total
            frac_path = var_path / var_total
            frac_resid = var_resid / var_total
        else:
            # Total variance is zero (clean profile or no effects)
            frac_geo = 0.0
            frac_noise = 0.0
            frac_path = 0.0
            frac_resid = 0.0

        budget[ch] = {
            'Var_total': var_total,
            'Var_geo': var_geo,
            'Var_noise': var_noise,
            'Var_path': var_path,
            'Var_resid': var_resid,
            'frac_geo': frac_geo,
            'frac_noise': frac_noise,
            'frac_path': frac_path,
            'frac_resid': frac_resid,
        }

    # Compute summary stats
    total_explained = []
    residual_fractions = []

    for ch in CHANNELS:
        explained = budget[ch]['frac_geo'] + budget[ch]['frac_noise'] + budget[ch]['frac_path']
        total_explained.append(explained)
        residual_fractions.append(budget[ch]['frac_resid'])

    budget['summary'] = {
        'total_variance_explained': float(np.mean(total_explained)),
        'mean_residual_fraction': float(np.mean(residual_fractions)),
    }

    return budget


def save_deltas_csv(
    deltas: Dict[str, List[Dict[str, Any]]],
    output_path: Path
):
    """
    Save deltas to CSV for inspection.

    Args:
        deltas: Dict from compute_deltas()
        output_path: Path to output CSV
    """
    # Flatten structure: one row per well, columns for delta_geo_*, delta_noise_*, etc.
    rows = []
    n_wells = len(deltas['total'])

    for i in range(n_wells):
        row = {
            'well_id': deltas['total'][i]['well_id'],
            'row': deltas['total'][i]['row'],
            'col': deltas['total'][i]['col'],
        }

        # Add delta columns
        for component in ['geo', 'noise', 'path', 'total', 'resid']:
            for ch in CHANNELS:
                row[f'delta_{component}_{ch}'] = deltas[component][i][ch]

        rows.append(row)

    # Write CSV
    fieldnames = ['well_id', 'row', 'col']
    for component in ['geo', 'noise', 'path', 'total', 'resid']:
        for ch in CHANNELS:
            fieldnames.append(f'delta_{component}_{ch}')

    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def save_variance_budget_csv(
    budget: Dict[str, Any],
    output_path: Path
):
    """
    Save variance budget to CSV.

    Args:
        budget: Dict from compute_variance_budget()
        output_path: Path to output CSV
    """
    rows = []

    for ch in CHANNELS:
        row = {
            'channel': ch,
            'Var_total': budget[ch]['Var_total'],
            'Var_geo': budget[ch]['Var_geo'],
            'Var_noise': budget[ch]['Var_noise'],
            'Var_path': budget[ch]['Var_path'],
            'Var_resid': budget[ch]['Var_resid'],
            'frac_geo': budget[ch]['frac_geo'],
            'frac_noise': budget[ch]['frac_noise'],
            'frac_path': budget[ch]['frac_path'],
            'frac_resid': budget[ch]['frac_resid'],
        }
        rows.append(row)

    fieldnames = [
        'channel',
        'Var_total', 'Var_geo', 'Var_noise', 'Var_path', 'Var_resid',
        'frac_geo', 'frac_noise', 'frac_path', 'frac_resid'
    ]

    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
