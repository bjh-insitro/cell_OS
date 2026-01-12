"""
Phase 0 Fixed Sentinel Scaffold

28 fixed well positions for sentinels, with type assignments.
Same positions and types on EVERY plate (all timepoints, all days, all operators, all cell lines).

This makes:
- SPC drift detection trivial (compare same wells over time)
- Spatial confounding impossible (fixed geometry)
- Warnings about sentinel distribution irrelevant (by design)
"""

import hashlib
import json

# Versioned scaffold contract
SCAFFOLD_ID = "phase0_v2_scaffold_v1"
SCAFFOLD_VERSION = "1.0.0"

# Fixed 28 positions (evenly distributed across 96-well plate with exclusions)
# Exclusions: A01, A06, A07, A12, H01, H06, H07, H12
SENTINEL_POSITIONS = [
    "A02", "A05", "A10",  # Row A (3)
    "B02", "B06", "B09", "B12",  # Row B (4)
    "C03", "C06", "C09", "C12",  # Row C (4)
    "D04", "D07", "D10",  # Row D (3)
    "E01", "E04", "E07", "E10",  # Row E (4)
    "F02", "F05", "F08", "F11",  # Row F (4)
    "G02", "G05", "G08", "G12",  # Row G (4)
    "H04", "H09",  # Row H (2)
]

# Fixed 28 positions for 384-well plate (distributed across entire area)
SENTINEL_POSITIONS_384 = [
    "A04", "A12", "A20",
    "C08", "C16", "C24",
    "E04", "E12", "E20",
    "G08", "G16", "G24",
    "I04", "I12", "I20",
    "K08", "K16", "K24",
    "M04", "M12", "M20",
    "O08", "O16", "O24",
    "B02", "F02", "J02", "N02"
]

# Type assignments (greedy placement with separation constraints)
# vehicle (8): min gap = 3
# ER_mid, mito_mid (5 each): min gap = 3
# oxidative, proteostasis (5 each): min gap = 1-2 (acceptable)
SENTINEL_SCAFFOLD = [
    {"position": "A02", "type": "vehicle"},
    {"position": "A05", "type": "ER_mid"},
    {"position": "A10", "type": "mito_mid"},
    {"position": "B02", "type": "vehicle"},
    {"position": "B06", "type": "ER_mid"},
    {"position": "B09", "type": "mito_mid"},
    {"position": "B12", "type": "vehicle"},
    {"position": "C03", "type": "ER_mid"},
    {"position": "C06", "type": "mito_mid"},
    {"position": "C09", "type": "vehicle"},
    {"position": "C12", "type": "ER_mid"},
    {"position": "D04", "type": "mito_mid"},
    {"position": "D07", "type": "vehicle"},
    {"position": "D10", "type": "ER_mid"},
    {"position": "E01", "type": "mito_mid"},
    {"position": "E04", "type": "vehicle"},
    {"position": "E07", "type": "oxidative"},
    {"position": "E10", "type": "oxidative"},
    {"position": "F02", "type": "vehicle"},
    {"position": "F05", "type": "oxidative"},
    {"position": "F08", "type": "proteostasis"},
    {"position": "F11", "type": "vehicle"},
    {"position": "G02", "type": "oxidative"},
    {"position": "G05", "type": "proteostasis"},
    {"position": "G08", "type": "proteostasis"},
    {"position": "G12", "type": "oxidative"},
    {"position": "H04", "type": "proteostasis"},
    {"position": "H09", "type": "proteostasis"},
]

# Phase 0 sentinel schema (doses)
PHASE0_SENTINEL_SCHEMA = {
    'vehicle': {'compound': 'DMSO', 'dose_uM': 0.0},
    'ER_mid': {'compound': 'thapsigargin', 'dose_uM': 0.5},
    'mito_mid': {'compound': 'oligomycin', 'dose_uM': 1.0},
    'proteostasis': {'compound': 'MG132', 'dose_uM': 1.0},
    'oxidative': {'compound': 'tBHQ', 'dose_uM': 30.0},
}


def compute_scaffold_hash():
    """
    Compute deterministic hash of scaffold specification.
    Hash includes: position, type, compound, dose (sorted for stability).
    """
    items = []
    for entry in SENTINEL_SCAFFOLD:
        schema = PHASE0_SENTINEL_SCHEMA[entry['type']]
        items.append({
            'position': entry['position'],
            'type': entry['type'],
            'compound': schema['compound'],
            'dose_uM': schema['dose_uM'],
        })

    # Sort by position for deterministic hash
    items.sort(key=lambda x: x['position'])

    # Canonical JSON representation
    canonical = json.dumps(items, sort_keys=True, separators=(',', ':'))

    # SHA256 hash (first 16 chars for human readability)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:16]


