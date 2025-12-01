"""
Dashboard configuration and page registry.

This module centralizes all page definitions and navigation structure
for the cell_OS dashboard application.
"""

from dataclasses import dataclass
from typing import Callable, Optional, List
from enum import Enum


class PageCategory(Enum):
    """Categories for organizing dashboard pages."""
    CORE = "Core"
    SIMULATION = "Simulation"
    AUDIT = "Audit & Inspection"
    PLANNING = "Planning & Management"
    ANALYSIS = "Analysis & Reports"


@dataclass
class PageConfig:
    """Configuration for a dashboard page."""
    key: str
    title: str
    emoji: str
    render_function: Callable
    category: PageCategory
    description: Optional[str] = None
    order: int = 0


class PageRegistry:
    """Registry for managing dashboard pages."""
    
    def __init__(self):
        self._pages: List[PageConfig] = []
        self._page_map: dict[str, PageConfig] = {}
    
    def register(self, page: PageConfig):
        """Register a new page."""
        self._pages.append(page)
        full_title = f"{page.emoji} {page.title}"
        self._page_map[full_title] = page
    
    def get_page(self, full_title: str) -> Optional[PageConfig]:
        """Get a page by its full title (emoji + title)."""
        return self._page_map.get(full_title)
    
    def get_all_pages(self) -> List[PageConfig]:
        """Get all registered pages sorted by category and order."""
        return sorted(self._pages, key=lambda p: (p.category.value, p.order, p.title))
    
    def get_page_titles(self) -> List[str]:
        """Get all page titles with emojis for navigation."""
        return [f"{p.emoji} {p.title}" for p in self.get_all_pages()]
    
    def get_pages_by_category(self) -> dict[PageCategory, List[PageConfig]]:
        """Get pages grouped by category."""
        categories = {}
        for page in self._pages:
            if page.category not in categories:
                categories[page.category] = []
            categories[page.category].append(page)
        
        # Sort pages within each category
        for category in categories:
            categories[category].sort(key=lambda p: (p.order, p.title))
        
        return categories


