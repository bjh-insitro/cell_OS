#!/usr/bin/env python3
"""Verify that all plates have identical sentinel scaffold"""

import json
import sys

def verify_scaffold(design_path):
    with open(design_path) as f:
        design = json.load(f)

    wells = design['wells']

    # Get sentinel positions from first plate
    plate1_sentinels = [(w['well_pos'], w['sentinel_type'])
                        for w in wells
                        if w['plate_id'] == 'Plate_1' and w['is_sentinel']]
    plate1_sentinels.sort()

    # Check consistency across all plates
    plates = sorted(set(w['plate_id'] for w in wells))
    consistent = True

    for plate_id in plates:
        plate_sentinels = [(w['well_pos'], w['sentinel_type'])
                          for w in wells
                          if w['plate_id'] == plate_id and w['is_sentinel']]
        plate_sentinels.sort()

        if plate_sentinels != plate1_sentinels:
            print(f'❌ INCONSISTENT: {plate_id} has different sentinel positions')
            consistent = False

    if consistent:
        print(f'✅ VERIFIED: All {len(plates)} plates have identical sentinel positions and types')
        print(f'\nSentinel scaffold ({len(plate1_sentinels)} positions):')
        for pos, stype in plate1_sentinels:
            print(f'  {pos}: {stype}')

        # Count by type
        from collections import Counter
        type_counts = Counter(stype for _, stype in plate1_sentinels)
        print(f'\nSentinel counts by type:')
        for stype in sorted(type_counts.keys()):
            print(f'  {stype}: {type_counts[stype]}')

    return consistent

if __name__ == '__main__':
    design_path = 'data/designs/phase0_founder_v2_regenerated.json'
    if len(sys.argv) > 1:
        design_path = sys.argv[1]

    success = verify_scaffold(design_path)
    sys.exit(0 if success else 1)
