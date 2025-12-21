"""
Experimental Design Validation Tools

Tools for validating and optimizing experimental designs:
- Power analysis (minimum sample size)
- Batch confounding detection
- Replication adequacy
- Optimization suggestions
- Confluence confounding detection (density-matched design enforcement)
"""

import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from scipy import stats
import pandas as pd
from collections import defaultdict


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

    def _predict_contact_pressure(self,
                                  cell_line: str,
                                  time_h: float,
                                  assay: str,
                                  compound: str,
                                  dose_uM: float) -> float:
        """
        Predict contact pressure at readout time using lightweight heuristic model.

        This is a **design-time policy guard**, not a full physical simulation.
        It uses conservative defaults to catch obvious confounding patterns.

        Args:
            cell_line: Cell line name (A549, HepG2, U2OS, 293T)
            time_h: Hours post-treatment
            assay: Assay type (affects readout timing)
            compound: Compound name
            dose_uM: Dose in micromolar

        Returns:
            Predicted contact pressure [0, 1] at readout time

        Contract:
        - Uses nominal seeding fractions and growth rates per cell line
        - Applies crude dose penalty to be conservative (prevent false negatives)
        - Same sigmoid as simulator: c0=0.75, width=0.08
        - Does NOT require running full simulation
        """
        # Nominal defaults (tune these as platform data accumulates)
        defaults = {
            "A549": {"seed_frac": 0.20, "growth_rate_h": 0.035},   # ~20h doubling
            "HepG2": {"seed_frac": 0.25, "growth_rate_h": 0.025},  # ~28h doubling
            "U2OS": {"seed_frac": 0.18, "growth_rate_h": 0.030},   # ~23h doubling
            "293T": {"seed_frac": 0.15, "growth_rate_h": 0.040},   # ~17h doubling
        }

        # Fallback for unknown cell lines
        d = defaults.get(cell_line, {"seed_frac": 0.20, "growth_rate_h": 0.030})

        # Conservative dose effect: assume compounds slow growth unless marked as vehicle
        dose_penalty = 0.0
        if dose_uM > 0 and compound.lower() not in ("dmso", "vehicle", "control", "pbs"):
            # Bounded logarithmic penalty (conservative: assumes mild growth inhibition)
            dose_penalty = min(0.6, 0.08 * np.log10(dose_uM + 1.0))

        # Predict confluence at time
        r = d["growth_rate_h"] * (1.0 - dose_penalty)
        confluence = d["seed_frac"] * np.exp(r * time_h)
        confluence = float(min(1.2, max(0.0, confluence)))  # Cap at 120% (overgrown)

        # Convert to pressure using same sigmoid as simulator
        c0, width = 0.75, 0.08
        x = (confluence - c0) / max(width, 1e-6)
        p = 1.0 / (1.0 + np.exp(-x))
        return float(min(1.0, max(0.0, p)))

    def validate_proposal_for_confluence_confounding(self,
                                                    wells: List[Dict[str, Any]],
                                                    design_id: str,
                                                    threshold: float = 0.15) -> None:
        """
        Validate that proposal does not have confounded density across comparison arms.

        This enforces **density-matched design** as a scientific constraint.
        Comparisons across conditions must be density-matched at readout time,
        or explicitly include a density sentinel arm.

        Args:
            wells: List of well dicts with keys: cell_line, compound, dose_uM, time_h, assay
            design_id: Design identifier (for error reporting)
            threshold: Maximum allowed delta_p across comparison arms (default 0.15)

        Raises:
            ValueError: If confluence confounding detected (with structured details)

        Resolution strategies (three options):
        1. Add a density sentinel arm (compound="DENSITY_SENTINEL")
        2. Add schema support for per-arm seeding density (future)
        3. Mark contact_pressure as explicit covariate (future)

        Contract:
        - Groups wells by (cell_line, time_h, assay) to identify comparison sets
        - Compares only within groups that have multiple conditions (compound, dose)
        - Uses conservative pressure prediction (errs toward rejection)
        - Sentinel escape hatch: wells with compound="DENSITY_SENTINEL" exempt the group
        """
        # Group wells by readout context (cell_line, time_h, assay)
        # These are wells that will be compared against each other
        groups = defaultdict(list)
        for w in wells:
            key = (w["cell_line"], w["time_h"], w["assay"])
            groups[key].append(w)

        # Check each readout group for confluence confounding
        for (cell_line, time_h, assay), group_wells in groups.items():
            # Sentinel escape hatch: if any well is marked as density sentinel, skip this group
            if any(w["compound"] == "DENSITY_SENTINEL" for w in group_wells):
                continue

            # Count unique conditions in this group
            conditions = defaultdict(int)
            for w in group_wells:
                cond_key = (w["compound"], w["dose_uM"])
                conditions[cond_key] += 1

            # Only validate if there are multiple conditions to compare
            if len(conditions) < 2:
                continue

            # Predict pressure for each well
            pressures = []
            for w in group_wells:
                p = self._predict_contact_pressure(
                    cell_line=cell_line,
                    time_h=time_h,
                    assay=assay,
                    compound=w["compound"],
                    dose_uM=w["dose_uM"]
                )
                pressures.append((p, w))

            # Check if delta_p exceeds threshold
            p_vals = [p for p, _ in pressures]
            delta_p = max(p_vals) - min(p_vals)

            if delta_p > threshold:
                # Find worst offenders for structured error details
                worst_high = max(pressures, key=lambda t: t[0])
                worst_low = min(pressures, key=lambda t: t[0])

                # Build structured error message
                message = (
                    f"Design likely confounded by confluence differences across comparison arms.\n"
                    f"  Cell line: {cell_line}, Time: {time_h}h, Assay: {assay}\n"
                    f"  Predicted pressure range: {worst_low[0]:.3f} to {worst_high[0]:.3f} (Δp={delta_p:.3f})\n"
                    f"  Threshold: {threshold:.3f}\n"
                    f"\n"
                    f"  Highest pressure: {worst_high[1]['compound']} @ {worst_high[1]['dose_uM']} µM (p={worst_high[0]:.3f})\n"
                    f"  Lowest pressure: {worst_low[1]['compound']} @ {worst_low[1]['dose_uM']} µM (p={worst_low[0]:.3f})\n"
                    f"\n"
                    f"Resolution strategies:\n"
                    f"  1. Add density sentinel arm: compound='DENSITY_SENTINEL' for this group\n"
                    f"  2. Add schema support for per-arm seeding density (future)\n"
                    f"  3. Mark contact_pressure as explicit covariate (future)"
                )

                # Raise with structured details (using ValueError since we don't import InvalidDesignError here)
                # The bridge layer will catch this and convert to InvalidDesignError
                raise ValueError({
                    "message": message,
                    "violation_code": "confluence_confounding",
                    "design_id": design_id,
                    "threshold": float(threshold),
                    "delta_p": float(delta_p),
                    "cell_line": cell_line,
                    "time_h": float(time_h),
                    "assay": assay,
                    "highest_pressure": {
                        "p": float(worst_high[0]),
                        "compound": worst_high[1]["compound"],
                        "dose_uM": float(worst_high[1]["dose_uM"]),
                    },
                    "lowest_pressure": {
                        "p": float(worst_low[0]),
                        "compound": worst_low[1]["compound"],
                        "dose_uM": float(worst_low[1]["dose_uM"]),
                    },
                    "resolution_strategies": [
                        "Add density sentinel arm: compound='DENSITY_SENTINEL' for this (cell_line, time_h, assay) group",
                        "Add schema support for per-arm seeding density and density-match arms",
                        "Mark contact_pressure as explicit covariate in design schema",
                    ],
                })
