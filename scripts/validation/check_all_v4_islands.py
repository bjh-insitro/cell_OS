#!/usr/bin/env python3
"""Check CV for all 8 v4 islands."""

import json
import numpy as np
from pathlib import Path

v4_file = sorted(Path("validation_frontend/public/demo_results/calibration_plates").glob("CAL_384_RULES_WORLD_v4_run_*_seed42.json"))[0]

with open(v4_file) as f:
    data = json.load(f)

# All 8 islands
islands = {
    'CV_NW_HEPG2_VEH': ['D4','D5','D6','E4','E5','E6','F4','F5','F6'],
    'CV_NW_A549_VEH': ['D8','D9','D10','E8','E9','E10','F8','F9','F10'],
    'CV_NE_HEPG2_VEH': ['D15','D16','D17','E15','E16','E17','F15','F16','F17'],
    'CV_NE_A549_VEH': ['D20','D21','D22','E20','E21','E22','F20','F21','F22'],
    'CV_SW_HEPG2_MORPH': ['K4','K5','K6','L4','L5','L6','M4','M5','M6'],
    'CV_SW_A549_MORPH': ['K8','K9','K10','L8','L9','L10','M8','M9','M10'],
    'CV_SE_HEPG2_VEH': ['K15','K16','K17','L15','L16','L17','M15','M16','M17'],
    'CV_SE_A549_DEATH': ['K20','K21','K22','L20','L21','L22','M20','M21','M22']
}

print("CV for Each Island (morph_nucleus):\n")
cvs = []
for name, wells in islands.items():
    results = [r for r in data['flat_results'] if r['well_id'] in wells]
    values = [r['morph_nucleus'] for r in results]
    if values:
        cv = (np.std(values, ddof=1) / np.mean(values)) * 100
        cvs.append(cv)
        print(f"{name:25s}: {cv:6.2f}%")

print(f"\nOverall Island Mean CV: {np.mean(cvs):.2f}% ± {np.std(cvs):.2f}%")
