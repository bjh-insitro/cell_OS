# Cell Line Database Migration - SQLite Backend

**Date**: 2025-11-29  
**Status**: ✅ Complete

## What Changed

### Before
- Cell line data stored in `data/cell_lines.yaml` (614 lines, human-edited)
- `cell_line_database.py` read from YAML file
- Dual systems: YAML + SQLite (confusing)

### After
- **Single source of truth**: `data/cell_lines.db` (SQLite database)
- `cell_line_database.py` now reads from SQLite
- YAML archived to `data/archive/cell_lines.yaml.backup_YYYYMMDD`

## Migration Steps Completed

1. ✅ Created migration script (`scripts/migrate_yaml_to_db.py`)
2. ✅ Migrated all 13 cell lines from YAML to SQLite
3. ✅ Rewrote `cell_line_database.py` to use SQLite backend
4. ✅ Archived YAML file to `data/archive/`
5. ✅ Verified all data migrated correctly
6. ✅ Fixed iPSC freezing_media value (cryostor_cs10)
7. ✅ Tested dashboard - all working

## Database Schema

### Tables
1. **cell_lines** - Core metadata (name, type, media, coating, etc.)
2. **cell_line_characteristics** - Flexible key-value pairs (dissociation, transfection, freezing params)
3. **cell_line_protocols** - Protocol parameters for different vessels
4. **cell_line_inventory** - Actual vials in freezers
5. **cell_line_usage** - Usage history

### iPSC Example
```sql
-- Core metadata
cell_line_id: iPSC
display_name: Induced Pluripotent Stem Cells
cell_type: iPSC
growth_media: mtesr_plus_kit
coating_required: 1
coating_reagent: vitronectin

-- Characteristics (key-value)
dissociation_method: accutase
freezing_media: cryostor_cs10
vial_type: tube_micronic_075
freezing_volume_ml: 0.35
cells_per_vial: 1000000
```

## API Compatibility

The `cell_line_database.py` API remains **100% compatible**:

```python
from cell_os.cell_line_database import get_cell_line_profile

profile = get_cell_line_profile('iPSC')
# Returns same CellLineProfile dataclass as before
```

## Benefits

1. ✅ **Single source of truth** - No more YAML/SQLite confusion
2. ✅ **Queryable** - Can filter by type, cost tier, etc.
3. ✅ **Scalable** - Handles inventory, usage tracking
4. ✅ **Transactional** - ACID guarantees
5. ✅ **Programmatic** - Easy to update via Python API
6. ✅ **Backward compatible** - No code changes needed

## How to Add/Update Cell Lines

### Option 1: Python API
```python
from cell_os.cell_line_db import CellLineDatabase, CellLine, CellLineCharacteristic

db = CellLineDatabase()

# Add cell line
cell_line = CellLine(
    cell_line_id="CHO",
    display_name="Chinese Hamster Ovary",
    cell_type="immortalized",
    growth_media="dmem_10fbs",
    coating_required=False
)
db.add_cell_line(cell_line)

# Add characteristics
db.add_characteristic(CellLineCharacteristic(
    cell_line_id="CHO",
    characteristic="freezing_media",
    value="cryostor_cs10"
))
```

### Option 2: SQL
```bash
sqlite3 data/cell_lines.db
```

```sql
INSERT INTO cell_lines (cell_line_id, display_name, cell_type, growth_media)
VALUES ('CHO', 'Chinese Hamster Ovary', 'immortalized', 'dmem_10fbs');

INSERT INTO cell_line_characteristics (cell_line_id, characteristic, value)
VALUES ('CHO', 'freezing_media', 'cryostor_cs10');
```

## Files Changed

- ✅ `src/cell_os/cell_line_database.py` - Rewritten to use SQLite
- ✅ `scripts/migrate_yaml_to_db.py` - Migration script (can be rerun)
- ✅ `data/cell_lines.db` - New database (13 cell lines)
- ✅ `data/archive/cell_lines.yaml.backup_*` - Archived YAML

## Verification

```bash
# Check database
sqlite3 data/cell_lines.db "SELECT cell_line_id, display_name FROM cell_lines"

# Test Python API
python3 -c "from cell_os.cell_line_database import list_cell_lines; print(list_cell_lines())"
```

## Next Steps (Optional)

1. Add more cell lines via Python API
2. Populate inventory table with actual vials
3. Track usage history
4. Create dashboard for database management