# Compute hash at module load time (frozen)
SCAFFOLD_HASH = compute_scaffold_hash()


def get_sentinel_tokens():
    """
    Get fixed sentinel tokens for Phase 0.
    Returns list of 28 sentinel tokens in position order.
    """
    tokens = []
    for entry in SENTINEL_SCAFFOLD:
        schema = PHASE0_SENTINEL_SCHEMA[entry['type']]
        tokens.append({
            'position': entry['position'],
            'compound': schema['compound'],
            'dose_uM': schema['dose_uM'],
            'is_sentinel': True,
            'sentinel_type': entry['type'],
        })
    return tokens


def get_dynamic_sentinel_tokens(cell_lines, pathways, reps_per_pathway=3, vehicle_reps_per_cl=4):
    """
    Generate dynamic sentinel tokens for multiple cell lines and selected pathways.
    """
    tokens = []
    # Map user-friendly pathway names to schema keys
    pathway_map = {
        'ER Stress': 'ER_mid',
        'Mitochondrial Stress': 'mito_mid',
        'Proteostasis': 'proteostasis',
        'Oxidative Stress': 'oxidative',
        'Metabolic Stress': 'mito_mid', # Fallback or specific mapping
        'DNA Damage': 'oxidative', # Fallback
        'Cytoskeletal Stress': 'proteostasis', # Fallback
        'Epigenetic Stress': 'proteostasis' # Fallback
    }
    
    # Limit to first 2 cell lines as requested
    target_cell_lines = cell_lines[:2]
    
    for cl in target_cell_lines:
        # Add Vehicle
        for _ in range(vehicle_reps_per_cl):
            schema = PHASE0_SENTINEL_SCHEMA['vehicle']
            tokens.append({
                'cell_line': cl,
                'compound': schema['compound'],
                'dose_uM': schema['dose_uM'],
                'is_sentinel': True,
                'sentinel_type': 'vehicle'
            })
            
        # Add Stress Pathways
        for p in pathways:
            schema_key = pathway_map.get(p)
            if schema_key and schema_key in PHASE0_SENTINEL_SCHEMA:
                schema = PHASE0_SENTINEL_SCHEMA[schema_key]
                for _ in range(reps_per_pathway):
                    tokens.append({
                        'cell_line': cl,
                        'compound': schema['compound'],
                        'dose_uM': schema['dose_uM'],
                        'is_sentinel': True,
                        'sentinel_type': schema_key
                    })
    return tokens


def get_scaffold_metadata():
    """
    Get scaffold versioning metadata for embedding in designs and certificates.
    """
    # Count types from scaffold (not schema, which doesn't have 'n')
    from collections import Counter
    type_counts = Counter(entry['type'] for entry in SENTINEL_SCAFFOLD)

    return {
        'scaffold_id': SCAFFOLD_ID,
        'scaffold_version': SCAFFOLD_VERSION,
        'scaffold_hash': SCAFFOLD_HASH,
        'scaffold_size': len(SENTINEL_SCAFFOLD),
        'scaffold_types': dict(type_counts),
    }


def get_experimental_positions(plate_format=96, exclusions=None):
    """
    Get positions for experimental wells (non-sentinel, non-excluded).
    Returns 60 positions for Phase 0 V2 (88 available - 28 sentinels).
    """
    if exclusions is None:
        exclusions = {'A01', 'A12', 'H01', 'H12', 'A06', 'A07', 'H06', 'H07'}

    # Generate all positions
    n_rows = 8 if plate_format == 96 else 16
    n_cols = 12 if plate_format == 96 else 24
    rows = [chr(65 + i) for i in range(n_rows)]

    all_positions = [f"{row}{col:02d}" for row in rows for col in range(1, n_cols + 1)]

    # Filter out excluded and sentinel positions
    sentinel_positions_set = set(SENTINEL_POSITIONS)
    experimental_positions = [
        pos for pos in all_positions
        if pos not in exclusions and pos not in sentinel_positions_set
    ]

    return experimental_positions


if __name__ == '__main__':
    import json

    print("Phase 0 Fixed Sentinel Scaffold\n")
    print(f"Total sentinel positions: {len(SENTINEL_POSITIONS)}")
    print(f"Total experimental positions: {len(get_experimental_positions())}\n")

    # Count by type
    from collections import Counter
    type_counts = Counter(entry['type'] for entry in SENTINEL_SCAFFOLD)
    print("Sentinel counts by type:")
    for stype, count in sorted(type_counts.items()):
        positions = [e['position'] for e in SENTINEL_SCAFFOLD if e['type'] == stype]
        print(f"  {stype:15s}: {count} - {', '.join(positions)}")

    print("\n\nScaffold JSON:")
    print(json.dumps(SENTINEL_SCAFFOLD, indent=2))
