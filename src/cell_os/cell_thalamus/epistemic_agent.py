"""
Phase 1 Epistemic Agent - Learns Where Biological Information Lives

This agent actively learns to discover which experimental conditions (dose, timepoint)
maximize mechanistic information content without being told the answer upfront.

Key Goal: Discover that mid-dose (0.5-2×IC50) at early timepoints (12h) provides
the best stress class separation - but learn this through exploration, not hardcoding.

Metrics:
- Separation ratio = between_class_variance / within_class_variance
- Higher ratio = better stress class discriminability in morphology space
"""

import numpy as np
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

from cell_os.cell_thalamus.thalamus_agent import CellThalamusAgent
from cell_os.cell_thalamus.design_generator import WellAssignment

logger = logging.getLogger(__name__)


@dataclass
class ExperimentQuery:
    """A single experimental condition to query."""
    compound: str
    dose_uM: float
    timepoint_h: float
    cell_line: str
    n_wells: int = 1  # Number of replicates

    def __repr__(self):
        return f"{self.compound} {self.dose_uM}µM @ {self.timepoint_h}h ({self.cell_line})"


@dataclass
class QueryResult:
    """Results from querying an experimental condition."""
    query: ExperimentQuery
    morphology: Dict[str, List[float]]  # {channel: [replicate_values]}
    viability: List[float]
    timestamp: datetime = field(default_factory=datetime.now)

    def get_mean_morphology(self) -> Dict[str, float]:
        """Get mean across replicates."""
        return {ch: np.mean(vals) for ch, vals in self.morphology.items()}


class InformationMetrics:
    """Computes information content metrics for active learning."""

    @staticmethod
    def compute_separation_ratio(data: List[QueryResult],
                                  stress_class_map: Dict[str, str]) -> float:
        """
        Compute separation ratio: between_class_variance / within_class_variance

        Args:
            data: List of experimental results
            stress_class_map: Maps compound -> stress_axis (e.g., 'tBHQ' -> 'oxidative')

        Returns:
            Separation ratio (higher = better class separation)
        """
        if len(data) < 2:
            return 0.0

        # Extract morphology features and class labels
        features = []
        labels = []

        for result in data:
            mean_morph = result.get_mean_morphology()
            feature_vector = [mean_morph[ch] for ch in ['er', 'mito', 'nucleus', 'actin', 'rna']]
            features.append(feature_vector)

            compound = result.query.compound
            stress_class = stress_class_map.get(compound, 'unknown')
            labels.append(stress_class)

        features = np.array(features)

        # Standardize features
        if len(features) < 2:
            return 0.0

        scaler = StandardScaler()
        features_scaled = scaler.fit_transform(features)

        # PCA to 2D
        if features_scaled.shape[0] < 2:
            return 0.0

        pca = PCA(n_components=min(2, features_scaled.shape[0], features_scaled.shape[1]))
        features_pca = pca.fit_transform(features_scaled)

        # Compute between-class and within-class variance
        unique_classes = list(set(labels))
        if len(unique_classes) < 2:
            return 0.0

        # Between-class variance (variance of class centroids)
        class_centroids = []
        for cls in unique_classes:
            cls_mask = np.array(labels) == cls
            if np.sum(cls_mask) > 0:
                centroid = features_pca[cls_mask].mean(axis=0)
                class_centroids.append(centroid)

        class_centroids = np.array(class_centroids)
        overall_centroid = features_pca.mean(axis=0)
        between_var = np.sum(np.var(class_centroids, axis=0))

        # Within-class variance (average variance within each class)
        within_vars = []
        for cls in unique_classes:
            cls_mask = np.array(labels) == cls
            if np.sum(cls_mask) > 1:
                cls_var = np.sum(np.var(features_pca[cls_mask], axis=0))
                within_vars.append(cls_var)

        if not within_vars:
            return 0.0

        within_var = np.mean(within_vars)

        if within_var < 1e-10:
            return float('inf') if between_var > 0 else 0.0

        separation_ratio = between_var / within_var
        return float(separation_ratio)

    @staticmethod
    def compute_uncertainty(data: List[QueryResult]) -> float:
        """
        Compute epistemic uncertainty - how much do we still not know?

        Simple version: coefficient of variation across replicates
        """
        if not data:
            return 1.0  # Maximum uncertainty when no data

        cvs = []
        for result in data:
            for channel, values in result.morphology.items():
                if len(values) > 1:
                    mean = np.mean(values)
                    std = np.std(values)
                    if mean > 0:
                        cvs.append(std / mean)

        return np.mean(cvs) if cvs else 0.1


