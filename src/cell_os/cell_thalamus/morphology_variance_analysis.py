"""
Morphology Variance Analysis for Autonomous Loop (Phase 1)

This module implements the foundation for morphology-based active learning:
- Per-condition covariance estimation in latent space
- Nuisance variance decomposition (plate, day, operator effects)
- Priority scoring that ranks conditions by "scientific ambiguity"

The goal: Stop optimizing viability curves and start tightening the morphology manifold
where it matters for defining reward functions and constraints.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from sklearn.decomposition import PCA
from sklearn.covariance import LedoitWolf
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from scipy.spatial.distance import euclidean
import logging

logger = logging.getLogger(__name__)


@dataclass
class ConditionVariance:
    """Morphology variance metrics for a single condition."""
    condition_id: str
    compound: str
    cell_line: str
    dose_uM: float
    timepoint_h: float

    # Core metrics
    n_replicates: int
    mean_embedding: np.ndarray
    covariance_trace: float  # tr(Σ_c) - total scatter
    covariance_logdet: float  # log|Σ_c| - volume

    # Biological context
    mean_viability: float
    is_death: bool  # viability < threshold

    # Nuisance decomposition
    nuisance_fraction: float  # fraction of variance from plate/day/operator

    # Priority score
    priority: float


@dataclass
class ManifoldDiagnostics:
    """Global diagnostics about manifold quality."""
    n_conditions: int
    median_n_replicates: int

    # Trajectory vs noise ratio
    trajectory_snr: Dict[str, float]  # per compound+cell

    # Nuisance dominance
    global_nuisance_fraction: float
    plate_predictability: float  # classifier accuracy for plate_id

    # Recommendations
    should_tighten_first: bool  # True if trajectory SNR is low
    should_add_anchors: bool  # True if nuisance dominates


class MorphologyVarianceAnalyzer:
    """
    Analyze morphology variance to rank conditions for autonomous loop.

    This replaces "entropy of EC50" with "covariance of phenotype."
    """

    def __init__(
        self,
        n_pcs: int = 15,
        death_viability_threshold: float = 0.25,
        nuisance_penalty_lambda: float = 0.5,
    ):
        """
        Args:
            n_pcs: Number of PCs to use (balance: capture biology vs avoid overfitting n=3)
            death_viability_threshold: Viability below this is considered "death manifold"
            nuisance_penalty_lambda: Weight for nuisance penalty in priority score
        """
        self.n_pcs = n_pcs
        self.death_threshold = death_viability_threshold
        self.lambda_nuis = nuisance_penalty_lambda

        self.pca = None
        self.scaler = None

    def analyze_design(
        self,
        results: List[Dict],
        design_id: str
    ) -> Tuple[List[ConditionVariance], ManifoldDiagnostics]:
        """
        Analyze a completed experiment to rank conditions by morphology variance.

        Args:
            results: List of well results from database
            design_id: Design ID for logging

        Returns:
            (ranked_conditions, diagnostics)
        """
        logger.info(f"Starting morphology variance analysis for {design_id}")
        logger.info(f"Total wells: {len(results)}")

        # Step 0: Extract morphology features and fit PCA
        X, metadata = self._extract_morphology_features(results)
        X_pca = self._fit_pca(X)

        logger.info(f"PCA: {X.shape} → {X_pca.shape} ({self.pca.explained_variance_ratio_[:5].sum():.1%} variance in first 5 PCs)")

        # Step 1: Group by condition and compute per-condition covariance
        conditions = self._compute_condition_covariances(X_pca, metadata)
        logger.info(f"Analyzed {len(conditions)} unique conditions")

        # Step 2: Estimate nuisance variance
        nuisance_scores = self._estimate_nuisance_variance(X_pca, metadata)

        # Assign nuisance fraction to each condition
        for cond in conditions:
            cond.nuisance_fraction = nuisance_scores.get(cond.condition_id, 0.0)

        # Step 3: Compute priority scores
        for cond in conditions:
            cond.priority = self._compute_priority(cond)

        # Step 4: Compute global diagnostics
        diagnostics = self._compute_diagnostics(conditions, X_pca, metadata, nuisance_scores)

        # Sort by priority (high → low)
        conditions.sort(key=lambda c: c.priority, reverse=True)

        return conditions, diagnostics

    def _extract_morphology_features(
        self,
        results: List[Dict]
    ) -> Tuple[np.ndarray, pd.DataFrame]:
        """Extract 5-channel morphology features from results."""
        features = []
        metadata_rows = []

        for r in results:
            # 5D morphology: ER, Mito, Nucleus, Actin, RNA
            morph = np.array([
                r.get('morph_er', 0.0),
                r.get('morph_mito', 0.0),
                r.get('morph_nucleus', 0.0),
                r.get('morph_actin', 0.0),
                r.get('morph_rna', 0.0),
            ])

            # Skip wells with missing morphology
            if np.any(np.isnan(morph)) or np.all(morph == 0):
                continue

            features.append(morph)

            # Store metadata for grouping
            metadata_rows.append({
                'well_id': r.get('well_id'),
                'compound': r.get('compound'),
                'cell_line': r.get('cell_line'),
                'dose_uM': r.get('dose_uM', 0.0),
                'timepoint_h': r.get('timepoint_h', 0.0),
                'viability_pct': r.get('viability_pct', 100.0),
                'plate_id': r.get('plate_id', 'unknown'),
                'day': r.get('day', 1),
                'operator': r.get('operator', 'unknown'),
                'is_sentinel': r.get('is_sentinel', False),
            })

        X = np.array(features)
        metadata = pd.DataFrame(metadata_rows)

        # Debug: check index before reset
        logger.info(f"Metadata index before reset: {metadata.index.tolist()[:10]}")

        metadata = metadata.reset_index(drop=True)

        # Debug: check index after reset
        logger.info(f"Metadata index after reset: {metadata.index.tolist()[:10]}")
        logger.info(f"Metadata columns: {metadata.columns.tolist()}")
        logger.info(f"Metadata dtypes:\n{metadata.dtypes}")

        logger.info(f"Extracted {len(X)} wells with valid morphology from {len(results)} total")

        return X, metadata

    def _fit_pca(self, X: np.ndarray) -> np.ndarray:
        """Fit PCA and return transformed embeddings."""
        # Standardize features (mean=0, std=1)
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)

        # Fit PCA - use min of requested PCs and available features
        n_features = X_scaled.shape[1]
        n_samples = X_scaled.shape[0]
        n_components = min(self.n_pcs, n_features, n_samples)

        self.pca = PCA(n_components=n_components)
        X_pca = self.pca.fit_transform(X_scaled)

        logger.info(f"PCA: {n_components} components from {n_features} features, {n_samples} samples")

        return X_pca

    def _compute_condition_covariances(
        self,
        X_pca: np.ndarray,
        metadata: pd.DataFrame
    ) -> List[ConditionVariance]:
        """Compute per-condition mean and covariance."""
        conditions = []

        # Group by condition (exclude sentinels for now)
        # Build a new DataFrame from scratch with only non-sentinel rows
        experimental_rows = []
        experimental_embeddings = []

        # Use enumerate to track position in X_pca, not DataFrame index
        for pos, (idx, row) in enumerate(metadata.iterrows()):
            if not row['is_sentinel']:
                experimental_rows.append(row.to_dict())
                experimental_embeddings.append(X_pca[pos])

        experimental = pd.DataFrame(experimental_rows).reset_index(drop=True)
        X_pca_subset = np.array(experimental_embeddings)

        logger.info(f"Filtered to {len(experimental)} experimental wells (excluding sentinels)")

        # Add PCA embeddings to metadata
        experimental['embedding'] = list(X_pca_subset)

        # Canonicalize vehicle wells: treat all "compound @ 0 µM" as "vehicle"
        # This prevents partitioning DMSO variance by compound name
        experimental['condition_compound'] = experimental.apply(
            lambda row: 'vehicle' if row['dose_uM'] == 0.0 or row['compound'] == 'DMSO' else row['compound'],
            axis=1
        )

        # Group by condition (use canonical compound name)
        grouped = experimental.groupby(['condition_compound', 'cell_line', 'dose_uM', 'timepoint_h'])

        for (compound, cell_line, dose_uM, timepoint_h), group in grouped:
            if len(group) < 2:
                # Need at least 2 replicates to estimate covariance
                continue

            # Extract embeddings for this condition
            embeddings = np.array(list(group['embedding']))

            # Compute mean
            mean_emb = embeddings.mean(axis=0)

            # Compute covariance with Ledoit-Wolf shrinkage (handles n=3 gracefully)
            if len(embeddings) >= 2:
                lw = LedoitWolf()
                try:
                    cov = lw.fit(embeddings).covariance_
                    cov_trace = np.trace(cov)
                    cov_logdet = np.linalg.slogdet(cov + 1e-6 * np.eye(len(cov)))[1]
                except:
                    # Fallback to diagonal if shrinkage fails
                    cov_trace = embeddings.var(axis=0).sum()
                    cov_logdet = np.log(embeddings.var(axis=0).prod() + 1e-6)
            else:
                cov_trace = 0.0
                cov_logdet = -np.inf

            # Biological context
            mean_viability = group['viability_pct'].mean() / 100.0
            is_death = mean_viability < self.death_threshold

            # Create condition ID (use canonical compound for vehicle)
            condition_id = f"{compound}_{cell_line}_{dose_uM:.2f}uM_{timepoint_h:.0f}h"

            # Display label: just use "vehicle" for canonicalized vehicle wells
            display_compound = compound

            conditions.append(ConditionVariance(
                condition_id=condition_id,
                compound=display_compound,  # Use display label
                cell_line=cell_line,
                dose_uM=dose_uM,
                timepoint_h=timepoint_h,
                n_replicates=len(embeddings),
                mean_embedding=mean_emb,
                covariance_trace=cov_trace,
                covariance_logdet=cov_logdet,
                mean_viability=mean_viability,
                is_death=is_death,
                nuisance_fraction=0.0,  # Will be filled later
                priority=0.0,  # Will be computed later
            ))

        return conditions

    def _estimate_nuisance_variance(
        self,
        X_pca: np.ndarray,
        metadata: pd.DataFrame
    ) -> Dict[str, float]:
        """
        Estimate fraction of variance due to nuisance factors (plate, day, operator).

        Three approaches:
        A) Classifier test: Can we predict plate_id from embeddings?
        B) Anchor stability: Between-plate distance vs within-plate scatter for vehicle
        C) Variance partition: Estimate σ²_nuisance / σ²_total per condition neighborhood

        Returns dict: condition_id → nuisance_fraction
        """
        # Approach A: Plate predictability (fast humiliation test)
        # Filter out sentinels - build new DataFrame to avoid indexing issues
        experimental_rows = []
        experimental_embeddings = []

        for pos, (idx, row) in enumerate(metadata.iterrows()):
            if not row['is_sentinel']:
                experimental_rows.append(row.to_dict())
                experimental_embeddings.append(X_pca[pos])

        if len(experimental_rows) < 10:
            # Not enough data for nuisance estimation
            return {}

        experimental = pd.DataFrame(experimental_rows).reset_index(drop=True)
        X_exp = np.array(experimental_embeddings)

        if experimental['plate_id'].nunique() < 2:
            # Need multiple plates for plate effect estimation
            return {}

        # Train classifier to predict plate from embedding
        y_plate = experimental['plate_id'].values

        try:
            clf = RandomForestClassifier(n_estimators=50, max_depth=5, random_state=42)
            clf.fit(X_exp, y_plate)
            plate_accuracy = clf.score(X_exp, y_plate)

            logger.info(f"Nuisance test A (Classifier): Plate prediction accuracy = {plate_accuracy:.1%}")

            # Approach B: Anchor stability test (harder to fake)
            # For vehicle conditions, compute between-plate mean shift vs within-plate scatter
            anchor_nuisance = self._compute_anchor_stability(X_exp, experimental)

            if anchor_nuisance is not None:
                logger.info(f"Nuisance test B (Anchor stability): nuisance fraction = {anchor_nuisance:.2f}")

            # Use the maximum of both tests as the nuisance estimate
            classifier_nuisance = max(0.0, (plate_accuracy - 0.5) / 0.5)  # Normalize to [0,1]
            global_nuisance = max(classifier_nuisance, anchor_nuisance or 0.0)

            logger.info(f"Final nuisance estimate: {global_nuisance:.2f}")

            # Canonicalize vehicle in condition IDs to match _compute_condition_covariances
            result = {}
            for _, r in experimental.iterrows():
                compound = 'vehicle' if r['dose_uM'] == 0.0 or r['compound'] == 'DMSO' else r['compound']
                condition_id = f"{compound}_{r['cell_line']}_{r['dose_uM']:.2f}uM_{r['timepoint_h']:.0f}h"
                result[condition_id] = global_nuisance

            return result

        except Exception as e:
            logger.warning(f"Nuisance estimation failed: {e}")
            return {}

    def _compute_anchor_stability(
        self,
        X_pca: np.ndarray,
        metadata: pd.DataFrame
    ) -> Optional[float]:
        """
        Compute anchor stability: between-plate distance vs within-plate scatter.

        For vehicle conditions, if between-plate mean shifts are comparable to
        within-plate scatter, you have nuisance even if the classifier shrugs.

        Returns: nuisance fraction (0-1), where >0.5 means nuisance dominates
        """
        # Find vehicle wells (dose = 0)
        vehicle_mask = metadata['dose_uM'] == 0.0

        if vehicle_mask.sum() < 10:
            return None  # Not enough vehicle wells

        vehicle_metadata = metadata[vehicle_mask].reset_index(drop=True)
        vehicle_embeddings = X_pca[vehicle_mask.values]

        plates = vehicle_metadata['plate_id'].unique()
        if len(plates) < 2:
            return None  # Need multiple plates

        # Compute per-plate means and within-plate scatter
        plate_means = []
        within_plate_scatters = []

        for plate in plates:
            plate_mask = vehicle_metadata['plate_id'] == plate
            plate_embeddings = vehicle_embeddings[plate_mask.values]

            if len(plate_embeddings) < 2:
                continue

            plate_mean = plate_embeddings.mean(axis=0)
            plate_scatter = np.sqrt(plate_embeddings.var(axis=0).sum())  # RMS of variances

            plate_means.append(plate_mean)
            within_plate_scatters.append(plate_scatter)

        if len(plate_means) < 2:
            return None

        # Compute between-plate distances
        plate_means = np.array(plate_means)
        between_plate_distances = []
        for i in range(len(plate_means)):
            for j in range(i+1, len(plate_means)):
                dist = np.linalg.norm(plate_means[i] - plate_means[j])
                between_plate_distances.append(dist)

        # Ratio: between-plate distance / within-plate scatter
        mean_between = np.mean(between_plate_distances)
        mean_within = np.mean(within_plate_scatters)

        if mean_within == 0:
            return None

        ratio = mean_between / mean_within

        # Convert to [0,1] nuisance fraction: ratio > 1 means nuisance dominates
        # Use sigmoid-like transformation: nuisance = ratio / (ratio + 1)
        nuisance_fraction = ratio / (ratio + 1.0)

        logger.info(f"Anchor stability: between/within ratio = {ratio:.2f} (nuisance = {nuisance_fraction:.2f})")

        return nuisance_fraction

    def _compute_priority(self, cond: ConditionVariance) -> float:
        """
        Compute priority score for a condition.

        Priority = S_within × (1 - I_death) × (1 - λ·P_nuis)

        High priority = high scatter, non-death, low nuisance
        """
        if cond.is_death:
            return 0.0

        # Within-condition scatter
        scatter = cond.covariance_trace

        # Death penalty
        death_penalty = 1.0 if not cond.is_death else 0.0

        # Nuisance penalty
        nuisance_penalty = 1.0 - self.lambda_nuis * cond.nuisance_fraction

        priority = scatter * death_penalty * nuisance_penalty

        return max(0.0, priority)

    def _compute_diagnostics(
        self,
        conditions: List[ConditionVariance],
        X_pca: np.ndarray,
        metadata: pd.DataFrame,
        nuisance_scores: Dict[str, float]
    ) -> ManifoldDiagnostics:
        """Compute global manifold quality diagnostics."""

        # Median replicates per condition
        n_reps = [c.n_replicates for c in conditions]
        median_n = int(np.median(n_reps)) if n_reps else 0

        # Trajectory SNR: measure signal-to-noise for dose-response trajectories
        trajectory_snr = self._compute_trajectory_snr(conditions)

        # Global nuisance fraction
        global_nuis = np.mean(list(nuisance_scores.values())) if nuisance_scores else 0.0

        # Plate predictability (from nuisance estimation)
        plate_pred = global_nuis  # Simplified proxy

        # Recommendations
        median_snr = np.median(list(trajectory_snr.values())) if trajectory_snr else 1.0
        should_tighten = median_snr < 1.0  # Trajectory buried in noise
        should_add_anchors = global_nuis > 0.5  # Nuisance dominates

        return ManifoldDiagnostics(
            n_conditions=len(conditions),
            median_n_replicates=median_n,
            trajectory_snr=trajectory_snr,
            global_nuisance_fraction=global_nuis,
            plate_predictability=plate_pred,
            should_tighten_first=should_tighten,
            should_add_anchors=should_add_anchors,
        )

    def _compute_trajectory_snr(
        self,
        conditions: List[ConditionVariance]
    ) -> Dict[str, float]:
        """
        Compute trajectory signal-to-noise ratio.

        For each compound × cell × timepoint series:
        SNR = trajectory_length / mean_scatter

        If SNR << 1: trajectory is buried in noise, need to tighten first
        If SNR >> 1: trajectory is clear, can fill gaps
        """
        trajectory_snr = {}

        # Group by compound × cell × timepoint
        grouped = {}
        for cond in conditions:
            key = f"{cond.compound}_{cond.cell_line}_{cond.timepoint_h:.0f}h"
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(cond)

        for key, conds in grouped.items():
            if len(conds) < 2:
                continue

            # Sort by dose
            conds_sorted = sorted(conds, key=lambda c: c.dose_uM)

            # Compute trajectory length (sum of distances between adjacent doses)
            traj_length = 0.0
            for i in range(len(conds_sorted) - 1):
                dist = euclidean(conds_sorted[i].mean_embedding, conds_sorted[i+1].mean_embedding)
                traj_length += dist

            # Mean scatter (sqrt of mean trace)
            mean_scatter = np.mean([np.sqrt(c.covariance_trace) for c in conds_sorted])

            # SNR
            snr = traj_length / mean_scatter if mean_scatter > 0 else 0.0
            trajectory_snr[key] = snr

        return trajectory_snr


def _to_native(val):
    """Convert numpy types to Python native types for JSON serialization."""
    if hasattr(val, 'item'):
        return val.item()
    elif isinstance(val, np.ndarray):
        return val.tolist()
    elif isinstance(val, (np.integer, np.floating)):
        return float(val)
    elif isinstance(val, np.bool_):
        return bool(val)
    return val


def rank_conditions_for_autonomous_loop(
    results: List[Dict],
    design_id: str,
    top_k: int = 10
) -> Tuple[List[Dict], Dict]:
    """
    High-level function to rank conditions for autonomous loop.

    Returns:
        (ranked_candidates, diagnostics_dict)
    """
    analyzer = MorphologyVarianceAnalyzer(
        n_pcs=15,
        death_viability_threshold=0.25,
        nuisance_penalty_lambda=0.5,
    )

    conditions, diagnostics = analyzer.analyze_design(results, design_id)

    # Convert to output format (ensure all numpy types are converted to native Python)
    candidates = []
    for cond in conditions[:top_k]:
        candidates.append({
            'compound': str(cond.compound),
            'cellLine': str(cond.cell_line),
            'dose_uM': _to_native(cond.dose_uM),
            'timepoint': f"{int(cond.timepoint_h)}h",
            'priority_score': _to_native(cond.priority),
            'covariance_trace': _to_native(cond.covariance_trace),
            'n_replicates': int(cond.n_replicates),
            'mean_viability': _to_native(cond.mean_viability),
            'is_death': bool(cond.is_death),
            'nuisance_fraction': _to_native(cond.nuisance_fraction),
            'reason': _explain_priority(cond),
        })

    diagnostics_dict = {
        'n_conditions': int(diagnostics.n_conditions),
        'median_n_replicates': int(diagnostics.median_n_replicates),
        'global_nuisance_fraction': _to_native(diagnostics.global_nuisance_fraction),
        'should_tighten_first': bool(diagnostics.should_tighten_first),
        'should_add_anchors': bool(diagnostics.should_add_anchors),
        'trajectory_snr': {k: _to_native(v) for k, v in diagnostics.trajectory_snr.items()},
    }

    return candidates, diagnostics_dict


def _explain_priority(cond: ConditionVariance) -> str:
    """Generate human-readable explanation for why condition is prioritized."""
    if cond.is_death:
        return "Excluded: death manifold (viability < 25%)"

    if cond.nuisance_fraction > 0.5:
        return f"High scatter ({cond.covariance_trace:.2f}) but nuisance-dominated ({cond.nuisance_fraction:.0%})"

    if cond.covariance_trace > 10.0:
        return f"Very high phenotypic variance ({cond.covariance_trace:.2f}) - needs tightening"
    elif cond.covariance_trace > 5.0:
        return f"High phenotypic variance ({cond.covariance_trace:.2f}) - ambiguous phenotype"
    else:
        return f"Moderate variance ({cond.covariance_trace:.2f}) - stable phenotype"
