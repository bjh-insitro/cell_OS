"""
Experimental Design Validation Tools

Tools for validating and optimizing experimental designs:
- Power analysis (minimum sample size)
- Batch confounding detection
- Replication adequacy
- Optimization suggestions
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from scipy import stats
import pandas as pd


@dataclass
class PowerAnalysisResult:
    """Result of statistical power analysis."""
    required_sample_size: int
    achieved_power: float
    effect_size: float
    alpha: float
    test_type: str
    recommendation: str


@dataclass
class BatchConfoundingResult:
    """Result of batch confounding analysis."""
    is_confounded: bool
    confounding_score: float  # 0-1, higher = worse
    problematic_batches: List[str]
    recommendation: str
    suggested_layout: Optional[Dict] = None


@dataclass
class ReplicationResult:
    """Result of replication adequacy analysis."""
    is_adequate: bool
    current_replicates: int
    recommended_replicates: int
    cv_estimate: float
    confidence_interval_width: float
    recommendation: str


class ExperimentalDesignValidator:
    """
    Validate and optimize experimental designs.
    
    Helps ensure experiments are properly powered and controlled.
    """
    
    def __init__(self):
        pass
    
    def power_analysis(self,
                      effect_size: float,
                      alpha: float = 0.05,
                      power: float = 0.80,
                      test_type: str = "t-test") -> PowerAnalysisResult:
        """
        Calculate required sample size for desired statistical power.
        
        Args:
            effect_size: Expected effect size (Cohen's d)
            alpha: Significance level (default 0.05)
            power: Desired statistical power (default 0.80)
            test_type: Type of statistical test
            
        Returns:
            PowerAnalysisResult with sample size recommendation
        """
        # Simplified power calculation for t-test
        # For more complex designs, use statsmodels or similar
        
        if test_type == "t-test":
            # Two-sample t-test
            # n ≈ 2 * (z_alpha + z_beta)^2 / d^2
            z_alpha = stats.norm.ppf(1 - alpha/2)
            z_beta = stats.norm.ppf(power)
            
            n_per_group = 2 * ((z_alpha + z_beta) / effect_size) ** 2
            n_per_group = int(np.ceil(n_per_group))
            
            # Calculate achieved power with this n
            ncp = effect_size * np.sqrt(n_per_group / 2)  # Non-centrality parameter
            achieved_power = 1 - stats.nct.cdf(
                stats.t.ppf(1 - alpha/2, 2*n_per_group - 2),
                2*n_per_group - 2,
                ncp
            )
            
            # Recommendation
            if n_per_group < 3:
                rec = "⚠️  Very small sample size - consider larger effect or lower power"
            elif n_per_group > 100:
                rec = "⚠️  Large sample size required - consider if effect is practically significant"
            else:
                rec = f"✓ Use {n_per_group} samples per group for {power:.0%} power"
            
            return PowerAnalysisResult(
                required_sample_size=n_per_group * 2,  # Total for both groups
                achieved_power=achieved_power,
                effect_size=effect_size,
                alpha=alpha,
                test_type=test_type,
                recommendation=rec
            )
        
        else:
            raise NotImplementedError(f"Power analysis for {test_type} not yet implemented")
    
    def detect_batch_confounding(self,
                                design: pd.DataFrame,
                                treatment_col: str = "treatment",
                                batch_col: str = "batch") -> BatchConfoundingResult:
        """
        Detect if experimental batches are confounded with treatments.
        
        Args:
            design: DataFrame with experimental design
            treatment_col: Column name for treatment groups
            batch_col: Column name for batch assignments
            
        Returns:
            BatchConfoundingResult with confounding assessment
        """
        # Create contingency table
        contingency = pd.crosstab(design[treatment_col], design[batch_col])
        
        # Perfect confounding: each treatment in only one batch
        # Check if any treatment appears in only one batch
        treatments_per_batch = (contingency > 0).sum(axis=1)
        confounded_treatments = treatments_per_batch[treatments_per_batch == 1].index.tolist()
        
        # Calculate confounding score using chi-square
        chi2, p_value, dof, expected = stats.chi2_contingency(contingency)
        
        # Normalized confounding score (0 = no confounding, 1 = perfect confounding)
        # Based on how much observed deviates from expected
        confounding_score = 1.0 - p_value  # Low p-value = high confounding
        
        is_confounded = confounding_score > 0.7 or len(confounded_treatments) > 0
        
        # Generate recommendation
        if is_confounded:
            rec = f"⚠️  Batch confounding detected! Treatments {confounded_treatments} are confounded with batches."
            rec += "\n   Recommendation: Randomize treatments across batches."
            
            # Suggest better layout
            suggested = self._suggest_balanced_layout(design, treatment_col, batch_col)
        else:
            rec = "✓ No significant batch confounding detected."
            suggested = None
        
        return BatchConfoundingResult(
            is_confounded=is_confounded,
            confounding_score=confounding_score,
            problematic_batches=confounded_treatments,
            recommendation=rec,
            suggested_layout=suggested
        )
    
    def _suggest_balanced_layout(self,
                                design: pd.DataFrame,
                                treatment_col: str,
                                batch_col: str) -> Dict:
        """Suggest a balanced experimental layout."""
        treatments = design[treatment_col].unique()
        n_batches = design[batch_col].nunique()
        n_per_treatment = len(design) // len(treatments)
        
        # Simple balanced design: distribute each treatment evenly across batches
        suggested = []
        for treatment in treatments:
            samples_per_batch = n_per_treatment // n_batches
            for batch_idx in range(n_batches):
                for _ in range(samples_per_batch):
                    suggested.append({
                        treatment_col: treatment,
                        batch_col: f"Batch_{batch_idx + 1}"
                    })
        
        return {"balanced_design": pd.DataFrame(suggested)}
    
    def assess_replication(self,
                          expected_cv: float,
                          desired_ci_width: float = 0.2,
                          confidence_level: float = 0.95) -> ReplicationResult:
        """
        Assess if replication is adequate for desired precision.
        
        Args:
            expected_cv: Expected coefficient of variation
            desired_ci_width: Desired confidence interval width (as fraction of mean)
            confidence_level: Confidence level (default 95%)
            
        Returns:
            ReplicationResult with replication recommendation
        """
        # For a given CV and desired CI width, calculate required n
        # CI width ≈ 2 * t * (CV / sqrt(n))
        # Solving for n: n = (2 * t * CV / width)^2
        
        # Use t-distribution (conservative)
        # Start with n=3 and iterate
        for n in range(3, 101):
            t_crit = stats.t.ppf((1 + confidence_level) / 2, n - 1)
            ci_width = 2 * t_crit * (expected_cv / np.sqrt(n))
            
            if ci_width <= desired_ci_width:
                recommended_n = n
                break
        else:
            recommended_n = 100  # Cap at 100
        
        # Assess current replication (assume minimum of 3)
        current_n = 3
        t_crit_current = stats.t.ppf((1 + confidence_level) / 2, current_n - 1)
        current_ci_width = 2 * t_crit_current * (expected_cv / np.sqrt(current_n))
        
        is_adequate = current_ci_width <= desired_ci_width
        
        # Recommendation
        if is_adequate:
            rec = f"✓ {current_n} replicates sufficient for {desired_ci_width:.0%} CI width"
        else:
            rec = f"⚠️  Need {recommended_n} replicates for {desired_ci_width:.0%} CI width"
            rec += f"\n   Current {current_n} replicates give {current_ci_width:.0%} CI width"
        
        return ReplicationResult(
            is_adequate=is_adequate,
            current_replicates=current_n,
            recommended_replicates=recommended_n,
            cv_estimate=expected_cv,
            confidence_interval_width=current_ci_width,
            recommendation=rec
        )
    
    def optimize_plate_layout(self,
                             treatments: List[str],
                             replicates: int,
                             plate_rows: int = 8,
                             plate_cols: int = 12,
                             randomize: bool = True) -> pd.DataFrame:
        """
        Optimize plate layout to minimize edge effects and batch confounding.
        
        Args:
            treatments: List of treatment names
            replicates: Number of replicates per treatment
            plate_rows: Number of rows in plate
            plate_cols: Number of columns in plate
            randomize: Whether to randomize positions
            
        Returns:
            DataFrame with optimized plate layout
        """
        total_wells = len(treatments) * replicates
        max_wells = plate_rows * plate_cols
        
        if total_wells > max_wells:
            raise ValueError(f"Too many samples ({total_wells}) for plate ({max_wells} wells)")
        
        # Create layout
        layout = []
        for treatment in treatments:
            for rep in range(replicates):
                layout.append({
                    "treatment": treatment,
                    "replicate": rep + 1
                })
        
        # Assign well positions
        # Strategy: avoid edges for critical samples, randomize within constraints
        well_positions = []
        
        # Identify edge wells
        edge_wells = set()
        for row in range(plate_rows):
            for col in range(plate_cols):
                if row == 0 or row == plate_rows - 1 or col == 0 or col == plate_cols - 1:
                    edge_wells.add((row, col))
        
        # Identify inner wells (preferred)
        inner_wells = []
        for row in range(1, plate_rows - 1):
            for col in range(1, plate_cols - 1):
                inner_wells.append((row, col))
        
        # Assign inner wells first
        if randomize:
            np.random.shuffle(inner_wells)
        
        for i, sample in enumerate(layout):
            if i < len(inner_wells):
                row, col = inner_wells[i]
            else:
                # Use edge wells if needed
                edge_list = list(edge_wells)
                if randomize:
                    np.random.shuffle(edge_list)
                row, col = edge_list[i - len(inner_wells)]
            
            well_id = f"{chr(ord('A') + row)}{col + 1}"
            sample["well_id"] = well_id
            sample["row"] = row
            sample["col"] = col
            sample["is_edge"] = (row, col) in edge_wells
        
        return pd.DataFrame(layout)
    
    def validate_design(self,
                       design: pd.DataFrame,
                       treatment_col: str = "treatment",
                       batch_col: Optional[str] = None) -> Dict[str, any]:
        """
        Comprehensive validation of experimental design.
        
        Args:
            design: DataFrame with experimental design
            treatment_col: Column name for treatments
            batch_col: Optional column name for batches
            
        Returns:
            Dict with validation results and recommendations
        """
        results = {}
        
        # Check balance
        treatment_counts = design[treatment_col].value_counts()
        is_balanced = treatment_counts.std() / treatment_counts.mean() < 0.1
        results["balanced"] = is_balanced
        results["treatment_counts"] = treatment_counts.to_dict()
        
        # Check batch confounding if batch column provided
        if batch_col and batch_col in design.columns:
            batch_result = self.detect_batch_confounding(design, treatment_col, batch_col)
            results["batch_confounding"] = batch_result
        
        # Check replication
        min_reps = treatment_counts.min()
        results["min_replicates"] = min_reps
        results["replication_adequate"] = min_reps >= 3
        
        # Overall recommendation
        issues = []
        if not is_balanced:
            issues.append("Unbalanced design")
        if batch_col and results.get("batch_confounding", {}).is_confounded:
            issues.append("Batch confounding detected")
        if min_reps < 3:
            issues.append("Insufficient replication")
        
        if issues:
            results["overall"] = "⚠️  Issues detected: " + ", ".join(issues)
        else:
            results["overall"] = "✓ Design looks good!"
        
        return results
