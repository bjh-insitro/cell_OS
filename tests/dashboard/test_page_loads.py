import importlib
import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

PAGE_MODULES = [
    ("dashboard_app.pages.tab_home", "render_home"),
    ("dashboard_app.pages.tab_1_mission_control", "render_mission_control"),
    ("dashboard_app.pages.tab_2_science", "render_science_explorer"),
    ("dashboard_app.pages.tab_3_economics", "render_economics"),
    ("dashboard_app.pages.tab_4_workflow", "render_workflow_visualizer"),
    ("dashboard_app.pages.tab_5_posh_decisions", "render_posh_decisions"),
    ("dashboard_app.pages.tab_6_posh_designer", "render_posh_designer"),
    ("dashboard_app.pages.tab_7_campaign_reports", "render_campaign_reports"),
    ("dashboard_app.pages.tab_8_budget_calculator", "render_budget_calculator"),
    ("dashboard_app.pages.tab_9_phenotype_clustering", "render_phenotype_clustering"),
    ("dashboard_app.pages.tab_analytics", "render_analytics"),
    ("dashboard_app.pages.tab_audit_resources", "render_resource_audit"),
    ("dashboard_app.pages.tab_audit_workflow_bom", "render_workflow_bom_audit"),
    ("dashboard_app.pages.tab_campaign_manager", "render_campaign_manager"),
    ("dashboard_app.pages.tab_campaign_posh", "render_posh_campaign_manager"),
    ("dashboard_app.pages.tab_cell_line_inspector", "render_cell_line_inspector"),
    ("dashboard_app.pages.tab_execution_monitor", "render_execution_monitor"),
    ("dashboard_app.pages.tab_facility_planning", "main"),
    ("dashboard_app.pages.tab_inventory", "render_inventory_manager"),
]


@pytest.mark.parametrize(("module_name", "render_attr"), PAGE_MODULES)
def test_dashboard_pages_exports(module_name, render_attr):
    module = importlib.import_module(module_name)
    assert hasattr(module, render_attr), f"{module_name} missing {render_attr}"
    render_fn = getattr(module, render_attr)
    assert callable(render_fn)
