import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import webbrowser
import os
from typing import List

# Import necessary classes for type hinting and internal logic (assuming these are in the environment)
from cell_os.titration_loop import TitrationReport
from cell_os.posh_lv_moi import ScreenConfig, ScreenSimulator, LVTransductionModel, TiterPosterior

# --- HELPER FUNCTION (Logic for Manifest) ---
# This replicates the logic from generate_manifest.py to populate the decision table
def _decide_strategy(r, config):
    if r.status == "GO": return "Standard", r.final_vol, "Ready"
    
    # Attempt Dilution Rescue (Simulates 1:10 dilution + 2% error)
    diluted_posterior = TiterPosterior(r.model.posterior.grid_titer/10, r.model.posterior.probs, (r.model.posterior.ci_95[0]/10, r.model.posterior.ci_95[1]/10))
    diluted_model = LVTransductionModel(f"{r.cell_line}", r.model.titer_tu_ul/10, r.model.max_infectivity, r.model.cells_per_well, 0, diluted_posterior)
    sim = ScreenSimulator(diluted_model, ScreenConfig(pipetting_error=0.02))
    new_pos = sim.get_probability_of_success()
    
    if new_pos > 0.90: 
        return "Dilute 1:10", sim.target_vol_ul, f"Rescued (PoS {new_pos:.1%})"
    return "REJECT", 0.0, f"Unstable (PoS {new_pos:.1%})"


