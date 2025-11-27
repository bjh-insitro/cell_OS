import sys
import os
import matplotlib.pyplot as plt

# 1. Setup Path
sys.path.append(os.path.join(os.getcwd(), 'src'))

# Import all necessary modules
from cell_os.titration_loop import AutonomousTitrationAgent
from cell_os.posh_lv_moi import ScreenConfig
from cell_os.generate_manifest import generate_screen_manifest
from cell_os.budget_manager import calculate_campaign_cost, BudgetConfig
from cell_os.html_reporter import generate_html_report

# 2. Define the "Ground Truth" Biological Scenarios
campaign_targets = [
    {"name": "U2OS", "true_params": {"titer": 35000, "alpha": 0.98}},
    {"name": "A549", "true_params": {"titer": 22000, "alpha": 0.95}},
    {"name": "HepG2", "true_params": {"titer": 6500, "alpha": 0.85}}
]

# 3. Configure the System (Defines the 'config' variable)
config = ScreenConfig(
    num_guides=4000, 
    coverage_target=1000, 
    target_bfp=0.30,
    pipetting_error=0.05
)

# 4. Initialize Budget Engine (Defines the 'prices' variable)
print("📥 Connecting to Recipe Optimizer...")
prices = BudgetConfig.from_optimizer() 

# 5. RUN CAMPAIGN (The Agent Initialization)
print("\n🚀 LAUNCHING AUTONOMOUS TITRATION CAMPAIGN")
print("="*60)

# The agent now receives the necessary configuration and pricing objects
agent = AutonomousTitrationAgent(config, prices) 
final_reports = agent.run_campaign(campaign_targets)

# 6. Generate Manifest (The Manager)
generate_screen_manifest(final_reports, config)

# 7. Generate Budget Report (The Accountant)
cost_summaries = calculate_campaign_cost(final_reports, prices)

# 8. Generate Dashboard (The Reporter)
print("\n📊 GENERATING INTERACTIVE DASHBOARD...")
full_log_text = "\n".join(agent.logs)

generate_html_report(
    reports=final_reports, 
    config=config, 
    log_text=full_log_text, 
    costs=cost_summaries
)