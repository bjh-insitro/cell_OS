#!/usr/bin/env python3
"""
Reorder phases in tab_campaign_posh.py:
- Move WCB (currently lines 1140-1216) to before Titration
- Change Titration from Phase 2 to Phase 3
"""

import sys

FILE_PATH = "dashboard_app/pages/tab_campaign_posh.py"

with open(FILE_PATH, 'r') as f:
    lines = f.readlines()

# Extract WCB section (lines 1140-1216, 0-indexed: 1139-1215)
wcb_section = lines[1139:1216]

# Remove 4-space indentation from WCB section
wcb_section_unindented = [line[4:] if line.startswith('    ') else line for line in wcb_section]

# Remove WCB section from its current location
lines_without_wcb = lines[:1139] + lines[1216:]

# Find where to insert WCB (after line 877, which is index 876)
# But we need to find the divider after MCB
insert_index = 877  # After "st.divider()" following MCB section

# Insert WCB section
new_lines = lines_without_wcb[:insert_index] + wcb_section_unindented + lines_without_wcb[insert_index:]

# Change "Phase 2: LV MOI Titration" to "Phase 3: LV MOI Titration"
for i, line in enumerate(new_lines):
    if "Phase 2: LV MOI Titration" in line:
        new_lines[i] = line.replace("Phase 2: LV MOI Titration", "Phase 3: LV MOI Titration")

# Write back
with open(FILE_PATH, 'w') as f:
    f.writelines(new_lines)

print("✅ Successfully reordered phases:")
print("  - Phase 1: MCB Generation")
print("  - Phase 2: WCB Generation (moved from end)")
print("  - Phase 3: LV MOI Titration (renumbered from Phase 2)")