class EpistemicAgent:
    """
    Phase 1 Agent: Learns to allocate experimental budget to maximize information.

    Strategy:
    1. Start with random sampling across dose/timepoint space
    2. After each batch, compute separation ratio
    3. Use acquisition function to decide next queries
    4. Converge to conditions with highest information content
    """

    def __init__(self,
                 budget: int = 384,  # Total wells available (4 plates)
                 hardware: Optional[CellThalamusAgent] = None):
        """
        Initialize epistemic agent.

        Args:
            budget: Total number of wells available
            hardware: Cell Thalamus agent for executing queries
        """
        self.budget = budget
        self.budget_remaining = budget
        self.hardware = hardware or CellThalamusAgent(phase=1)

        # Data collected so far
        self.results: List[QueryResult] = []

        # Compound-to-stress-axis mapping
        self.stress_class_map = {
            'tBHQ': 'oxidative',
            'H2O2': 'oxidative',
            'tunicamycin': 'er_stress',
            'thapsigargin': 'er_stress',
            'CCCP': 'mitochondrial',
            'oligomycin': 'mitochondrial',
            'etoposide': 'dna_damage',
            'MG132': 'proteasome',
            'nocodazole': 'microtubule',
            'paclitaxel': 'microtubule'
        }

        # Search space
        self.compounds = list(self.stress_class_map.keys())
        self.doses_relative = [0.1, 0.5, 1.0, 2.0, 5.0, 10.0]  # Relative to IC50
        self.timepoints = [12.0, 24.0, 48.0]
        self.cell_lines = ['A549', 'HepG2']

        logger.info(f"Epistemic Agent initialized with budget={budget} wells")

    def execute_query(self, query: ExperimentQuery) -> QueryResult:
        """
        Execute an experimental query and return results.

        Args:
            query: Experimental condition to test

        Returns:
            QueryResult with morphology data
        """
        if self.budget_remaining < query.n_wells:
            raise ValueError(f"Insufficient budget: {self.budget_remaining} < {query.n_wells}")

        logger.info(f"Executing query: {query}")

        # Execute replicates
        morphology_replicates = {ch: [] for ch in ['er', 'mito', 'nucleus', 'actin', 'rna']}
        viability_replicates = []

        for rep in range(query.n_wells):
            well = WellAssignment(
                well_id=f"Q{len(self.results):03d}_R{rep:02d}",
                cell_line=query.cell_line,
                compound=query.compound,
                dose_uM=query.dose_uM,
                timepoint_h=query.timepoint_h,
                plate_id=f"Phase1_Agent",
                day=1,
                operator='Agent',
                is_sentinel=False
            )

            result = self.hardware._execute_well(well)

            if result:
                for ch in ['er', 'mito', 'nucleus', 'actin', 'rna']:
                    morphology_replicates[ch].append(result['morphology'][ch])
                # Viability is stored as ldh_viability in the result
                viability_replicates.append(result.get('ldh_viability', result.get('viability', 1.0)))

        self.budget_remaining -= query.n_wells

        query_result = QueryResult(
            query=query,
            morphology=morphology_replicates,
            viability=viability_replicates
        )

        self.results.append(query_result)

        logger.info(f"Budget remaining: {self.budget_remaining}/{self.budget}")
        return query_result

    def acquisition_function(self) -> ExperimentQuery:
        """
        Choose next experimental condition to query.

        Strategy (simple greedy for now):
        1. If < 20% of budget spent: Random exploration
        2. Else: Exploit - sample around conditions with high separation ratio

        Returns:
            Next experimental query to execute
        """
        budget_used = self.budget - self.budget_remaining
        exploration_threshold = int(0.2 * self.budget)

        # Phase 1: Random exploration
        if budget_used < exploration_threshold:
            return self._random_query()

        # Phase 2: Exploitation - focus on informative regions
        return self._exploit_query()

    def _random_query(self) -> ExperimentQuery:
        """Generate random query for exploration."""
        return ExperimentQuery(
            compound=np.random.choice(self.compounds),
            dose_uM=np.random.choice(self.doses_relative) * 30.0,  # Assume IC50~30µM for simplicity
            timepoint_h=np.random.choice(self.timepoints),
            cell_line=np.random.choice(self.cell_lines),
            n_wells=3  # 3 replicates for noise estimation
        )

    def _exploit_query(self) -> ExperimentQuery:
        """
        Choose query to maximize expected information gain.

        Simple heuristic: Find dose/timepoint with best separation so far,
        sample more compounds at those conditions.
        """
        # Group results by (dose, timepoint)
        from collections import defaultdict
        condition_results = defaultdict(list)

        for result in self.results:
            key = (result.query.dose_uM, result.query.timepoint_h)
            condition_results[key].append(result)

        # Compute separation ratio for each condition
        best_separation = 0.0
        best_condition = None

        for condition, results in condition_results.items():
            if len(results) >= 2:
                sep_ratio = InformationMetrics.compute_separation_ratio(
                    results, self.stress_class_map
                )
                if sep_ratio > best_separation:
                    best_separation = sep_ratio
                    best_condition = condition

        # If found good condition, sample more compounds there
        if best_condition:
            dose, timepoint = best_condition
            # Sample compound we haven't tested much at this condition
            tested_compounds = [r.query.compound for r in condition_results[best_condition]]
            untested = [c for c in self.compounds if c not in tested_compounds]

            if untested:
                compound = np.random.choice(untested)
            else:
                compound = np.random.choice(self.compounds)

            return ExperimentQuery(
                compound=compound,
                dose_uM=dose,
                timepoint_h=timepoint,
                cell_line=np.random.choice(self.cell_lines),
                n_wells=3
            )

        # Fallback to random
        return self._random_query()

    def run_campaign(self, n_iterations: int = 10) -> Dict[str, Any]:
        """
        Run autonomous campaign for n iterations.

        Args:
            n_iterations: Number of query batches to execute

        Returns:
            Campaign summary with final metrics
        """
        logger.info(f"Starting Phase 1 campaign: {n_iterations} iterations")

        iteration_stats = []

        for iteration in range(n_iterations):
            logger.info(f"\n=== Iteration {iteration + 1}/{n_iterations} ===")

            # Choose next query
            query = self.acquisition_function()

            # Execute query
            result = self.execute_query(query)

            # Compute current separation ratio
            if len(self.results) >= 4:
                sep_ratio = InformationMetrics.compute_separation_ratio(
                    self.results, self.stress_class_map
                )
            else:
                sep_ratio = 0.0

            iteration_stats.append({
                'iteration': iteration + 1,
                'query': str(query),
                'separation_ratio': sep_ratio,
                'budget_remaining': self.budget_remaining
            })

            logger.info(f"Separation ratio: {sep_ratio:.3f}")
            logger.info(f"Budget: {self.budget_remaining}/{self.budget}")

        # Final analysis
        summary = self._generate_summary(iteration_stats)
        return summary

    def _generate_summary(self, iteration_stats: List[Dict]) -> Dict[str, Any]:
        """Generate campaign summary with key findings."""

        # Analyze which dose/timepoint ranges were most sampled
        from collections import Counter
        dose_counts = Counter([r.query.dose_uM for r in self.results])
        timepoint_counts = Counter([r.query.timepoint_h for r in self.results])

        # Final separation ratio
        final_separation = InformationMetrics.compute_separation_ratio(
            self.results, self.stress_class_map
        )

        summary = {
            'total_queries': len(self.results),
            'budget_used': self.budget - self.budget_remaining,
            'final_separation_ratio': final_separation,
            'most_sampled_doses': dose_counts.most_common(3),
            'most_sampled_timepoints': timepoint_counts.most_common(3),
            'iteration_stats': iteration_stats
        }

        logger.info(f"\n{'='*60}")
        logger.info("CAMPAIGN SUMMARY")
        logger.info(f"{'='*60}")
        logger.info(f"Total queries: {summary['total_queries']}")
        logger.info(f"Budget used: {summary['budget_used']}/{self.budget}")
        logger.info(f"Final separation ratio: {final_separation:.3f}")
        logger.info(f"Most sampled doses: {summary['most_sampled_doses']}")
        logger.info(f"Most sampled timepoints: {summary['most_sampled_timepoints']}")

        return summary
