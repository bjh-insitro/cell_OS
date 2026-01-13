"""
POSH Visualization Module.

Provides plotting functions for POSH library design, LV titration, and risk assessment.
"""

import pandas as pd
import numpy as np
import altair as alt
from typing import Optional, Dict

from .library_design import POSHLibrary
from .lv_moi import (
    LVTransductionModel,
    LVDesignBundle,
    ScreenSimulator,
    ScreenConfig
)
from .screen_design import ScreenDesignResult


def plot_library_composition(library: POSHLibrary) -> alt.Chart:
    """
    Plot library composition showing guides per gene distribution.
    
    Returns an Altair chart.
    """
    df = library.df.copy()
    
    # Count guides per gene
    guides_per_gene = df.groupby('gene').size().reset_index(name='num_guides')
    
    chart = alt.Chart(guides_per_gene).mark_bar().encode(
        x=alt.X('num_guides:Q', bin=alt.Bin(maxbins=20), title='Guides per Gene'),
        y=alt.Y('count()', title='Number of Genes'),
        tooltip=[
            alt.Tooltip('num_guides:Q', title='Guides'),
            alt.Tooltip('count()', title='Gene Count')
        ]
    ).properties(
        title='Library Composition: Guides per Gene Distribution',
        width=600,
        height=300
    )
    
    return chart


def plot_titration_curve(
    model: LVTransductionModel,
    titration_data: Optional[pd.DataFrame] = None,
    target_moi: float = 0.3
) -> alt.Chart:
    """
    Plot LV titration curve with uncertainty bands.
    
    Args:
        model: Fitted LVTransductionModel
        titration_data: Optional observed data (columns: volume_ul, fraction_bfp)
        target_moi: Target MOI to highlight
        
    Returns an Altair chart.
    """
    # Generate prediction grid
    vol_grid = np.linspace(0.1, 20, 200)
    bfp_pred = [model.predict_bfp(v) for v in vol_grid]
    
    df_pred = pd.DataFrame({
        'volume_ul': vol_grid,
        'bfp_fraction': bfp_pred
    })
    
    # Prediction line
    line = alt.Chart(df_pred).mark_line(color='steelblue', size=2).encode(
        x=alt.X('volume_ul:Q', scale=alt.Scale(type='log'), title='LV Volume (µL)'),
        y=alt.Y('bfp_fraction:Q', scale=alt.Scale(domain=[0, 1]), title='BFP Fraction'),
        tooltip=[
            alt.Tooltip('volume_ul:Q', format='.2f', title='Volume (µL)'),
            alt.Tooltip('bfp_fraction:Q', format='.2%', title='BFP%')
        ]
    )
    
    # Add uncertainty band if posterior is available
    layers = [line]
    
    if model.posterior:
        # Sample from posterior to get uncertainty
        sampled_titers = np.random.choice(
            model.posterior.grid_titer,
            size=100,
            p=model.posterior.probs
        )
        
        # Calculate predictions for each sampled titer
        predictions = []
        for t in sampled_titers:
            for v in vol_grid:
                moi = (v * t) / model.cells_per_well
                bfp = model.max_infectivity * (1 - np.exp(-moi))
                predictions.append({'volume_ul': v, 'bfp_fraction': bfp})
        
        df_samples = pd.DataFrame(predictions)
        
        # Calculate percentiles
        df_band = df_samples.groupby('volume_ul')['bfp_fraction'].agg([
            ('lower', lambda x: np.percentile(x, 2.5)),
            ('upper', lambda x: np.percentile(x, 97.5))
        ]).reset_index()
        
        band = alt.Chart(df_band).mark_area(opacity=0.3, color='steelblue').encode(
            x=alt.X('volume_ul:Q', scale=alt.Scale(type='log')),
            y='lower:Q',
            y2='upper:Q'
        )
        
        layers.insert(0, band)
    
    # Add observed data points if provided
    if titration_data is not None:
        points = alt.Chart(titration_data).mark_circle(size=60, color='orange').encode(
            x=alt.X('volume_ul:Q', scale=alt.Scale(type='log')),
            y='fraction_bfp:Q',
            tooltip=[
                alt.Tooltip('volume_ul:Q', format='.2f', title='Volume (µL)'),
                alt.Tooltip('fraction_bfp:Q', format='.2%', title='Observed BFP%')
            ]
        )
        layers.append(points)
    
    # Add target MOI line
    target_vol = model.volume_for_moi(target_moi)
    target_bfp = model.predict_bfp(target_vol)
    
    df_target = pd.DataFrame({
        'volume_ul': [target_vol],
        'bfp_fraction': [target_bfp],
        'label': [f'Target MOI {target_moi}']
    })
    
    target_rule = alt.Chart(df_target).mark_rule(color='red', strokeDash=[5, 5]).encode(
        x='volume_ul:Q'
    )
    
    target_point = alt.Chart(df_target).mark_point(size=100, color='red', shape='diamond').encode(
        x='volume_ul:Q',
        y='bfp_fraction:Q',
        tooltip=[
            alt.Tooltip('label:N', title=''),
            alt.Tooltip('volume_ul:Q', format='.2f', title='Volume (µL)'),
            alt.Tooltip('bfp_fraction:Q', format='.2%', title='Expected BFP%')
        ]
    )
    
    layers.extend([target_rule, target_point])
    
    chart = alt.layer(*layers).properties(
        title=f'LV Titration Curve: {model.cell_line}',
        width=700,
        height=400
    )
    
    return chart


