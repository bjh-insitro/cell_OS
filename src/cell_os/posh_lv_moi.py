"""
POSH LV & MOI Modeling Agent.

This module handles the design of Lentiviral (LV) batches and titration experiments
for POSH screens. It utilizes a Censored, Saturation-Aware Poisson model to infer
functional titer, filters experimental noise via RANSAC, and performs Bayesian
optimization for autonomous experiment steering and scale-up risk assessment.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
from scipy.optimize import curve_fit
from scipy.stats import norm
from sklearn.linear_model import RANSACRegressor, LinearRegression

from cell_os.lab_world_model import LabWorldModel
from cell_os.posh_scenario import POSHScenario
from cell_os.posh_library_design import POSHLibrary


class LVDesignError(Exception):
    """Raised when LV design or modeling fails."""
    pass


# --- Dataclasses ---

@dataclass
class LVBatch:
    """Represents a lentiviral batch for a POSH library."""
    name: str
    volume_ul_total: float          # total available volume
    titer_TU_per_ml: float          # transducing units per mL
    library: POSHLibrary            # link back to library
    notes: str = ""
    aliquot_count: int = 1
    aliquot_volume_ul: float = 0.0  # volume per aliquot


@dataclass
class LVTitrationPlan:
    """Experiment design for LV titration in a given cell line."""
    cell_line: str
    plate_format: str               # e.g. "96", "24", "6"
    cells_per_well: int
    lv_volumes_ul: List[float]      # volumes to test, per well
    replicates_per_condition: int


@dataclass
class LVTitrationResult:
    """Observed data from an LV titration."""
    cell_line: str
    data: pd.DataFrame  # columns: volume_ul, fraction_bfp (0.0-1.0)


@dataclass
class TiterPosterior:
    """Bayesian posterior distribution over the Titer."""
    grid_titer: np.ndarray     # The x-axis (potential titers)
    probs: np.ndarray          # The y-axis (probability density)
    ci_95: Tuple[float, float] # 95% Credible Interval


@dataclass
class LVTransductionModel:
    """
    Fitted Poisson model for a given cell line.
    
    Model: BFP_frac = alpha * (1 - exp(- (Volume * Titer) / Cells ))
    """
    cell_line: str
    titer_tu_ul: float        # Inferred Transducing Units per uL
    max_infectivity: float    # Alpha parameter (0.0 - 1.0)
    cells_per_well: int       # Reference cell count used for fitting
    r_squared: float
    posterior: Optional[TiterPosterior] = None
    outliers: List[int] = field(default_factory=list) # Indices of dropped data points

    def predict_bfp(self, volume_ul: float) -> float:
        """Predict BFP fraction for a given LV volume."""
        if volume_ul < 0: return 0.0
        moi = (volume_ul * self.titer_tu_ul) / self.cells_per_well
        return self.max_infectivity * (1.0 - np.exp(-moi))

    def predict_moi_from_vol(self, volume_ul: float) -> float:
        """Predict theoretical MOI for a given volume."""
        return (volume_ul * self.titer_tu_ul) / self.cells_per_well

    def volume_for_moi(self, target_moi: float) -> float:
        """Calculate LV volume needed to achieve target MOI (Theoretical)."""
        # MOI = (Vol * Titer) / Cells  => Vol = (MOI * Cells) / Titer
        if self.titer_tu_ul <= 0:
             raise LVDesignError(f"Titer is 0 for {self.cell_line}, cannot solve for volume.")
        
        vol = (target_moi * self.cells_per_well) / self.titer_tu_ul
        return vol
    
    def volume_for_target_bfp(self, target_bfp: float) -> float:
        """Calculate LV volume needed to hit a specific BFP%."""
        if target_bfp >= self.max_infectivity:
            raise LVDesignError(f"Target BFP {target_bfp} exceeds max infectivity {self.max_infectivity}")
        
        # Inverse of: y = a * (1 - e^(-VT/N))
        # V = - (N / T) * ln(1 - y/a)
        term = 1.0 - (target_bfp / self.max_infectivity)
        if term <= 0: return 0.0 
        
        vol = - (self.cells_per_well / self.titer_tu_ul) * np.log(term)
        return vol


@dataclass
class LVDesignBundle:
    """Container for all LV-related design artifacts."""
    batch: LVBatch
    titration_plans: Dict[str, LVTitrationPlan]
    models: Dict[str, LVTransductionModel] = field(default_factory=dict)


@dataclass
class ScreenConfig:
    """Configuration for scaling up to a large screen."""
    num_guides: int = 4000         # Total guides in library
    coverage_target: int = 1000    # Cells per guide (post-selection)
    target_bfp: float = 0.30       # Target Transduction efficiency
    bfp_tolerance: Tuple[float, float] = (0.25, 0.35) # Acceptable BFP range
    
    # Process Noise Parameters (The "Real World" Mess)
    cell_counting_error: float = 0.10  # 10% error in counting 13M cells
    pipetting_error: float = 0.05      # 5% error in adding virus volume


# --- Core Physics Functions ---

def _poisson_curve(vol, titer, n_cells, alpha):
    """The physical model: y = alpha * (1 - e^(-vol * titer / n_cells))"""
    moi = (vol * titer) / n_cells
    return alpha * (1.0 - np.exp(-moi))


def _calculate_posterior(
    df_clean: pd.DataFrame, 
    best_titer: float, 
    n_cells: int, 
    alpha: float
) -> TiterPosterior:
    """
    Computes a grid approximation of the posterior probability of Titer.
    Assumes Gaussian noise on BFP measurements.
    """
    # 1. Define Grid (0.1x to 3x of the point estimate)
    grid_size = 1000
    t_min = max(100, best_titer * 0.1)
    t_max = best_titer * 3.0
    titer_grid = np.linspace(t_min, t_max, grid_size)
    
    # 2. Compute Likelihoods
    log_likelihoods = np.zeros_like(titer_grid)
    
    # Estimate sigma from residuals of best fit
    y_pred_best = _poisson_curve(df_clean['volume_ul'], best_titer, n_cells, alpha)
    residuals = df_clean['fraction_bfp'] - y_pred_best
    sigma = np.std(residuals) + 1e-6 # Avoid div by zero
    
    for i, t in enumerate(titer_grid):
        y_pred = _poisson_curve(df_clean['volume_ul'], t, n_cells, alpha)
        # Sum of log-pdf for all points
        ll = norm.logpdf(df_clean['fraction_bfp'], loc=y_pred, scale=sigma).sum()
        log_likelihoods[i] = ll
        
    # 3. Normalize to Probability
    # Subtract max to prevent underflow/overflow in exp
    probs = np.exp(log_likelihoods - np.max(log_likelihoods))
    probs /= probs.sum()
    
    # 4. Calculate CI
    cumsum = np.cumsum(probs)
    low_idx = np.searchsorted(cumsum, 0.025)
    high_idx = np.searchsorted(cumsum, 0.975)
    
    return TiterPosterior(
        grid_titer=titer_grid,
        probs=probs,
        ci_95=(titer_grid[low_idx], titer_grid[high_idx])
    )


# --- Workflow Functions ---

def design_lv_batch(
    world: LabWorldModel, 
    scenario: POSHScenario, 
    library: POSHLibrary,
    aliquot_count: int = 10,
    aliquot_volume_ul: float = 50.0
) -> LVBatch:
    """Create a synthetic LVBatch description."""
    total_vol = aliquot_count * aliquot_volume_ul
    
    return LVBatch(
        name=f"LV_{scenario.name}",
        volume_ul_total=total_vol,
        titer_TU_per_ml=0.0, # Unknown initially
        library=library,
        notes="Designed by POSH Agent",
        aliquot_count=aliquot_count,
        aliquot_volume_ul=aliquot_volume_ul
    )


def design_lv_titration_plan(
    world: LabWorldModel,
    scenario: POSHScenario,
    lv_batch: LVBatch,
    cell_line: str,
    plate_format: Optional[str] = None,
    cells_per_well: Optional[int] = None,
    lv_volumes_ul: Optional[List[float]] = None,
) -> LVTitrationPlan:
    """Design a titration experiment for one cell line."""
    _plate_format = plate_format or "6"
    _cells_per_well = cells_per_well or 100000
    
    if lv_volumes_ul:
        _volumes = lv_volumes_ul
    else:
        # Standard initial spread
        _volumes = [0.1, 0.3, 0.5, 1.0, 3.0, 5.0, 10.0]
    
    return LVTitrationPlan(
        cell_line=cell_line,
        plate_format=_plate_format,
        cells_per_well=_cells_per_well,
        lv_volumes_ul=_volumes,
        replicates_per_condition=1
    )


def fit_lv_transduction_model(
    scenario: POSHScenario,
    lv_batch: LVBatch,
    titration_result: LVTitrationResult,
    n_cells_override: int = 100000 # Default for 6-well if not in result
) -> LVTransductionModel:
    """
    Fits the Saturation-Aware Poisson Model to titration data.
    
    Steps:
    1. Linearize data (approx MOI) and use RANSAC to identify corrupted wells.
    2. Run Non-Linear Least Squares (Curve Fit) on inliers to find Titer & Alpha.
    3. Generate Bayesian Posterior for risk assessment.
    """
    df = titration_result.data.copy()
    
    # Validation
    required_cols = {'volume_ul', 'fraction_bfp'}
    if not required_cols.issubset(df.columns):
        raise LVDesignError(f"Dataframe missing columns. Found: {df.columns}")
        
    # 0. Pre-process: Clip physical bounds
    df = df[(df['fraction_bfp'] > 0.001) & (df['fraction_bfp'] < 0.999)].copy()
    if len(df) < 2:
         # Not enough data to fit anything useful
         # Return a zeroed model or raise error depending on policy
         # Here we assume we can't proceed
         raise LVDesignError(f"Insufficient valid data points for {titration_result.cell_line}")

    # 1. RANSAC Outlier Detection
    # Transform to Linear Space: MOI approx -ln(1 - BFP)
    # This is only valid for BFP < 0.8 roughly, but good enough for outlier detection
    df['linear_y'] = -np.log(1.0 - df['fraction_bfp'])
    
    X = df[['volume_ul']].values
    y = df['linear_y'].values
    
    # RANSAC Regressor
    # We need enough samples; if N is small, adjust params
    min_samples = max(2, int(len(df) * 0.5))
    try:
        ransac = RANSACRegressor(min_samples=min_samples, residual_threshold=0.5, random_state=42)
        ransac.fit(X, y)
        inlier_mask = ransac.inlier_mask_
        outlier_indices = df.index[~inlier_mask].tolist()
        df_clean = df[inlier_mask].copy()
    except Exception:
        # If RANSAC fails (e.g. perfect line or too few points), use all data
        df_clean = df
        outlier_indices = []
    
    if len(df_clean) < 2:
        df_clean = df
        outlier_indices = []

    # 2. Non-Linear Least Squares (Physics Model)
    # We fit Titer (T) and Max Infectivity (Alpha)
    
    # Initial Guess:
    # Estimate slope k from linear regression of clean data
    lr = LinearRegression().fit(df_clean[['volume_ul']], df_clean['linear_y'])
    slope_est = lr.coef_[0] # slope = Titer / N_cells
    titer_guess = slope_est * n_cells_override
    p0 = [max(1000, titer_guess), 0.98] # Guess Titer, Alpha=0.98
    
    # Bounds: Titer > 0, 0.5 < Alpha <= 1.0
    bounds = ([0, 0.5], [np.inf, 1.0])
    
    try:
        popt, pcov = curve_fit(
            lambda v, t, a: _poisson_curve(v, t, n_cells_override, a),
            df_clean['volume_ul'],
            df_clean['fraction_bfp'],
            p0=p0,
            bounds=bounds,
            maxfev=5000
        )
        titer_est, alpha_est = popt
    except RuntimeError:
        raise LVDesignError(f"Curve fit failed for {titration_result.cell_line}")

    # 3. Calculate R^2 on clean data
    y_pred = _poisson_curve(df_clean['volume_ul'], titer_est, n_cells_override, alpha_est)
    ss_res = np.sum((df_clean['fraction_bfp'] - y_pred) ** 2)
    ss_tot = np.sum((df_clean['fraction_bfp'] - np.mean(df_clean['fraction_bfp'])) ** 2)
    r2 = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

    # 4. Generate Posterior
    posterior = _calculate_posterior(df_clean, titer_est, n_cells_override, alpha_est)

    return LVTransductionModel(
        cell_line=titration_result.cell_line,
        titer_tu_ul=titer_est,
        max_infectivity=alpha_est,
        cells_per_well=n_cells_override,
        r_squared=r2,
        posterior=posterior,
        outliers=outlier_indices
    )


def design_lv_for_scenario(
    world: LabWorldModel,
    scenario: POSHScenario,
    library: POSHLibrary,
) -> LVDesignBundle:
    """
    Convenience function:
    - create LVBatch
    - design titration plan for each cell line
    """
    batch = design_lv_batch(world, scenario, library)
    
    plans = {}
    for cell_line in scenario.cell_lines:
        plans[cell_line] = design_lv_titration_plan(world, scenario, batch, cell_line)
        
    return LVDesignBundle(
        batch=batch,
        titration_plans=plans,
        models={}
    )


# --- Autonomous Exploration Agent ---

class LVAutoExplorer:
    """
    Active Learning agent that suggests the optimal next volumes to test
    based on the current model's uncertainty.
    """
    def __init__(self, scenario: POSHScenario, batch: LVBatch):
        self.scenario = scenario
        self.batch = batch

    def suggest_next_volumes(
        self, 
        current_results: LVTitrationResult, 
        n_suggestions: int = 2
    ) -> List[float]:
        """
        Suggests volumes to resolve uncertainty, prioritizing the range near target MOI.
        """
        # 1. Fit current model
        try:
            model = fit_lv_transduction_model(self.scenario, self.batch, current_results)
        except LVDesignError:
            # Fallback if fit fails
            return self._heuristic_recovery(current_results)

        # 2. Heuristic Checks (Guardrails)
        max_bfp = current_results.data['fraction_bfp'].max()
        max_vol = current_results.data['volume_ul'].max()
        min_bfp = current_results.data['fraction_bfp'].min()
        min_vol = current_results.data['volume_ul'].min()
        
        # If signal is lost in noise floor (<5%), push drastically higher
        if max_bfp < 0.05:
            return [max_vol * 2.0, max_vol * 4.0][:n_suggestions]
        
        # If signal is instantly saturated (>80% at lowest vol), push lower
        if min_bfp > 0.80:
            return [min_vol * 0.5, min_vol * 0.1][:n_suggestions]

        # 3. Bayesian Utility: Maximize Information Gain
        candidates = np.geomspace(0.1, 20.0, 100)
        
        # Sample curves from posterior
        sampled_titers = np.random.choice(
            model.posterior.grid_titer, 
            size=50, 
            p=model.posterior.probs
        )
        
        # Calculate BFP predictions
        alpha = model.max_infectivity
        N = model.cells_per_well
        
        predictions = []
        for t in sampled_titers:
            moi = (candidates * t) / N
            pred = alpha * (1 - np.exp(-moi))
            predictions.append(pred)
            
        predictions = np.array(predictions)
        
        # Calculate Variance (Uncertainty)
        variances = np.var(predictions, axis=0)
        
        # Relevance Weighting: Focus on variance near target BFP (e.g. 0.25 - 0.35)
        # We use a gaussian weight centered at 0.30
        mean_preds = np.mean(predictions, axis=0)
        target_bfp = 0.30
        relevance = np.exp(-0.5 * ((mean_preds - target_bfp) / 0.15)**2)
        
        utility = variances * relevance
        
        # Pick best volumes
        best_indices = np.argsort(utility)[::-1]
        
        suggestions = []
        for idx in best_indices:
            vol = candidates[idx]
            # Avoid repeating existing volumes
            if not any(np.isclose(vol, current_results.data['volume_ul'], rtol=0.2)):
                suggestions.append(round(vol, 2))
            if len(suggestions) >= n_suggestions:
                break
                
        return suggestions

    def _heuristic_recovery(self, result):
        return [1.0, 5.0]


# --- Simulation & Risk Assessment ---

class ScreenSimulator:
    """
    Monte Carlo engine to stress-test the 'One Shot' scaling experiment.
    
    It combines Titer Posterior uncertainty with Process Noise (pipetting/counting)
    to calculate the Probability of Success (PoS).
    """
    def __init__(self, model: LVTransductionModel, config: ScreenConfig):
        self.model = model
        self.config = config
        
        if not self.model.posterior:
            raise LVDesignError("Model has no posterior. Cannot run risk simulation.")
        
        # Calculate Requirements
        # 1. Cells needed surviving = Guides * Coverage
        self.surviving_cells_needed = config.num_guides * config.coverage_target
        
        # 2. Total cells to transduce = Surviving / Target Efficiency
        self.total_cells_target = int(self.surviving_cells_needed / config.target_bfp)
        
        # 3. Calculate Target Volume based on the model's Point Estimate
        # Vol = (MOI * Cells) / Titer
        target_moi = -np.log(1.0 - config.target_bfp)
        
        if self.model.titer_tu_ul <= 0:
            self.target_vol_ul = 0.0
        else:
            self.target_vol_ul = (target_moi * self.total_cells_target) / self.model.titer_tu_ul

    def run_monte_carlo(self, n_sims: int = 5000) -> np.ndarray:
        """
        Simulates the 'One Shot' flask experiment n_sims times.
        Returns array of resulting BFP fractions.
        """
        # 1. Sample Titers from our Posterior (The Uncertainty in the Virus)
        sampled_titers = np.random.choice(
            self.model.posterior.grid_titer, 
            size=n_sims, 
            p=self.model.posterior.probs
        )
        
        # 2. Simulate Process Noise (The Uncertainty in the Human/Robot)
        # A. Actual Cells Plated (Normal Dist around target)
        actual_cells = np.random.normal(
            self.total_cells_target, 
            self.total_cells_target * self.config.cell_counting_error,
            n_sims
        )
        
        # B. Actual Volume Added (Normal Dist around target volume)
        actual_vol = np.random.normal(
            self.target_vol_ul,
            self.target_vol_ul * self.config.pipetting_error,
            n_sims
        )
        
        # C. Physics: Calculate resulting MOI & BFP
        # MOI = (Vol * Titer) / Cells
        moi_sim = (actual_vol * sampled_titers) / actual_cells
        
        # BFP = alpha * (1 - e^-MOI)
        bfp_sim = self.model.max_infectivity * (1.0 - np.exp(-moi_sim))
        
        return bfp_sim

    def get_probability_of_success(self) -> float:
        """Returns the probability (0.0 - 1.0) that the screen lands in the tolerance zone."""
        outcomes = self.run_monte_carlo()
        low, high = self.config.bfp_tolerance
        
        success_count = ((outcomes >= low) & (outcomes <= high)).sum()
        return success_count / len(outcomes)