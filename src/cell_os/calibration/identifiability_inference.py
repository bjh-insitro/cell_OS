"""
Inference for identifiability suite.

Three components:
1. Mixed model (Plate A): Estimate well-level persistent RE variance → ICC
2. Survival fit (Plate C): Recover commitment parameters (λ0, threshold, p)
3. Held-out prediction (Plate B): Validate joint model
"""

import numpy as np
import pandas as pd
from typing import Dict, Tuple, Optional
from scipy import stats
from scipy.optimize import minimize


def fit_re_icc(
    observations_df: pd.DataFrame,
    metric: str = "cell_count",
    regime: str = "low_stress_re_only"
) -> Dict:
    """
    Estimate well-level persistent variance from low-stress data (Plate A).

    Uses simple variance decomposition:
    - ICC = var_between_wells / (var_between_wells + var_within_wells)

    Args:
        observations_df: Observations dataframe
        metric: Metric to analyze (default: "cell_count")
        regime: Regime to analyze (default: "low_stress_re_only")

    Returns:
        Dict with keys:
            - icc: Intraclass correlation coefficient
            - var_well: Between-well variance
            - var_resid: Within-well (residual) variance
            - n_wells: Number of wells
            - n_obs: Total observations
    """
    # Filter to regime and metric
    df = observations_df[
        (observations_df['regime'] == regime) &
        (observations_df['metric_name'] == metric)
    ].copy()

    if len(df) == 0:
        return {'icc': 0.0, 'var_well': 0.0, 'var_resid': 0.0, 'n_wells': 0, 'n_obs': 0}

    # Compute well means (average over time)
    well_means = df.groupby('well_id')['value'].mean()

    # Compute grand mean
    grand_mean = df['value'].mean()

    # Between-well variance
    n_wells = len(well_means)
    var_between = np.var(well_means, ddof=1) if n_wells > 1 else 0.0

    # Within-well variance (pooled residual variance)
    residuals = []
    for well_id in well_means.index:
        well_df = df[df['well_id'] == well_id]
        well_mean = well_means[well_id]
        well_residuals = well_df['value'] - well_mean
        residuals.extend(well_residuals)

    var_within = np.var(residuals, ddof=1) if len(residuals) > 1 else 0.0

    # ICC = var_between / (var_between + var_within)
    total_var = var_between + var_within
    icc = var_between / total_var if total_var > 0 else 0.0

    return {
        'icc': float(icc),
        'var_well': float(var_between),
        'var_resid': float(var_within),
        'n_wells': int(n_wells),
        'n_obs': len(df),
    }