def generate_html_report(reports: list[TitrationReport], config: ScreenConfig, log_text: str, costs: list = None, filename="campaign_report.html"):
    """Generates the interactive Plotly/HTML report."""
    
    print(f"📊 GENERATING INTERACTIVE HTML REPORT -> {filename}...")
    
    # --- 1. MANIFEST TABLE (Decision Summary) ---
    manifest_rows = []
    for r in reports:
        strategy, vol, note = _decide_strategy(r, config)
        vol_str = f"{vol:.1f} µL" if vol > 0 else "---"
        status_color = "green" if r.status == "GO" else "red"
        if "Rescued" in note: status_color = "orange"
        
        manifest_rows.append({
            "Cell Line": f"<b>{r.cell_line}</b>",
            "Status": f"<b style='color:{status_color}'>{r.status}</b>",
            "Strategy": strategy,
            "Vol/Flask": vol_str,
            "Target mTagBFP2+": f"{config.target_bfp:.0%}",
            "Confidence": f"{r.final_pos:.1%}",
            "Notes": note
        })
    df_manifest = pd.DataFrame(manifest_rows)

    # --- 2. PLOTS (Plotly Interactive) ---
    fig = make_subplots(
        rows=1, cols=len(reports),
        subplot_titles=[f"{r.cell_line} ({r.status})" for r in reports],
        horizontal_spacing=0.05
    )

    for i, r in enumerate(reports):
        col_idx = i + 1
        
        # Plot History Points (SCALED TO %)
        for j, df in enumerate(r.history_dfs):
            label = f"Round {j+1}"
            y_percent = df['fraction_bfp'] * 100
            
            fig.add_trace(go.Scatter(
                x=df['volume_ul'], y=y_percent, mode='markers', name=label if i==0 else None,
                marker=dict(size=10 if j > 0 else 8, color='grey', line=dict(width=1, color='black')),
                showlegend=(i==0 and j==0), # Only show R1 legend once
                hovertemplate="Vol: %{x}µL<br>mTagBFP2+: %{y:.1f}%"
            ), row=1, col=col_idx)

        # Plot Model & Tube (SCALED TO %)
        if r.model:
            x_smooth = np.linspace(0, 15, 100)
            y_smooth = [r.model.predict_bfp(v) * 100 for v in x_smooth]
            line_color = '#2ecc71' if r.status == "GO" else '#f39c12'
            
            fig.add_trace(go.Scatter(x=x_smooth, y=y_smooth, mode='lines', line=dict(color=line_color, width=3)), row=1, col=col_idx)
            
            # Uncertainty Tube
            sampled = np.random.choice(r.model.posterior.grid_titer, 1000, p=r.model.posterior.probs)
            ym_percent = (r.model.max_infectivity * (1 - np.exp(-(np.outer(sampled, x_smooth)/100000)))) * 100
            lower = np.percentile(ym_percent, 2.5, axis=0); upper = np.percentile(ym_percent, 97.5, axis=0)
            
            fig.add_trace(go.Scatter(
                x=np.concatenate([x_smooth, x_smooth[::-1]]),
                y=np.concatenate([upper, lower[::-1]]),
                fill='toself', fillcolor=line_color, opacity=0.2, line=dict(width=0),
                name="95% CI" if i==0 else None, showlegend=(i==0), hoverinfo='skip'
            ), row=1, col=col_idx)

        # Formatting
        fig.update_xaxes(title_text="Volume (µL)", row=1, col=col_idx, range=[0, 13])
        if i == 0: fig.update_yaxes(title_text="mTagBFP2+ (%)", row=1, col=col_idx, range=[0, 105])
        else: fig.update_yaxes(showticklabels=False, row=1, col=col_idx, range=[0, 105])

    fig.update_layout(height=400, margin=dict(l=20, r=20, t=40, b=20), template="plotly_white")
    
    # --- 3. ASSEMBLE HTML & BUDGET SECTION ---
    
    # BUDGET SECTION: Itemized Cost Tables
    budget_html = ""
    if costs:
        budget_html += "<h2>4. Financial Summary (Activity-Based Audit)</h2>"
        total_campaign_cost = 0

        for c in costs:
            # Recreate table rows for this cell line's specific audit
            items_data = []
            for item in c.line_items:
                items_data.append({
                    "Category": item.category,
                    "Item": item.name,
                    "Qty Consumed": f"{item.qty:.1f} {item.unit}",
                    "Cost": f"${item.total_cost:.2f}"
                })
            
            df_items = pd.DataFrame(items_data)
            
            budget_html += f"<h3>{c.cell_line} | Total Sunk: <span style='color:#f39c12'>${c.total_sunk_cost:.2f}</span></h3>"
            budget_html += df_items.to_html(escape=False, index=False, border=0, classes='dataframe')
            budget_html += "<br>"
            total_campaign_cost += c.total_sunk_cost
            
        budget_html += f"<div class='header-meta' style='font-size: 1.2em; font-weight: bold;'>GRAND TOTAL (All Titrations): <span style='color:#e74c3c'>${total_campaign_cost:.2f}</span></div>"

    # --- 4. FINAL ASSEMBLY ---
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Titration Campaign Report</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 0; padding: 20px; background: #f4f6f8; }}
            .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 25px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); }}
            h1 {{ color: #2c3e50; margin-bottom: 5px; }}
            .header-meta {{ color: #7f8c8d; font-size: 0.9em; margin-bottom: 25px; }}
            .dataframe {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; font-size: 0.9em; }}
            .dataframe th {{ background-color: #34495e; color: white; padding: 8px; text-align: left; }}
            .dataframe td {{ padding: 8px; border-bottom: 1px solid #eee; }}
            .dataframe tr:nth-child(even) {{ background-color: #f9f9f9; }}
            .log-window {{ background: #2c3e50; color: #ecf0f1; padding: 15px; border-radius: 5px; font-family: 'Monaco', 'Consolas', monospace; font-size: 12px; height: 200px; overflow-y: scroll; white-space: pre-wrap; }}
            h2 {{ font-size: 1.2em; border-bottom: 2px solid #eee; padding-bottom: 10px; margin-top: 30px; }}
            h3 {{ font-size: 1.0em; margin-top: 20px; margin-bottom: 10px; color: #7f8c8d; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🧪 Autonomous Titration Report</h1>
            <div class="header-meta">Generated by cell_OS | Target: {config.target_bfp:.0%} mTagBFP2+ | Guides: {config.num_guides}</div>
            
            <h2>1. Decision Manifest</h2>
            {df_manifest.to_html(escape=False, index=False, border=0, classes='dataframe')}
            
            <h2>2. Data & Models</h2>
            {fig.to_html(full_html=False, include_plotlyjs='cdn')}
            
            {budget_html}
            
            <h2>3. Execution Log</h2>
            <div class="log-window">{log_text}</div>
        </div>
    </body>
    </html>
    """
    
    with open(filename, "w") as f:
        f.write(html_content)
    webbrowser.open('file://' + os.path.realpath(filename))