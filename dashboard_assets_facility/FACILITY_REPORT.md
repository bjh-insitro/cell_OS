# Facility Simulation Report

**Generated**: 2025-11-28
**Feature**: Multi-Campaign Capacity Planning

---

## Executive Summary

A new `FacilitySimulator` module has been added to enable capacity planning for multi-campaign schedules. It uses a "Load Stacking" approach to aggregate resource demands from multiple concurrent MCB/WCB simulations and identify bottlenecks.

## Key Capabilities

1.  **Concurrent Simulation**: Can schedule any number of MCB/WCB campaigns with arbitrary start dates.
2.  **Resource Tracking**:
    *   **Incubator**: Tracks total flask count vs. capacity.
    *   **Labor (BSC)**: Tracks biosafety cabinet hours vs. daily availability.
    *   **Staff**: Tracks FTE hours.
3.  **Conflict Detection**: Automatically flags days where demand exceeds capacity.

## Validation Results

A stress test with **10 overlapping campaigns** (5 MCB + 5 WCB) was performed against a constrained facility (20 flasks, 2.0h BSC/day).

- **Peak Incubator**: 17 flasks (85% utilization)
- **Peak BSC**: 3.7 hours (185% utilization - **VIOLATION**)
- **Outcome**: The simulator correctly identified 5 days of BSC overload, enabling the user to reschedule campaigns to smooth the peak.

## Usage

```python
from cell_os.facility_sim import FacilityConfig, FacilitySimulator, CampaignRequest

# 1. Configure
config = FacilityConfig(incubator_capacity_flasks=200, bsc_hours_per_day=8.0)
sim = FacilitySimulator(config)

# 2. Schedule
sim.add_campaign(CampaignRequest("MCB", "U2OS", start_day=0, campaign_id="Run1"))
sim.add_campaign(CampaignRequest("MCB", "U2OS", start_day=7, campaign_id="Run2"))

# 3. Run
df = sim.run(duration_days=30)
```