def fit_commitment_params(
    events_df: pd.DataFrame,
    observations_df: pd.DataFrame,
    regime: str = "high_stress_event_rich",
    mechanism: str = "er_stress",
    stress_metric: str = "er_stress"
) -> Dict:
    """
    Recover commitment parameters (λ0, threshold, p) from high-stress data (Plate C).

    Uses maximum likelihood estimation with discrete-time hazard model:
        λ(t) = min(cap, λ0 * ((max(0, S(t) - S_commit) / (1 - S_commit))^p))

    Args:
        events_df: Events dataframe
        observations_df: Observations dataframe (for stress trajectories)
        regime: Regime to analyze (default: "high_stress_event_rich")
        mechanism: Commitment mechanism (default: "er_stress")
        stress_metric: Stress metric name (default: "er_stress")

    Returns:
        Dict with keys:
            - threshold: Recovered commitment threshold
            - baseline_hazard_per_h: Recovered λ0
            - sharpness_p: Recovered p
            - log_likelihood: Log-likelihood of best fit
            - n_wells: Number of wells
            - n_events: Number of commitment events
            - predicted_commit_prob: Mean predicted commitment probability
            - observed_commit_frac: Observed commitment fraction
    """
    # Filter events to regime and mechanism
    events = events_df[events_df['regime'] == regime].copy()

    # Filter observations to regime and stress metric
    obs = observations_df[
        (observations_df['regime'] == regime) &
        (observations_df['metric_name'] == stress_metric)
    ].copy()

    if len(events) == 0 or len(obs) == 0:
        return {
            'threshold': None,
            'baseline_hazard_per_h': None,
            'sharpness_p': None,
            'log_likelihood': -np.inf,
            'n_wells': 0,
            'n_events': 0,
        }

    # Get well list
    well_ids = events['well_id'].unique()
    n_wells = len(well_ids)
    n_events = events['committed'].sum()

    # Build stress trajectories for each well
    stress_trajectories = {}
    for well_id in well_ids:
        well_obs = obs[obs['well_id'] == well_id].sort_values('time_h')
        stress_trajectories[well_id] = {
            'time_h': well_obs['time_h'].values,
            'stress': well_obs['value'].values,
        }

    # Grid search for parameters
    # Threshold: 0.3 to 0.9 (commitment unlikely below 0.3)
    # p: 1.0 to 4.0 (linear to sharp)
    # λ0: 0.001 to 1.0 (log scale)

    threshold_grid = np.linspace(0.3, 0.9, 10)
    p_grid = np.linspace(1.0, 4.0, 7)
    lambda0_grid = np.logspace(-3, 0, 8)  # 0.001 to 1.0

    best_ll = -np.inf
    best_params = None

    for threshold in threshold_grid:
        for p in p_grid:
            for lambda0 in lambda0_grid:
                ll = _compute_log_likelihood(
                    events=events,
                    stress_trajectories=stress_trajectories,
                    threshold=threshold,
                    lambda0=lambda0,
                    p=p,
                    cap=10.0  # High cap (assume no effective cap in data)
                )

                if ll > best_ll:
                    best_ll = ll
                    best_params = (threshold, lambda0, p)

    if best_params is None:
        return {
            'threshold': None,
            'baseline_hazard_per_h': None,
            'sharpness_p': None,
            'log_likelihood': -np.inf,
            'n_wells': n_wells,
            'n_events': int(n_events),
        }

    threshold_best, lambda0_best, p_best = best_params

    # Compute cumulative hazard diagnostic: predicted vs observed commitment
    # For each well, compute H = ∫λ(t)dt, then p_commit = 1 - exp(-H)
    predicted_probs = []
    for well_id in well_ids:
        if well_id not in stress_trajectories:
            continue

        traj = stress_trajectories[well_id]
        times = traj['time_h']
        stresses = traj['stress']

        if len(times) == 0:
            continue

        # Compute cumulative hazard
        cumulative_hazard = 0.0
        for i in range(len(times) - 1):
            s = stresses[i]
            dt = times[i + 1] - times[i]

            # Hazard at this stress level
            if s <= threshold_best:
                hazard = 0.0
            else:
                u = (s - threshold_best) / (1.0 - threshold_best)
                hazard = min(10.0, lambda0_best * (u ** p_best))  # Use cap=10.0

            cumulative_hazard += hazard * dt

        # P(commit) = 1 - exp(-H)
        p_commit = 1.0 - np.exp(-cumulative_hazard)
        predicted_probs.append(p_commit)

    predicted_commit_prob = np.mean(predicted_probs) if len(predicted_probs) > 0 else 0.0
    observed_commit_frac = n_events / n_wells if n_wells > 0 else 0.0

    return {
        'threshold': float(threshold_best),
        'baseline_hazard_per_h': float(lambda0_best),
        'sharpness_p': float(p_best),
        'log_likelihood': float(best_ll),
        'n_wells': int(n_wells),
        'n_events': int(n_events),
        'predicted_commit_prob': float(predicted_commit_prob),
        'observed_commit_frac': float(observed_commit_frac),
    }