def create_page_registry() -> PageRegistry:
    """
    Create and populate the page registry with all dashboard pages.
    
    This is the single source of truth for all pages in the dashboard.
    To add a new page, simply add a new PageConfig here.
    """
    # Import all page renderers
    from dashboard_app.pages.tab_home import render_home
    from dashboard_app.pages.tab_1_mission_control import render_mission_control
    from dashboard_app.pages.tab_2_science import render_science_explorer
    from dashboard_app.pages.tab_3_economics import render_economics
    from dashboard_app.pages.tab_4_workflow import render_workflow_visualizer
    from dashboard_app.pages.tab_audit_resources import render_resource_audit
    from dashboard_app.pages.tab_audit_workflow_bom import render_workflow_bom_audit
    from dashboard_app.pages.tab_cell_line_inspector import render_cell_line_inspector
    from dashboard_app.pages.tab_execution_monitor import render_execution_monitor
    from dashboard_app.pages.tab_analytics import render_analytics
    from dashboard_app.pages.tab_inventory import render_inventory_manager
    from dashboard_app.pages.tab_campaign_manager import render_campaign_manager
    from dashboard_app.pages.tab_campaign_posh import render_posh_campaign_manager
    from dashboard_app.pages.tab_5_posh_decisions import render_posh_decisions
    from dashboard_app.pages.tab_6_posh_designer import render_posh_designer
    from dashboard_app.pages.tab_7_campaign_reports import render_campaign_reports
    from dashboard_app.pages.tab_8_budget_calculator import render_budget_calculator
    from dashboard_app.pages.tab_9_phenotype_clustering import render_phenotype_clustering
    
    registry = PageRegistry()
    
    # Core Pages
    registry.register(PageConfig(
        key="home",
        title="Home",
        emoji="🏠",
        render_function=render_home,
        category=PageCategory.CORE,
        description="Overview, quick start, and shortcuts",
        order=0
    ))

    registry.register(PageConfig(
        key="mission_control",
        title="Mission Control",
        emoji="🚀",
        render_function=render_mission_control,
        category=PageCategory.CORE,
        description="Main dashboard overview and system status",
        order=1
    ))
    
    registry.register(PageConfig(
        key="science",
        title="Science",
        emoji="🔬",
        render_function=render_science_explorer,
        category=PageCategory.CORE,
        description="Scientific data exploration",
        order=2
    ))
    
    registry.register(PageConfig(
        key="economics",
        title="Economics",
        emoji="💰",
        render_function=render_economics,
        category=PageCategory.CORE,
        description="Financial analysis and cost tracking",
        order=3
    ))
    
    # Simulation Pages
    registry.register(PageConfig(
        key="posh_campaign_sim",
        title="POSH Campaign Sim",
        emoji="🧬",
        render_function=render_posh_campaign_manager,
        category=PageCategory.SIMULATION,
        description="POSH campaign simulation and management",
        order=1
    ))
    
    registry.register(PageConfig(
        key="workflow_visualizer",
        title="Workflow Visualizer",
        emoji="🕸️",
        render_function=render_workflow_visualizer,
        category=PageCategory.SIMULATION,
        description="Visualize workflow execution graphs",
        order=2
    ))
    
    # Audit & Inspection Pages
    registry.register(PageConfig(
        key="resource_audit",
        title="Resource Audit",
        emoji="🛠️",
        render_function=render_resource_audit,
        category=PageCategory.AUDIT,
        description="Audit resource usage and availability",
        order=1
    ))
    
    registry.register(PageConfig(
        key="workflow_bom_audit",
        title="Workflow BOM Audit",
        emoji="🔍",
        render_function=render_workflow_bom_audit,
        category=PageCategory.AUDIT,
        description="Bill of materials audit for workflows",
        order=2
    ))
    
    registry.register(PageConfig(
        key="cell_line_inspector",
        title="Cell Line Inspector",
        emoji="🧬",
        render_function=render_cell_line_inspector,
        category=PageCategory.AUDIT,
        description="Inspect cell line configurations and parameters",
        order=3
    ))
    
    registry.register(PageConfig(
        key="execution_monitor",
        title="Execution Monitor",
        emoji="⚙️",
        render_function=render_execution_monitor,
        category=PageCategory.AUDIT,
        description="Monitor workflow execution in real-time",
        order=4
    ))
    
    # Planning & Management Pages
    registry.register(PageConfig(
        key="inventory",
        title="Inventory",
        emoji="📦",
        render_function=render_inventory_manager,
        category=PageCategory.PLANNING,
        description="Manage inventory and resources",
        order=1
    ))
    
    registry.register(PageConfig(
        key="campaign_manager",
        title="Campaign Manager",
        emoji="🗓️",
        render_function=render_campaign_manager,
        category=PageCategory.PLANNING,
        description="Plan and manage campaigns",
        order=2
    ))
    
    registry.register(PageConfig(
        key="posh_decisions",
        title="POSH Decision Assistant",
        emoji="🧭",
        render_function=render_posh_decisions,
        category=PageCategory.PLANNING,
        description="Decision support for POSH experiments",
        order=3
    ))
    
    registry.register(PageConfig(
        key="posh_designer",
        title="POSH Screen Designer",
        emoji="🧪",
        render_function=render_posh_designer,
        category=PageCategory.PLANNING,
        description="Design POSH screening experiments",
        order=4
    ))
    
    registry.register(PageConfig(
        key="budget_calculator",
        title="Budget Calculator",
        emoji="🧮",
        render_function=render_budget_calculator,
        category=PageCategory.PLANNING,
        description="Calculate experiment budgets",
        order=5
    ))
    
    # Analysis & Reports Pages
    registry.register(PageConfig(
        key="analytics",
        title="Analytics",
        emoji="📈",
        render_function=render_analytics,
        category=PageCategory.ANALYSIS,
        description="Advanced analytics and insights",
        order=1
    ))
    
    registry.register(PageConfig(
        key="campaign_reports",
        title="Campaign Reports",
        emoji="📊",
        render_function=render_campaign_reports,
        category=PageCategory.ANALYSIS,
        description="Generate campaign reports",
        order=2
    ))
    
    registry.register(PageConfig(
        key="phenotype_clustering",
        title="Phenotype Clustering",
        emoji="🧬",
        render_function=render_phenotype_clustering,
        category=PageCategory.ANALYSIS,
        description="Cluster and analyze phenotype data",
        order=3
    ))
    
    return registry