def plot_risk_assessment(simulator: ScreenSimulator, n_sims: int = 5000) -> alt.Chart:
    """
    Plot risk assessment showing distribution of expected BFP outcomes.
    
    Args:
        simulator: ScreenSimulator instance
        n_sims: Number of Monte Carlo simulations
        
    Returns an Altair chart.
    """
    outcomes = simulator.run_monte_carlo(n_sims=n_sims)
    
    df = pd.DataFrame({'bfp_fraction': outcomes})
    
    # Histogram
    hist = alt.Chart(df).mark_bar(opacity=0.7).encode(
        x=alt.X('bfp_fraction:Q', bin=alt.Bin(maxbins=50), title='BFP Fraction'),
        y=alt.Y('count()', title='Frequency'),
        tooltip=[
            alt.Tooltip('bfp_fraction:Q', bin=alt.Bin(maxbins=50), format='.2%', title='BFP Range'),
            alt.Tooltip('count()', title='Count')
        ]
    )
    
    # Add tolerance zone
    low, high = simulator.config.bfp_tolerance
    
    df_zone = pd.DataFrame({
        'x': [low, high],
        'label': ['Lower Bound', 'Upper Bound']
    })
    
    zone_low = alt.Chart(df_zone[df_zone['label'] == 'Lower Bound']).mark_rule(
        color='green', strokeDash=[5, 5], size=2
    ).encode(x='x:Q')
    
    zone_high = alt.Chart(df_zone[df_zone['label'] == 'Upper Bound']).mark_rule(
        color='green', strokeDash=[5, 5], size=2
    ).encode(x='x:Q')
    
    # Calculate PoS
    pos = simulator.get_probability_of_success()
    
    chart = alt.layer(hist, zone_low, zone_high).properties(
        title=f'Risk Assessment: Probability of Success = {pos:.1%}',
        width=700,
        height=400
    )
    
    return chart


def plot_cost_breakdown(result: ScreenDesignResult) -> alt.Chart:
    """
    Plot cost breakdown for POSH screen design.
    
    Currently placeholder - would need ResourceAccounting integration.
    """
    # Placeholder data
    costs = [
        {'category': 'Library Synthesis', 'cost_usd': 5000},
        {'category': 'LV Production', 'cost_usd': 3000},
        {'category': 'Cell Culture', 'cost_usd': 2000},
        {'category': 'Reagents', 'cost_usd': 1500},
        {'category': 'Imaging', 'cost_usd': 2500}
    ]
    
    df = pd.DataFrame(costs)
    
    chart = alt.Chart(df).mark_bar().encode(
        x=alt.X('cost_usd:Q', title='Cost (USD)'),
        y=alt.Y('category:N', title='Category', sort='-x'),
        color=alt.Color('category:N', legend=None),
        tooltip=[
            alt.Tooltip('category:N', title='Category'),
            alt.Tooltip('cost_usd:Q', format='$,.0f', title='Cost')
        ]
    ).properties(
        title='POSH Screen Cost Breakdown',
        width=600,
        height=300
    )
    
    return chart


def plot_titer_posterior(model: LVTransductionModel) -> Optional[alt.Chart]:
    """
    Plot the Bayesian posterior distribution over titer.
    
    Returns None if no posterior is available.
    """
    if not model.posterior:
        return None
    
    df = pd.DataFrame({
        'titer_tu_ul': model.posterior.grid_titer,
        'probability': model.posterior.probs
    })
    
    # Add credible interval markers
    ci_low, ci_high = model.posterior.ci_95
    
    chart = alt.Chart(df).mark_area(opacity=0.7, color='steelblue').encode(
        x=alt.X('titer_tu_ul:Q', title='Titer (TU/µL)'),
        y=alt.Y('probability:Q', title='Probability Density'),
        tooltip=[
            alt.Tooltip('titer_tu_ul:Q', format='.0f', title='Titer'),
            alt.Tooltip('probability:Q', format='.4f', title='Probability')
        ]
    )
    
    # Add point estimate
    df_point = pd.DataFrame({
        'titer_tu_ul': [model.titer_tu_ul],
        'label': ['Point Estimate']
    })
    
    point = alt.Chart(df_point).mark_rule(color='red', size=2).encode(
        x='titer_tu_ul:Q',
        tooltip=['label:N', alt.Tooltip('titer_tu_ul:Q', format='.0f', title='Titer')]
    )
    
    # Add CI markers
    df_ci = pd.DataFrame({
        'titer_tu_ul': [ci_low, ci_high],
        'label': ['95% CI Lower', '95% CI Upper']
    })
    
    ci_lines = alt.Chart(df_ci).mark_rule(color='green', strokeDash=[5, 5]).encode(
        x='titer_tu_ul:Q',
        tooltip=['label:N', alt.Tooltip('titer_tu_ul:Q', format='.0f', title='Titer')]
    )
    
    final_chart = alt.layer(chart, point, ci_lines).properties(
        title=f'Titer Posterior: {model.cell_line}',
        width=700,
        height=300
    )
    
    return final_chart
