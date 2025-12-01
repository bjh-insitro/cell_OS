# Inventory and Campaign Management

## Overview

cell_OS provides advanced capabilities for managing lab resources and scheduling high-throughput campaigns. This guide covers the **Inventory Manager** for tracking stock and the **Campaign Manager** for planning experiments.

## 📦 Inventory Manager

The Inventory Manager tracks the consumption of reagents and consumables, ensuring you never run out of critical supplies.

### Key Features

- **Persistent Tracking**: Stock levels are saved to a local database (`data/inventory.db`).
- **Lot Management**: Track specific lots of reagents (e.g., "DMEM Lot A123") with expiration dates.
- **FIFO Consumption**: Automatically consumes from the oldest active lot first (First-In, First-Out).
- **Auto-Deduction**: When a protocol executes, required resources are automatically deducted from inventory.

### Usage

> **Note on data sources:** `Inventory` hydrates from the canonical SQLite database (`data/inventory.db`) when no path is provided. Legacy YAML fixtures (e.g., `data/raw/pricing.yaml`) still work for tests/notebooks, but production edits should be made via the DB or the `InventoryManager` API.

#### Viewing Stock
Navigate to the **📦 Inventory** tab in the dashboard to view current stock levels, filter by category, and search for specific items.

#### Adding Stock (Restocking)
1. Go to the **➕ Restock** sub-tab.
2. Select the resource to add.
3. Enter the quantity and optional Lot ID/Expiration Date.
4. Click "Add Stock".

#### Transaction History
View a complete log of all stock additions and consumptions in the **📜 Transaction History** sub-tab.

---

## 🗓️ Campaign Manager

The Campaign Manager allows you to design and schedule long-term experimental campaigns, such as maintaining cell lines or running screening assays.

### Key Features

- **Campaign Design Wizard**: Quickly generate schedules for common tasks (e.g., "Passage every 3 days for 2 weeks").
- **Automated Scheduling**: Creates a calendar of jobs with specific dates and times.
- **Queue Integration**: Submits generated jobs directly to the **Job Queue** for execution.

### Creating a Campaign

1. Navigate to the **🗓️ Campaign Manager** tab.
2. Enter a **Campaign Name** (e.g., "HEK293T Maintenance").
3. Select parameters:
   - **Cell Line**: The cell line to use.
   - **Vessel**: The culture vessel (e.g., T75 Flask).
   - **Duration**: How many days the campaign runs.
   - **Intervals**: How often to Feed and Passage.
4. Click **Generate Schedule**.
5. Review the preview table.
6. Click **🚀 Submit Campaign to Queue** to finalize.

### Monitoring

Once submitted, you can track the progress of your campaign in the **Active Campaigns** section or view individual jobs in the **Execution Monitor**.

---

## Technical Details

### Database Schema
- **Inventory**: Stores `lots` and `transactions` in `data/inventory.db`.
- **Campaigns**: Stores `campaigns` and `campaign_jobs` in `data/campaigns.db`.

### Python API

```python
from cell_os.inventory_manager import InventoryManager
from cell_os.campaign_manager import CampaignManager

# Initialize
inv_manager = InventoryManager(inventory)
camp_manager = CampaignManager(job_queue, executor, resolver)

# Add stock
inv_manager.add_stock("res-dmem", 500.0, lot_id="LOT-123")

# Create campaign
campaign = camp_manager.create_campaign("My Campaign")
camp_manager.generate_maintenance_schedule(campaign.campaign_id, ...)
camp_manager.submit_campaign(campaign.campaign_id)
```
