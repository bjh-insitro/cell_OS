"""
Interactive Plotly Reporter for cell_OS Campaigns.

Generates rich, interactive reports with drill-down capabilities.
Replaces static HTML with dynamic Plotly visualizations.
"""
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from typing import List, Dict, Any
from pathlib import Path

from cell_os.posh_lv_moi import TitrationReport
from cell_os.budget_manager import BudgetConfig


def create_titration_curve_plotly(report: TitrationReport, target_moi: float = 0.3) -> go.Figure:
    """Create interactive titration curve with model fit."""
    
    # Observed data
    data_points = go.Scatter(
        x=report.data['volume_ul'],
        y=report.data['fraction_bfp'],
        mode='markers',
        name='Observed',
        marker=dict(size=12, color='steelblue', opacity=0.7),
        hovertemplate='Volume: %{x:.2f} µL<br>BFP: %{y:.2%}<extra></extra>'
    )
    
    # Model fit
    if hasattr(report.model, 'titer_tu_ul'):
        vol_grid = np.linspace(report.data['volume_ul'].min(), 
                                report.data['volume_ul'].max(), 100)
        n_cells = 300000  # Assume standard
        moi_grid = (vol_grid * report.model.titer_tu_ul) / n_cells
        bfp_pred = report.model.max_infectivity * (1 - np.exp(-moi_grid))
        
        model_line = go.Scatter(
            x=vol_grid,
            y=bfp_pred,
            mode='lines',
            name='Model Fit',
            line=dict(color='darkred', width=2),
            hovertemplate='Volume: %{x:.2f} µL<br>Predicted BFP: %{y:.2%}<extra></extra>'
        )
        
        # Target MOI line
        target_vol = (target_moi * n_cells) / report.model.titer_tu_ul
        target_bfp = report.model.max_infectivity * (1 - np.exp(-target_moi))
        
        target_line = go.Scatter(
            x=[target_vol],
            y=[target_bfp],
            mode='markers+text',
            name=f'Target MOI ({target_moi})',
            marker=dict(size=15, color='green', symbol='star'),
            text=[f'Target<br>{target_vol:.2f} µL'],
            textposition='top center'
        )
        
        traces = [data_points, model_line, target_line]
    else:
        traces = [data_points]
    
    fig = go.Figure(data=traces)
    
    fig.update_layout(
        title=dict(
            text=f'Titration Curve: {report.cell_line}',
            font=dict(size=20, color='#333')
        ),
        xaxis_title='LV Volume (µL)',
        yaxis_title='Fraction BFP+',
        hovermode='closest',
        template='plotly_white',
        height=500
    )
    
    fig.update_yaxes(tickformat='.0%')
    
    return fig


def create_cost_breakdown_plotly(reports: List[TitrationReport], budget: BudgetConfig) -> go.Figure:
    """Create interactive pie chart of campaign costs."""
    
    total_virus_cost = 0
    total_reagent_cost = 0
    total_flow_cost = 0
    
    for report in reports:
        n_rounds = len(report.data)
        n_wells_per_round = 7  # Standard
        total_virus_cost += report.data['volume_ul'].sum() * budget.virus_price
        total_reagent_cost += n_rounds * n_wells_per_round * budget.reagent_cost_per_well
        total_flow_cost += (n_rounds * n_wells_per_round * budget.mins_per_sample_flow / 60) * budget.flow_rate_per_hour
    
    fig = go.Figure(data=[go.Pie(
        labels=['Virus', 'Reagents', 'Flow Cytometry'],
        values=[total_virus_cost, total_reagent_cost, total_flow_cost],
        marker=dict(colors=['#FF6B6B', '#4ECDC4', '#45B7D1']),
        textinfo='label+percent+value',
        texttemplate='%{label}<br>%{percent}<br>$%{value:.2f}',
        hovertemplate='<b>%{label}</b><br>$%{value:.2f}<br>%{percent}<extra></extra>'
    )])
    
    fig.update_layout(
        title='Campaign Cost Breakdown',
        template='plotly_white',
        height=400
    )
    
    return fig


