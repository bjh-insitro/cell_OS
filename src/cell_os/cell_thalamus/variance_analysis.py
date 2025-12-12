"""
Variance Analysis for Cell Thalamus

Analyzes variance components to determine if biological factors dominate
technical factors (plate, day, operator).

Includes SPC (Statistical Process Control) for sentinel monitoring.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class VarianceAnalyzer:
    """
    Analyzes variance structure in Cell Thalamus data.

    Goals:
    1. Biological variance (cell_line, compound, dose, time) >> Technical variance
    2. Technical terms (plate, day, operator) < 30% of total
    3. Sentinels within control limits
    """

    def __init__(self, db):
        """
        Initialize variance analyzer.

        Args:
            db: CellThalamusDB instance
        """
        self.db = db

    def analyze_design(self, design_id: str) -> Dict:
        """
        Perform full variance analysis on a design.

        Args:
            design_id: Design ID to analyze

        Returns:
            Dict with variance components, SPC results, and summary
        """
        # Get all results
        results = self.db.get_results(design_id)

        if not results:
            return {"error": "No results found"}

        # Convert to DataFrame
        df = pd.DataFrame(results)

        # Analyze each metric
        metrics = ['atp_signal', 'morph_er', 'morph_mito', 'morph_nucleus', 'morph_actin', 'morph_rna']

        variance_components = {}
        for metric in metrics:
            components = self.compute_variance_components(df, metric)
            variance_components[metric] = components

        # SPC analysis on sentinels
        spc_results = self.sentinel_spc(df)

        # Overall summary
        summary = self.generate_summary(variance_components, spc_results)

        return {
            'variance_components': variance_components,
            'spc_results': spc_results,
            'summary': summary
        }

    def compute_variance_components(self, df: pd.DataFrame, metric: str) -> Dict:
        """
        Compute variance components for a metric.

        Partitions variance into:
        - Biological: cell_line, compound, dose, timepoint
        - Technical: plate, day, operator

        Args:
            df: Results DataFrame
            metric: Metric column name

        Returns:
            Dict with variance components
        """
        # Filter to non-sentinel data
        df_exp = df[df['is_sentinel'] == False].copy()

        if len(df_exp) == 0:
            return {"error": "No experimental data"}

        # Overall variance
        total_var = df_exp[metric].var()

        # Biological factors
        compound_var = self._group_variance(df_exp, metric, 'compound')
        dose_var = self._group_variance(df_exp, metric, 'dose_uM')
        cell_line_var = self._group_variance(df_exp, metric, 'cell_line')
        timepoint_var = self._group_variance(df_exp, metric, 'timepoint_h')

        biological_var = compound_var + dose_var + cell_line_var + timepoint_var

        # Technical factors
        plate_var = self._group_variance(df_exp, metric, 'plate_id')
        day_var = self._group_variance(df_exp, metric, 'day')
        operator_var = self._group_variance(df_exp, metric, 'operator')

        technical_var = plate_var + day_var + operator_var

        # Residual
        residual_var = max(0, total_var - biological_var - technical_var)

        # Fractions
        bio_frac = biological_var / total_var if total_var > 0 else 0
        tech_frac = technical_var / total_var if total_var > 0 else 0
        res_frac = residual_var / total_var if total_var > 0 else 0

        return {
            'total_variance': total_var,
            'biological_variance': biological_var,
            'technical_variance': technical_var,
            'residual_variance': residual_var,
            'biological_fraction': bio_frac,
            'technical_fraction': tech_frac,
            'residual_fraction': res_frac,
            'components': {
                'compound': compound_var,
                'dose': dose_var,
                'cell_line': cell_line_var,
                'timepoint': timepoint_var,
                'plate': plate_var,
                'day': day_var,
                'operator': operator_var
            }
        }

    def _group_variance(self, df: pd.DataFrame, metric: str, factor: str) -> float:
        """
        Compute variance explained by a grouping factor.

        Uses ANOVA-style variance decomposition:
        Var(factor) = Var(group means)

        Args:
            df: DataFrame
            metric: Metric column
            factor: Grouping factor column

        Returns:
            Variance explained by factor
        """
        group_means = df.groupby(factor)[metric].mean()
        overall_mean = df[metric].mean()

        # Variance of group means (weighted by group size)
        group_sizes = df.groupby(factor).size()
        total_size = len(df)

        var_between = sum(
            (group_sizes[g] / total_size) * (group_means[g] - overall_mean) ** 2
            for g in group_means.index
        )

        return var_between

    def sentinel_spc(self, df: pd.DataFrame) -> Dict:
        """
        Perform SPC analysis on sentinel wells.

        Monitors:
        - DMSO baseline (should be stable)
        - Mild stress (should be consistent)
        - Strong stress (should be consistent)

        Args:
            df: Results DataFrame

        Returns:
            SPC results with control limits and out-of-control flags
        """
        # Filter to sentinels only
        df_sent = df[df['is_sentinel'] == True].copy()

        if len(df_sent) == 0:
            return {"error": "No sentinel data"}

        results = {}

        # Analyze each sentinel type
        for compound in df_sent['compound'].unique():
            sent_data = df_sent[df_sent['compound'] == compound]

            # Compute control limits for ATP signal
            atp_mean = sent_data['atp_signal'].mean()
            atp_std = sent_data['atp_signal'].std()

            ucl = atp_mean + 3 * atp_std  # Upper control limit
            lcl = atp_mean - 3 * atp_std  # Lower control limit

            # Flag out-of-control points
            out_of_control = sent_data[
                (sent_data['atp_signal'] > ucl) | (sent_data['atp_signal'] < lcl)
            ]

            results[compound] = {
                'mean': atp_mean,
                'std': atp_std,
                'ucl': ucl,
                'lcl': lcl,
                'n_points': len(sent_data),
                'n_out_of_control': len(out_of_control),
                'in_control': len(out_of_control) == 0
            }

        return results

    def generate_summary(self, variance_components: Dict, spc_results: Dict) -> Dict:
        """
        Generate overall summary of variance analysis.

        Args:
            variance_components: Variance component results
            spc_results: SPC results

        Returns:
            Summary dict with pass/fail criteria
        """
        # Check success criteria
        criteria = {}

        # 1. Biological variance should dominate (>70%)
        bio_fracs = [
            v['biological_fraction']
            for v in variance_components.values()
            if 'biological_fraction' in v
        ]
        avg_bio_frac = np.mean(bio_fracs) if bio_fracs else 0
        criteria['biological_dominance'] = {
            'value': avg_bio_frac,
            'threshold': 0.7,
            'pass': avg_bio_frac > 0.7
        }

        # 2. Technical variance should be controlled (<30%)
        tech_fracs = [
            v['technical_fraction']
            for v in variance_components.values()
            if 'technical_fraction' in v
        ]
        avg_tech_frac = np.mean(tech_fracs) if tech_fracs else 0
        criteria['technical_control'] = {
            'value': avg_tech_frac,
            'threshold': 0.3,
            'pass': avg_tech_frac < 0.3
        }

        # 3. Sentinels should be in control
        if 'error' not in spc_results:
            sentinels_in_control = all(
                v['in_control'] for v in spc_results.values()
            )
            criteria['sentinel_stability'] = {
                'sentinels_in_control': sentinels_in_control,
                'pass': sentinels_in_control
            }
        else:
            criteria['sentinel_stability'] = {'pass': False, 'error': 'No sentinel data'}

        # Overall pass
        all_pass = all(c['pass'] for c in criteria.values())

        return {
            'criteria': criteria,
            'overall_pass': all_pass,
            'biological_fraction_mean': avg_bio_frac,
            'technical_fraction_mean': avg_tech_frac
        }

    def get_dose_response_summary(self, design_id: str, compound: str,
                                  cell_line: str, metric: str = 'atp_signal') -> Dict:
        """
        Get dose-response summary for a specific compound/cell line.

        Args:
            design_id: Design ID
            compound: Compound name
            cell_line: Cell line name
            metric: Metric to analyze

        Returns:
            Dose-response summary with statistics
        """
        data = self.db.get_dose_response_data(design_id, compound, cell_line, metric)

        if not data:
            return {"error": "No data found"}

        # Group by dose and compute statistics
        dose_groups = {}
        for dose, value in data:
            if dose not in dose_groups:
                dose_groups[dose] = []
            dose_groups[dose].append(value)

        summary = {}
        for dose, values in dose_groups.items():
            summary[dose] = {
                'n': len(values),
                'mean': np.mean(values),
                'std': np.std(values),
                'sem': np.std(values) / np.sqrt(len(values)) if len(values) > 0 else 0
            }

        return summary