def _compute_log_likelihood(
    events: pd.DataFrame,
    stress_trajectories: Dict,
    threshold: float,
    lambda0: float,
    p: float,
    cap: float
) -> float:
    """
    Compute log-likelihood for commitment hazard model.

    For each well:
    - If committed: log(P(commit at observed time))
    - If not committed: log(P(survive to end))

    Args:
        events: Events dataframe
        stress_trajectories: Dict[well_id -> {'time_h', 'stress'}]
        threshold: Commitment threshold
        lambda0: Baseline hazard
        p: Sharpness parameter
        cap: Hazard cap

    Returns:
        Log-likelihood
    """
    log_likelihood = 0.0

    for _, row in events.iterrows():
        well_id = row['well_id']
        committed = row['committed']
        commitment_time_h = row['commitment_time_h']

        if well_id not in stress_trajectories:
            continue

        traj = stress_trajectories[well_id]
        times = traj['time_h']
        stresses = traj['stress']

        if len(times) == 0:
            continue

        # Compute survival probability up to each timepoint
        survival_prob = 1.0

        for i in range(len(times) - 1):
            t = times[i]
            s = stresses[i]
            dt = times[i + 1] - times[i]

            # Hazard at this stress level
            if s <= threshold:
                hazard = 0.0
            else:
                u = (s - threshold) / (1.0 - threshold)
                hazard = min(cap, lambda0 * (u ** p))

            # P(survive this interval) = exp(-hazard * dt)
            p_survive_interval = np.exp(-hazard * dt)
            survival_prob *= p_survive_interval

            # If committed at this interval
            if committed and commitment_time_h is not None:
                if t <= commitment_time_h < times[i + 1]:
                    # Event occurred in this interval
                    # P(event) = hazard * exp(-hazard * (t_event - t))
                    # For discrete time, approximate as: hazard * dt * p_survive_interval
                    p_event = 1.0 - p_survive_interval  # Discrete-time approximation
                    log_likelihood += np.log(max(p_event, 1e-10))
                    break

        else:
            # No event occurred (or event after last timepoint)
            if not committed:
                # Survived to end
                log_likelihood += np.log(max(survival_prob, 1e-10))

    return log_likelihood


def predict_commitment_fraction(
    observations_df: pd.DataFrame,
    recovered_params: Dict,
    regime: str = "mid_stress_mixed",
    stress_metric: str = "er_stress"
) -> Dict:
    """
    Predict commitment fraction in held-out regime (Plate B) using recovered params.

    Args:
        observations_df: Observations dataframe
        recovered_params: Dict with 'threshold', 'baseline_hazard_per_h', 'sharpness_p'
        regime: Regime to predict (default: "mid_stress_mixed")
        stress_metric: Stress metric name (default: "er_stress")

    Returns:
        Dict with keys:
            - predicted_fraction: Predicted commitment fraction
            - n_wells: Number of wells
    """
    # Filter observations
    obs = observations_df[
        (observations_df['regime'] == regime) &
        (observations_df['metric_name'] == stress_metric)
    ].copy()

    if len(obs) == 0:
        return {'predicted_fraction': 0.0, 'n_wells': 0}

    well_ids = obs['well_id'].unique()
    n_wells = len(well_ids)

    # Extract params
    threshold = recovered_params['threshold']
    lambda0 = recovered_params['baseline_hazard_per_h']
    p = recovered_params['sharpness_p']
    cap = 10.0  # Assume high cap

    # For each well, compute survival probability to end
    predicted_events = 0

    for well_id in well_ids:
        well_obs = obs[obs['well_id'] == well_id].sort_values('time_h')
        times = well_obs['time_h'].values
        stresses = well_obs['value'].values

        if len(times) == 0:
            continue

        # Compute survival to end
        survival_prob = 1.0
        for i in range(len(times) - 1):
            s = stresses[i]
            dt = times[i + 1] - times[i]

            if s <= threshold:
                hazard = 0.0
            else:
                u = (s - threshold) / (1.0 - threshold)
                hazard = min(cap, lambda0 * (u ** p))

            p_survive_interval = np.exp(-hazard * dt)
            survival_prob *= p_survive_interval

        # P(commit) = 1 - P(survive)
        p_commit = 1.0 - survival_prob
        predicted_events += p_commit

    predicted_fraction = predicted_events / n_wells if n_wells > 0 else 0.0

    return {
        'predicted_fraction': float(predicted_fraction),
        'n_wells': int(n_wells),
    }