def create_go_nogo_summary_plotly(reports: List[TitrationReport]) -> go.Figure:
    """Create bar chart of GO/NO-GO decisions."""
    
    cell_lines = [r.cell_line for r in reports]
    statuses = [r.status for r in reports]
    colors = ['green' if s == 'GO' else 'red' for s in statuses]
    pos_values = [r.probability_of_success for r in reports]
    
    fig = go.Figure(data=[
        go.Bar(
            x=cell_lines,
            y=pos_values,
            marker_color=colors,
            text=[f'{v:.1%}' for v in pos_values],
            textposition='auto',
            hovertemplate='<b>%{x}</b><br>PoS: %{y:.1%}<extra></extra>'
        )
    ])
    
    # Add threshold line
    fig.add_hline(y=0.8, line_dash="dash", line_color="gray", 
                   annotation_text="Success Threshold (80%)")
    
    fig.update_layout(
        title='GO/NO-GO Summary',
        xaxis_title='Cell Line',
        yaxis_title='Probability of Success',
        template='plotly_white',
        height=400,
        yaxis=dict(tickformat='.0%', range=[0, 1])
    )
    
    return fig


def generate_interactive_report(
    reports: List[TitrationReport],
    budget: BudgetConfig,
    output_path: str = "campaign_interactive_report.html"
):
    """
    Generate a complete interactive HTML report using Plotly.
    
    Args:
        reports: List of titration reports
        budget: Budget configuration
        output_path: Where to save the HTML file
    """
    
    # Create subplots with different types
    from plotly.subplots import make_subplots
    
    # Summary metrics at top
    total_cost = sum(r.total_cost_usd for r in reports)
    n_go = sum(1 for r in reports if r.status == 'GO')
    
    # Main figure with multiple subplots
    fig = make_subplots(
        rows=2 + len(reports), 
        cols=2,
        row_heights=[0.2, 0.3] + [0.5 / len(reports)] * len(reports),
        column_widths=[0.5, 0.5],
        subplot_titles=[
            'GO/NO-GO Summary', 'Cost Breakdown'
        ] + [f'{r.cell_line} Titration' for r in reports] + [''] * len(reports),
        specs=[
            [{"type": "bar"}, {"type": "pie"}]
        ] + [[{"type": "scatter"}, {"type": "table"}]] * len(reports),
        vertical_spacing=0.05,
        horizontal_spacing=0.1
    )
    
    # Row 1: Summary Charts
    go_nogo_fig = create_go_nogo_summary_plotly(reports)
    for trace in go_nogo_fig.data:
        fig.add_trace(trace, row=1, col=1)
    
    cost_fig = create_cost_breakdown_plotly(reports, budget)
    for trace in cost_fig.data:
        fig.add_trace(trace, row=1, col=2)
    
    # Rows 2+: Individual titration curves
    for idx, report in enumerate(reports, start=2):
        curve_fig = create_titration_curve_plotly(report)
        for trace in curve_fig.data:
            fig.add_trace(trace, row=idx, col=1)
        
        # Add data table
        table_trace = go.Table(
            header=dict(
                values=['Round', 'Volume (µL)', 'BFP%', 'Cost ($)'],
                fill_color='lightblue',
                align='left'
            ),
            cells=dict(
                values=[
                    list(range(1, len(report.data) + 1)),
                    report.data['volume_ul'].round(2),
                    (report.data['fraction_bfp'] * 100).round(1),
                    [f"${c:.2f}" for c in report.data.get('cost_usd', [0] * len(report.data))]
                ],
                align='left'
            )
        )
        fig.add_trace(table_trace, row=idx, col=2)
    
    # Update layout
    fig.update_layout(
        title_text=f"Campaign Report - {len(reports)} Cell Lines - {n_go}/{len(reports)} GO - ${total_cost:.2f}",
        showlegend=False,
        height=400 + 500 * len(reports),
        template='plotly_white'
    )
    
    # Save to HTML
    fig.write_html(output_path, include_plotlyjs='cdn')
    print(f"✅ Interactive report saved to: {output_path}")
    
    return fig


if __name__ == "__main__":
    # Demo/test
    print("Plotly Reporter module loaded successfully!")
