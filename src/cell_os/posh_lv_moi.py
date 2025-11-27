"""
POSH LV & MOI Modeling Agent.
Defines core data structures for physics, risk, and campaign configuration.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
import pandas as pd
import numpy as np
from scipy.optimize import curve_fit
from scipy.stats import norm
from sklearn.linear_model import RANSACRegressor, LinearRegression
from cell_os.lab_world_model import LabWorldModel
from cell_os.posh_scenario import POSHScenario
from cell_os.posh_library_design import POSHLibrary

class LVDesignError(Exception): pass

# --- Dataclasses ---
@dataclass
class LVBatch:
    name: str; volume_ul_total: float; titer_TU_per_ml: float; library: POSHLibrary
    notes: str = ""; aliquot_count: int = 1; aliquot_volume_ul: float = 0.0

@dataclass
class LVTitrationPlan:
    cell_line: str; plate_format: str; cells_per_well: int; lv_volumes_ul: List[float]; replicates_per_condition: int

@dataclass
class LVTitrationResult:
    cell_line: str; data: pd.DataFrame

@dataclass
class TiterPosterior:
    grid_titer: np.ndarray; probs: np.ndarray; ci_95: Tuple[float, float]

@dataclass
class LVTransductionModel:
    cell_line: str; titer_tu_ul: float; max_infectivity: float; cells_per_well: int
    r_squared: float; posterior: Optional[TiterPosterior] = None; outliers: List[int] = field(default_factory=list)

    def predict_bfp(self, volume_ul: float) -> float:
        if volume_ul < 0: return 0.0
        moi = (volume_ul * self.titer_tu_ul) / self.cells_per_well
        return self.max_infectivity * (1.0 - np.exp(-moi))

    def volume_for_moi(self, target_moi: float) -> float:
        if self.titer_tu_ul <= 0: raise LVDesignError(f"Titer is 0 for {self.cell_line}")
        return (target_moi * self.cells_per_well) / self.titer_tu_ul

@dataclass
class LVDesignBundle:
    batch: LVBatch; titration_plans: Dict[str, LVTitrationPlan]; models: Dict[str, LVTransductionModel] = field(default_factory=dict)

@dataclass
class ScreenConfig:
    """
    Configuration parameters for the screen and titration agent limits.
    """
    num_guides: int = 4000
    coverage_target: int = 1000
    target_bfp: float = 0.30
    bfp_tolerance: Tuple[float, float] = (0.25, 0.35)
    cell_counting_error: float = 0.10
    pipetting_error: float = 0.05
    
    # --- AUTONOMOUS LIMITS (Budget-Aware Stopping) ---
    max_titration_rounds: int = 3
    max_titration_budget_usd: float = 1000.0
    # -----------------------------------------------------

@dataclass
class TitrationReport:
    """Final output report summarizing the titration experiment and decisions."""
    cell_line: str
    status: str
    rounds_run: int
    final_pos: float
    final_vol: float
    history_dfs: List[pd.DataFrame] = field(default_factory=list)
    model: Any = None
    final_cost: float = 0.0

# --- Core Physics ---
def _poisson_curve(vol, titer, n_cells, alpha):
    """The saturation-aware Poisson curve."""
    moi = (vol * titer) / n_cells
    return alpha * (1.0 - np.exp(-(vol * titer) / n_cells))

def _calculate_posterior(df_clean, best_titer, n_cells, alpha):
    """Calculates the titer probability distribution."""
    grid_size = 1000
    t_min = max(100, best_titer * 0.1); t_max = best_titer * 3.0
    titer_grid = np.linspace(t_min, t_max, grid_size)

    y_pred_best = _poisson_curve(df_clean['volume_ul'], best_titer, n_cells, alpha)
    sigma = np.std(df_clean['fraction_bfp'] - y_pred_best) + 1e-6

    log_likelihoods = np.zeros_like(titer_grid)
    for i, t in enumerate(titer_grid):
        y_pred = _poisson_curve(df_clean['volume_ul'], t, n_cells, alpha)
        log_likelihoods[i] = norm.logpdf(df_clean['fraction_bfp'], loc=y_pred, scale=sigma).sum()

    probs = np.exp(log_likelihoods - np.max(log_likelihoods))
    probs /= probs.sum()
    cumsum = np.cumsum(probs)
    return TiterPosterior(titer_grid, probs, (titer_grid[np.searchsorted(cumsum, 0.025)], titer_grid[np.searchsorted(cumsum, 0.975)]))

# --- Workflow ---
def design_lv_batch(world, scenario, library, aliquot_count=10, aliquot_volume_ul=50.0):
    return LVBatch(f"LV_{scenario.name}", aliquot_count*aliquot_volume_ul, 0.0, library, "Designed by POSH", aliquot_count, aliquot_volume_ul)

def design_lv_titration_plan(world, scenario, batch, cell_line, plate_format="6", cells_per_well=100000, lv_volumes_ul=None):
    vols = lv_volumes_ul or [0.1, 0.3, 0.5, 1.0, 3.0, 5.0, 10.0]
    return LVTitrationPlan(cell_line, plate_format, cells_per_well, vols, 1)

def fit_lv_transduction_model(scenario, batch, titration_result, n_cells_override=100000):
    """Fits the non-linear Poisson model with RANSAC outlier detection."""
    df = titration_result.data.copy()
    df = df[(df['fraction_bfp'] > 0.001) & (df['fraction_bfp'] < 0.999)].copy()
    if len(df) < 2: raise LVDesignError(f"Insufficient data for {titration_result.cell_line}")

    # 1. RANSAC Outlier Detection (on linearized data)
    df['linear_y'] = -np.log(1.0 - df['fraction_bfp'])
    try:
        ransac = RANSACRegressor(min_samples=max(2, int(len(df)*0.5)), residual_threshold=0.5, random_state=42)
        ransac.fit(df[['volume_ul']], df['linear_y'])
        df_clean = df[ransac.inlier_mask_].copy()
    except: df_clean = df
    if len(df_clean) < 2: df_clean = df

    # 2. Curve Fit (Non-Linear Least Squares)
    lr = LinearRegression().fit(df_clean[['volume_ul']], df_clean['linear_y'])
    p0 = [max(1000, lr.coef_[0] * n_cells_override), 0.98]
    try:
        popt, _ = curve_fit(lambda v, t, a: _poisson_curve(v, t, n_cells_override, a), df_clean['volume_ul'], df_clean['fraction_bfp'], p0=p0, bounds=([0, 0.5], [np.inf, 1.0]), maxfev=5000)
    except: raise LVDesignError(f"Fit failed for {titration_result.cell_line}")

    # 3. Calculate R^2 and Posterior
    y_pred = _poisson_curve(df_clean['volume_ul'], popt[0], n_cells_override, popt[1])
    ss_res = np.sum((df_clean['fraction_bfp'] - y_pred)**2)
    ss_tot = np.sum((df_clean['fraction_bfp'] - df_clean['fraction_bfp'].mean())**2)

    # --- FINAL FIX APPLIED HERE: popart -> popt ---
    return LVTransductionModel(
        cell_line=titration_result.cell_line, 
        titer_tu_ul=popt[0], # Corrected variable name
        max_infectivity=popt[1], 
        cells_per_well=n_cells_override, 
        r_squared=1-(ss_res/ss_tot) if ss_tot>0 else 0, 
        posterior=_calculate_posterior(df_clean, popt[0], popt[1], n_cells_override), 
        outliers=[]
    )

def design_lv_for_scenario(world, scenario, library):
    batch = design_lv_batch(world, scenario, library)
    plans = {cl: design_lv_titration_plan(world, scenario, batch, cl) for cl in scenario.cell_lines}
    return LVDesignBundle(batch, plans, {})

# --- Autonomous Explorer (Smart Diversity Logic) ---
class LVAutoExplorer:
    def __init__(self, scenario: POSHScenario, batch: LVBatch):
        self.scenario = scenario; self.batch = batch

    def suggest_next_volumes(self, current_results: LVTitrationResult, n_suggestions: int = 2) -> List[float]:
        """Suggests next points based on where model variance is highest near target BFP."""
        try: model = fit_lv_transduction_model(self.scenario, self.batch, current_results)
        except LVDesignError: return [1.0, 5.0]

        max_bfp = current_results.data['fraction_bfp'].max()
        if max_bfp < 0.05: return [float(current_results.data['volume_ul'].max() * x) for x in [2.0, 4.0]][:n_suggestions]
        if current_results.data['fraction_bfp'].min() > 0.80: return [float(current_results.data['volume_ul'].min() * x) for x in [0.5, 0.1]][:n_suggestions]

        candidates = np.geomspace(0.1, 20.0, 100)
        sampled_titers = np.random.choice(model.posterior.grid_titer, size=50, p=model.posterior.probs)

        predictions = np.array([model.max_infectivity * (1 - np.exp(-(candidates * t) / model.cells_per_well)) for t in sampled_titers])
        variances = np.var(predictions, axis=0)
        relevance = np.exp(-0.5 * ((np.mean(predictions, axis=0) - 0.30) / 0.15)**2)
        utility = variances * relevance

        suggestions = []
        existing_vols = current_results.data['volume_ul'].values

        for ex in existing_vols: utility *= (1.0 - np.exp(-0.5 * ((np.log(candidates) - np.log(ex)) / 0.2)**2))

        for _ in range(n_suggestions):
            if np.max(utility) < 1e-9: break
            best_vol = candidates[np.argmax(utility)]
            suggestions.append(round(float(best_vol), 2))
            utility *= (1.0 - np.exp(-0.5 * ((np.log(candidates) - np.log(best_vol)) / 0.3)**2))

        return suggestions

# --- Risk Simulator ---
class ScreenSimulator:
    def __init__(self, model, config):
        self.model = model; self.config = config
        self.total_cells = int((config.num_guides * config.coverage_target) / config.target_bfp)
        self.target_vol_ul = (-np.log(1.0 - config.target_bfp) * self.total_cells) / self.model.titer_tu_ul if self.model.titer_tu_ul > 0 else 0.0

    def get_probability_of_success(self, n_sims=5000):
        titers = np.random.choice(self.model.posterior.grid_titer, size=n_sims, p=self.model.posterior.probs)
        cells = np.random.normal(self.total_cells, self.config.cell_counting_error * self.total_cells, n_sims)
        vols = np.random.normal(self.target_vol_ul, self.config.pipetting_error * self.target_vol_ul, n_sims)
        bfp = self.model.max_infectivity * (1.0 - np.exp(-(vols * titers) / cells))
        return ((bfp >= self.config.bfp_tolerance[0]) & (bfp <= self.config.bfp_tolerance[1])).sum() / n_sims