def compare_prediction_to_empirical(
    events_df: pd.DataFrame,
    predicted_fraction: float,
    regime: str = "mid_stress_mixed"
) -> Dict:
    """
    Compare predicted commitment fraction to empirical.

    Args:
        events_df: Events dataframe
        predicted_fraction: Predicted commitment fraction from model
        regime: Regime to compare (default: "mid_stress_mixed")

    Returns:
        Dict with keys:
            - empirical_fraction: Observed commitment fraction
            - predicted_fraction: Model prediction
            - fraction_error: Absolute error
            - ks_stat: KS statistic on event times (if events exist)
            - n_wells: Number of wells
            - n_events: Number of observed events
    """
    events = events_df[events_df['regime'] == regime].copy()

    if len(events) == 0:
        return {
            'empirical_fraction': 0.0,
            'predicted_fraction': predicted_fraction,
            'fraction_error': abs(predicted_fraction - 0.0),
            'ks_stat': None,
            'n_wells': 0,
            'n_events': 0,
        }

    n_wells = len(events)
    n_events = events['committed'].sum()
    empirical_fraction = n_events / n_wells

    fraction_error = abs(empirical_fraction - predicted_fraction)

    # KS statistic on event times (if any events)
    ks_stat = None
    if n_events > 0:
        # For now, skip KS test (would need predicted distribution, not just fraction)
        # Could implement if needed for full validation
        ks_stat = None

    return {
        'empirical_fraction': float(empirical_fraction),
        'predicted_fraction': float(predicted_fraction),
        'fraction_error': float(fraction_error),
        'ks_stat': ks_stat,
        'n_wells': int(n_wells),
        'n_events': int(n_events),
    }


# ============================================================================
# Phase 2C.2: Multi-Mechanism Competing-Risks Inference
# ============================================================================


def fit_multi_mechanism_params(
    events_df: pd.DataFrame,
    observations_df: pd.DataFrame,
    er_dominant_regime: str = "er_dominant",
    mito_dominant_regime: str = "mito_dominant"
) -> Dict:
    """
    Fit ER and mito commitment parameters from mechanism-specific regimes.

    NO ACCESS TO mechanism labels - fits using stress trajectories only.

    Args:
        events_df: Events dataframe
        observations_df: Observations dataframe
        er_dominant_regime: Regime where ER dominates (mito negligible)
        mito_dominant_regime: Regime where mito dominates (ER negligible)

    Returns:
        Dict with keys:
            - params_er: ER parameters (threshold, baseline_hazard_per_h, sharpness_p)
            - params_mito: Mito parameters (threshold, baseline_hazard_per_h, sharpness_p)
            - fit_quality_er: Fit diagnostics for ER
            - fit_quality_mito: Fit diagnostics for mito
    """
    # Fit ER params from ER-dominant regime (treating mito as zero)
    params_er = fit_commitment_params(
        events_df=events_df,
        observations_df=observations_df,
        regime=er_dominant_regime,
        mechanism="er_stress",  # Not a label - just tells us which stress covariate to use
        stress_metric="er_stress"
    )

    # Fit mito params from mito-dominant regime (treating ER as zero)
    params_mito = fit_commitment_params(
        events_df=events_df,
        observations_df=observations_df,
        regime=mito_dominant_regime,
        mechanism="mito",  # Not a label - just tells us which stress covariate to use
        stress_metric="mito_dysfunction"
    )

    return {
        'params_er': params_er,
        'params_mito': params_mito,
        'fit_quality_er': {
            'log_likelihood': params_er['log_likelihood'],
            'n_events': params_er['n_events'],
            'n_wells': params_er['n_wells'],
        },
        'fit_quality_mito': {
            'log_likelihood': params_mito['log_likelihood'],
            'n_events': params_mito['n_events'],
            'n_wells': params_mito['n_wells'],
        },
    }


