"""
Facility Simulator

Simulates multiple concurrent cell culture campaigns (MCB/WCB) in a shared facility.
Models resource constraints (Incubators, BSCs, Staff) and identifies bottlenecks.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from cell_os.mcb_crash import MCBTestConfig, MCBSimulation
from cell_os.wcb_crash import WCBTestConfig, WCBSimulation

@dataclass
class FacilityConfig:
    """Configuration for the facility."""
    incubator_capacity_flasks: int = 200
    bsc_hours_per_day: float = 8.0
    staff_fte: float = 2.0
    random_seed: int = 42

@dataclass
class CampaignRequest:
    """Request to run a campaign."""
    campaign_type: str  # "MCB" or "WCB"
    cell_line: str
    start_day: int
    campaign_id: str

class FacilitySimulator:
    """Simulates facility operations over time."""
    
    def __init__(self, config: FacilityConfig):
        self.config = config
        self.rng = np.random.default_rng(config.random_seed)
        
        self.campaigns: List[Dict] = [] # Active campaigns
        self.completed_campaigns: List[Dict] = []
        self.schedule: List[CampaignRequest] = []
        
        self.current_day = 0
        self.history = []
        
        # Resource State
        self.incubator_usage = 0
        self.bsc_usage_hours = 0.0
        self.staff_usage_hours = 0.0
        
    def add_campaign(self, request: CampaignRequest):
        """Schedule a campaign."""
        self.schedule.append(request)
        self.schedule.sort(key=lambda x: x.start_day)
        
    def run(self, duration_days: int = 60):
        """Run the facility simulation using Load Stacking."""
        print(f"Starting Facility Simulation for {duration_days} days...")
        
        # Facility Timeline: List of dicts for each day
        timeline = []
        for d in range(duration_days + 1):
            timeline.append({
                "day": d,
                "incubator_usage": 0,
                "bsc_hours": 0.0,
                "staff_hours": 0.0,
                "active_campaigns": 0,
                "violations": []
            })
            
        # Process each campaign
        for req in self.schedule:
            print(f"Processing request: {req.campaign_id} ({req.campaign_type}) starting Day {req.start_day}")
            
            # Run simulation to get profile
            # We disable failures to get a "planned" profile
            if req.campaign_type == "MCB":
                config = MCBTestConfig(num_simulations=1, cell_line=req.cell_line, enable_failures=False)
                sim = MCBSimulation(0, config, self.rng)
            else:
                config = WCBTestConfig(num_simulations=1, cell_line=req.cell_line, enable_failures=False)
                sim = WCBSimulation(0, config, self.rng)
                
            sim.run()
            
            # Stack load onto timeline
            for metric in sim.daily_metrics:
                sim_day = metric['day']
                facility_day = req.start_day + sim_day
                
                if facility_day <= duration_days:
                    day_stat = timeline[facility_day]
                    day_stat['incubator_usage'] += metric['flask_count']
                    day_stat['bsc_hours'] += metric['bsc_hours']
                    day_stat['staff_hours'] += metric['staff_hours']
                    # Only count as active once per day per campaign
                    # But here we iterate metrics, so it's fine.
                    # Actually, active_campaigns should be incremented.
                    # Since we loop metrics, we might increment multiple times if sim has multiple entries per day?
                    # No, daily_metrics is one per day.
                    day_stat['active_campaigns'] += 1
                    
        # Check constraints
        for day_stat in timeline:
            d = day_stat['day']
            if day_stat['incubator_usage'] > self.config.incubator_capacity_flasks:
                day_stat['violations'].append(f"Incubator Overflow: {day_stat['incubator_usage']} > {self.config.incubator_capacity_flasks}")
            
            if day_stat['bsc_hours'] > self.config.bsc_hours_per_day:
                day_stat['violations'].append(f"BSC Overload: {day_stat['bsc_hours']:.1f} > {self.config.bsc_hours_per_day}")
                
        return pd.DataFrame(timeline)
    
    def _process_day(self):
        pass # Not used in Load Stacking approach

    def _compile_results(self):
        pass # Not used
