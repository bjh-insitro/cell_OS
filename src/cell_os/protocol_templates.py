"""
Protocol Templates for Cell Culture Operations.

Defines abstract protocol templates with logical reagent roles and volume keys
that are resolved to concrete parameters via ProtocolResolver.
"""

# T75 Flask Passaging Protocol Template
PASSAGE_T75_TEMPLATE = [
    # Pre-detach
    {"uo": "aspirate", "volume_key": "working_volume"},
    {"uo": "dispense", "reagent_role": "wash_buffer", "volume_key": "wash_1"},
    {"uo": "aspirate", "volume_key": "wash_1"},

    # Detach
    {"uo": "dispense", "reagent_role": "detach_reagent", "volume_key": "detach"},
    {"uo": "incubate", "incubation_key": "detach"},

    # Quench + first collect
    {"uo": "dispense", "reagent_role": "growth_media", "volume_key": "quench"},
    {"uo": "aspirate", "volume_key": "collect_1"},

    # Second wash + collect
    {"uo": "dispense", "reagent_role": "wash_buffer", "volume_key": "wash_2"},
    {"uo": "aspirate", "volume_key": "collect_2"},

    # Centrifuge and pellet handling
    {"uo": "centrifuge", "speed_g": 300, "minutes": 5},
    {"uo": "aspirate", "volume_key": "collect_1"},   # aspirate supernatant after combining volumes

    # Resuspend pellet
    {"uo": "dispense", "reagent_role": "growth_media", "volume_key": "resuspend"},

    # Count 100 µL for NC-202 cassette
    {"uo": "count", "method": "nc202", "volume_key": "count_sample"},
]

# T25 Flask Passaging Protocol Template (Same structure as T75)
PASSAGE_T25_TEMPLATE = [
    # Pre-detach
    {"uo": "aspirate", "volume_key": "working_volume"},
    {"uo": "dispense", "reagent_role": "wash_buffer", "volume_key": "wash_1"},
    {"uo": "aspirate", "volume_key": "wash_1"},

    # Detach
    {"uo": "dispense", "reagent_role": "detach_reagent", "volume_key": "detach"},
    {"uo": "incubate", "incubation_key": "detach"},

    # Quench + first collect
    {"uo": "dispense", "reagent_role": "growth_media", "volume_key": "quench"},
    {"uo": "aspirate", "volume_key": "collect_1"},

    # Second wash + collect
    {"uo": "dispense", "reagent_role": "wash_buffer", "volume_key": "wash_2"},
    {"uo": "aspirate", "volume_key": "collect_2"},

    # Centrifuge and pellet handling
    {"uo": "centrifuge", "speed_g": 300, "minutes": 5},
    {"uo": "aspirate", "volume_key": "collect_1"},   # aspirate supernatant after combining volumes

    # Resuspend pellet
    {"uo": "dispense", "reagent_role": "growth_media", "volume_key": "resuspend"},

    # Count 100 µL for NC-202 cassette
    {"uo": "count", "method": "nc202", "volume_key": "count_sample"},
]