def compute_hazard_trajectory(
    stress_trajectory: np.ndarray,
    threshold: float,
    lambda0: float,
    p: float,
    cap: float = 10.0
) -> np.ndarray:
    """
    Compute hazard trajectory from stress trajectory.

    λ(t) = min(cap, λ0 * ((max(0, S(t) - threshold) / (1 - threshold))^p))

    Args:
        stress_trajectory: Stress values over time
        threshold: Commitment threshold
        lambda0: Baseline hazard
        p: Sharpness parameter
        cap: Hazard cap

    Returns:
        Hazard values over time
    """
    hazards = np.zeros_like(stress_trajectory)

    for i, s in enumerate(stress_trajectory):
        if s <= threshold:
            hazards[i] = 0.0
        else:
            u = (s - threshold) / (1.0 - threshold)
            hazards[i] = min(cap, lambda0 * (u ** p))

    return hazards


def attribute_events_competing_risks(
    events_df: pd.DataFrame,
    observations_df: pd.DataFrame,
    params_er: Dict,
    params_mito: Dict,
    regime: str = "mixed"
) -> Dict:
    """
    Attribute events in mixed regime to ER vs mito using competing-risks model.

    NO ACCESS TO mechanism labels - uses stress trajectories and fitted params only.

    For each event at time T:
        P(ER | event at T) = λ_ER(T) / (λ_ER(T) + λ_mito(T))
        P(mito | event at T) = λ_mito(T) / (λ_ER(T) + λ_mito(T))

    Predicted mechanism = argmax posterior

    Args:
        events_df: Events dataframe
        observations_df: Observations dataframe
        params_er: ER parameters
        params_mito: Mito parameters
        regime: Regime to attribute (default: "mixed")

    Returns:
        Dict with keys:
            - attributions: List of dicts per event:
                {well_id, event_time_h, posterior_er, posterior_mito, predicted_mech}
            - predicted_fraction_total: Predicted total commitment fraction
            - predicted_fraction_er: Predicted ER-attributed fraction
            - predicted_fraction_mito: Predicted mito-attributed fraction
            - n_wells: Total wells
            - n_events_observed: Observed events
            - stress_correlation: Correlation between ER and mito stress at event times
    """
    events = events_df[events_df['regime'] == regime].copy()

    # Get both stress trajectories
    obs_er = observations_df[
        (observations_df['regime'] == regime) &
        (observations_df['metric_name'] == 'er_stress')
    ].copy()

    obs_mito = observations_df[
        (observations_df['regime'] == regime) &
        (observations_df['metric_name'] == 'mito_dysfunction')
    ].copy()

    if len(events) == 0 or len(obs_er) == 0 or len(obs_mito) == 0:
        return {
            'attributions': [],
            'predicted_fraction_total': 0.0,
            'predicted_fraction_er': 0.0,
            'predicted_fraction_mito': 0.0,
            'n_wells': 0,
            'n_events_observed': 0,
            'stress_correlation': None,
        }

    well_ids = events['well_id'].unique()
    n_wells = len(well_ids)

    # Build trajectories for each well
    trajectories = {}
    for well_id in well_ids:
        er_traj = obs_er[obs_er['well_id'] == well_id].sort_values('time_h')
        mito_traj = obs_mito[obs_mito['well_id'] == well_id].sort_values('time_h')

        if len(er_traj) == 0 or len(mito_traj) == 0:
            continue

        trajectories[well_id] = {
            'time_h': er_traj['time_h'].values,  # Assume same timepoints
            'er_stress': er_traj['value'].values,
            'mito_stress': mito_traj['value'].values,
        }

    # Extract params
    threshold_er = params_er.get('threshold', 0.60)
    lambda0_er = params_er.get('baseline_hazard_per_h', 0.20)
    p_er = params_er.get('sharpness_p', 2.0)

    threshold_mito = params_mito.get('threshold', 0.60)
    lambda0_mito = params_mito.get('baseline_hazard_per_h', 0.15)
    p_mito = params_mito.get('sharpness_p', 2.5)

    cap = 10.0

    # Compute attributions for each event
    attributions = []
    stress_correlations = []

    for _, event_row in events.iterrows():
        well_id = event_row['well_id']
        committed = event_row['committed']
        event_time_h = event_row['commitment_time_h']

        if not committed or event_time_h is None:
            continue

        if well_id not in trajectories:
            continue

        traj = trajectories[well_id]
        times = traj['time_h']
        er_stresses = traj['er_stress']
        mito_stresses = traj['mito_stress']

        # Find timepoint closest to event
        idx = np.argmin(np.abs(times - event_time_h))
        s_er_at_event = er_stresses[idx]
        s_mito_at_event = mito_stresses[idx]

        # Compute hazards at event time
        if s_er_at_event <= threshold_er:
            lambda_er_at_event = 0.0
        else:
            u_er = (s_er_at_event - threshold_er) / (1.0 - threshold_er)
            lambda_er_at_event = min(cap, lambda0_er * (u_er ** p_er))

        if s_mito_at_event <= threshold_mito:
            lambda_mito_at_event = 0.0
        else:
            u_mito = (s_mito_at_event - threshold_mito) / (1.0 - threshold_mito)
            lambda_mito_at_event = min(cap, lambda0_mito * (u_mito ** p_mito))

        lambda_total = lambda_er_at_event + lambda_mito_at_event

        # Posterior probabilities
        if lambda_total > 0:
            posterior_er = lambda_er_at_event / lambda_total
            posterior_mito = lambda_mito_at_event / lambda_total
        else:
            # Both hazards zero (shouldn't happen for committed event, but handle gracefully)
            posterior_er = 0.5
            posterior_mito = 0.5

        predicted_mech = "er_stress" if posterior_er > posterior_mito else "mito"

        attributions.append({
            'well_id': well_id,
            'event_time_h': float(event_time_h),
            'posterior_er': float(posterior_er),
            'posterior_mito': float(posterior_mito),
            'predicted_mech': predicted_mech,
            's_er_at_event': float(s_er_at_event),
            's_mito_at_event': float(s_mito_at_event),
        })

        # Track stress correlation at event times
        stress_correlations.append((s_er_at_event, s_mito_at_event))

    # Compute stress correlation at event times
    if len(stress_correlations) > 1:
        s_er_events = [x[0] for x in stress_correlations]
        s_mito_events = [x[1] for x in stress_correlations]
        stress_corr = np.corrcoef(s_er_events, s_mito_events)[0, 1]
    else:
        stress_corr = None

    # Predict commitment fractions using competing-risks model
    predicted_events_er = 0.0
    predicted_events_mito = 0.0

    for well_id in well_ids:
        if well_id not in trajectories:
            continue

        traj = trajectories[well_id]
        times = traj['time_h']
        er_stresses = traj['er_stress']
        mito_stresses = traj['mito_stress']

        # Compute hazard trajectories
        hazard_er_traj = compute_hazard_trajectory(er_stresses, threshold_er, lambda0_er, p_er, cap)
        hazard_mito_traj = compute_hazard_trajectory(mito_stresses, threshold_mito, lambda0_mito, p_mito, cap)
        hazard_total_traj = hazard_er_traj + hazard_mito_traj

        # Compute survival and attribution
        survival_prob = 1.0
        p_commit_er = 0.0
        p_commit_mito = 0.0

        for i in range(len(times) - 1):
            dt = times[i + 1] - times[i]
            lambda_total_t = hazard_total_traj[i]
            lambda_er_t = hazard_er_traj[i]
            lambda_mito_t = hazard_mito_traj[i]

            # Survival in this interval
            p_survive_interval = np.exp(-lambda_total_t * dt)
            p_commit_interval = 1.0 - p_survive_interval

            # Attribution within this interval
            if lambda_total_t > 0:
                frac_er = lambda_er_t / lambda_total_t
                frac_mito = lambda_mito_t / lambda_total_t
            else:
                frac_er = 0.5
                frac_mito = 0.5

            # Increment mechanism-specific commitments
            p_commit_er += survival_prob * p_commit_interval * frac_er
            p_commit_mito += survival_prob * p_commit_interval * frac_mito

            survival_prob *= p_survive_interval

        predicted_events_er += p_commit_er
        predicted_events_mito += p_commit_mito

    predicted_fraction_er = predicted_events_er / n_wells if n_wells > 0 else 0.0
    predicted_fraction_mito = predicted_events_mito / n_wells if n_wells > 0 else 0.0
    predicted_fraction_total = predicted_fraction_er + predicted_fraction_mito

    n_events_observed = len(attributions)

    return {
        'attributions': attributions,
        'predicted_fraction_total': float(predicted_fraction_total),
        'predicted_fraction_er': float(predicted_fraction_er),
        'predicted_fraction_mito': float(predicted_fraction_mito),
        'n_wells': int(n_wells),
        'n_events_observed': int(n_events_observed),
        'stress_correlation': float(stress_corr) if stress_corr is not None else None,
    }


