# Database Repository Pattern Migration Guide

## Overview

The database access layer has been refactored to use the **Repository Pattern**, which provides:
- **Separation of concerns**: Business logic separated from SQL
- **Testability**: Easy to mock repositories for testing
- **Consistency**: Common CRUD operations in base class
- **Type safety**: Dataclasses for all models

## Architecture

```
src/cell_os/database/
├── __init__.py           # Package exports
├── base.py               # BaseRepository with common CRUD
└── repositories/
    ├── __init__.py
    └── campaign.py       # CampaignRepository
```

## Before (Old Pattern)

```python
# Direct SQL in business logic
import sqlite3

conn = sqlite3.connect("data/campaigns.db")
cursor = conn.cursor()
cursor.execute(
    "INSERT INTO campaigns (campaign_id, campaign_type) VALUES (?, ?)",
    ("campaign_1", "autonomous")
)
conn.commit()
conn.close()
```

## After (Repository Pattern)

```python
# Clean, testable repository pattern
from cell_os.database import CampaignRepository, Campaign

repo = CampaignRepository()
campaign = Campaign(
    campaign_id="campaign_1",
    campaign_type="autonomous"
)
repo.create_campaign(campaign)
```

## Usage Examples

### Creating a Campaign

```python
from cell_os.database import CampaignRepository, Campaign

repo = CampaignRepository("data/campaigns.db")

campaign = Campaign(
    campaign_id="my_campaign",
    campaign_type="autonomous",
    goal="Optimize cell viability",
    config={"max_iterations": 10}
)

repo.create_campaign(campaign)
```

### Retrieving a Campaign

```python
campaign = repo.get_campaign("my_campaign")
print(f"Status: {campaign.status}")
print(f"Config: {campaign.config}")
```

### Updating Campaign Status

```python
repo.update_campaign_status(
    "my_campaign",
    status="completed",
    results_summary={"final_score": 0.95}
)
```

### Adding Iterations

```python
from cell_os.database import CampaignIteration

iteration = CampaignIteration(
    campaign_id="my_campaign",
    iteration_number=1,
    proposals=[{"experiment": "exp_1"}],
    metrics={"score": 0.85}
)

repo.add_iteration(iteration)
```

### Finding Campaigns

```python
# Find all autonomous campaigns
autonomous_campaigns = repo.find_campaigns(campaign_type="autonomous")

# Find completed campaigns
completed = repo.find_campaigns(status="completed")
```

## Benefits

### 1. **Testability**

```python
# Easy to mock for testing
from unittest.mock import Mock

mock_repo = Mock(spec=CampaignRepository)
mock_repo.get_campaign.return_value = Campaign(
    campaign_id="test",
    campaign_type="manual"
)
```

### 2. **Type Safety**

```python
# IDE autocomplete and type checking
campaign: Campaign = repo.get_campaign("id")
campaign.status  # ← IDE knows this is a string
campaign.config  # ← IDE knows this is Optional[Dict]
```

### 3. **Consistent API**

All repositories inherit from `BaseRepository`:
- `_fetch_one()` - Get single row as dict
- `_fetch_all()` - Get all rows as list of dicts
- `_insert()` - Insert row
- `_update()` - Update rows
- `_delete()` - Delete rows

### 4. **No SQL in Business Logic**

```python
# Before: SQL scattered everywhere
cursor.execute("SELECT * FROM campaigns WHERE status = ?", ("running",))

# After: Clean method calls
running_campaigns = repo.find_campaigns(status="running")
```

## Migration Path

### Step 1: Keep Old Code Working

The old `campaign_db.py` still exists and works. No immediate changes needed.

### Step 2: Gradually Migrate

Start using the new repository in new code:

```python
# New code
from cell_os.database import CampaignRepository
repo = CampaignRepository()
```

### Step 3: Update Existing Code

When refactoring existing modules, replace direct SQL with repository calls:

```python
# Old
from cell_os.campaign_db import CampaignDatabase
db = CampaignDatabase()

# New
from cell_os.database import CampaignRepository
repo = CampaignRepository()
```

## Creating New Repositories

To add a new repository (e.g., for inventory):

1. **Create the repository file**:

```python
# src/cell_os/database/repositories/inventory.py
from ..base import BaseRepository
from dataclasses import dataclass

@dataclass
class InventoryItem:
    item_id: str
    name: str
    quantity: int

class InventoryRepository(BaseRepository):
    def _init_schema(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                item_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                quantity INTEGER DEFAULT 0
            )
        """)
        conn.commit()
        conn.close()
    
    def get_item(self, item_id: str):
        row = self._fetch_one(
            "SELECT * FROM inventory WHERE item_id = ?",
            (item_id,)
        )
        return InventoryItem(**row) if row else None
```

2. **Export from `__init__.py`**:

```python
# src/cell_os/database/__init__.py
from .repositories.inventory import InventoryRepository, InventoryItem

__all__ = [..., 'InventoryRepository', 'InventoryItem']
```

3. **Write tests**:

```python
# tests/unit/test_inventory_repository.py
def test_inventory_repository(tmp_path):
    repo = InventoryRepository(str(tmp_path / "test.db"))
    # ... test code
```

## Best Practices

1. **Use dataclasses for models** - Type safety and IDE support
2. **Keep SQL in repositories** - Don't leak SQL into business logic
3. **Use transactions for multi-step operations** - Override `_get_connection()` if needed
4. **Write tests for all repository methods** - Easy to test with `tmp_path`
5. **Use meaningful method names** - `get_campaign()` not `fetch_by_id()`

## Next Steps

- Migrate `cell_line_db.py` to `CellLineRepository`
- Migrate `simulation_params_db.py` to `SimulationParamsRepository`
- Migrate `experimental_db.py` to `ExperimentRepository`
- Add connection pooling for performance
- Add query caching where appropriate

---

**Status**: ✅ CampaignRepository implemented and tested  
**Tests**: 6/6 passing  
**Backward Compatible**: Yes (old code still works)