def validate_attribution_accuracy(
    attributions: list,
    events_df: pd.DataFrame,
    regime: str = "mixed"
) -> Dict:
    """
    Post-hoc validation: Compare predicted mechanisms to ground truth labels.

    THIS IS THE ONLY PLACE where mechanism labels are used.
    This function is called AFTER inference is complete.

    Args:
        attributions: List of attribution dicts from attribute_events_competing_risks
        events_df: Events dataframe (with ground truth mechanism labels)
        regime: Regime name

    Returns:
        Dict with keys:
            - accuracy: Fraction of correctly attributed events
            - confusion_matrix: Dict with counts {er_er, er_mito, mito_er, mito_mito}
            - n_events: Number of events validated
            - per_mechanism_accuracy: Accuracy for ER-events and mito-events separately
    """
    if len(attributions) == 0:
        return {
            'accuracy': 0.0,
            'confusion_matrix': {'er_er': 0, 'er_mito': 0, 'mito_er': 0, 'mito_mito': 0},
            'n_events': 0,
            'per_mechanism_accuracy': {'er': 0.0, 'mito': 0.0},
        }

    events = events_df[events_df['regime'] == regime].copy()

    # Build ground truth map: well_id -> true_mechanism
    true_mechanisms = {}
    for _, row in events.iterrows():
        if row['committed'] and row['commitment_time_h'] is not None:
            # Column name is 'mechanism' in events.csv
            mechanism_col = 'death_commitment_mechanism' if 'death_commitment_mechanism' in row else 'mechanism'
            true_mechanisms[row['well_id']] = row[mechanism_col]

    # Compare predictions to ground truth
    correct = 0
    total = 0

    confusion = {
        'er_er': 0,      # True ER, predicted ER
        'er_mito': 0,    # True ER, predicted mito
        'mito_er': 0,    # True mito, predicted ER
        'mito_mito': 0,  # True mito, predicted mito
    }

    for attr in attributions:
        well_id = attr['well_id']
        predicted_mech = attr['predicted_mech']

        if well_id not in true_mechanisms:
            continue

        true_mech = true_mechanisms[well_id]
        total += 1

        # Normalize mechanism names (handle "er_stress" vs "er" inconsistency)
        true_mech_norm = "er" if true_mech == "er_stress" else "mito"
        predicted_mech_norm = "er" if predicted_mech == "er_stress" else "mito"

        if true_mech_norm == predicted_mech_norm:
            correct += 1

        # Update confusion matrix
        key = f"{true_mech_norm}_{predicted_mech_norm}"
        if key in confusion:
            confusion[key] += 1

    accuracy = correct / total if total > 0 else 0.0

    # Per-mechanism accuracy
    er_correct = confusion['er_er']
    er_total = confusion['er_er'] + confusion['er_mito']
    er_accuracy = er_correct / er_total if er_total > 0 else 0.0

    mito_correct = confusion['mito_mito']
    mito_total = confusion['mito_er'] + confusion['mito_mito']
    mito_accuracy = mito_correct / mito_total if mito_total > 0 else 0.0

    return {
        'accuracy': float(accuracy),
        'confusion_matrix': confusion,
        'n_events': int(total),
        'per_mechanism_accuracy': {
            'er': float(er_accuracy),
            'mito': float(mito_accuracy),
        },
    }
