import json
from pathlib import Path

nb_path = Path('/Users/aarontopol/Desktop/cell_OS/notebooks/Generate_Plate_Design.ipynb')
with open(nb_path, 'r') as f:
    nb = json.load(f)

# Define the content for each major section
setup_content = r"""%load_ext autoreload
%autoreload 2
import sys
import csv
import re
import json
import os
from datetime import datetime
from pathlib import Path
import ipywidgets as widgets
from IPython.display import display, clear_output

# Add scripts to path
sys.path.append('../scripts')
import generate_custom_plate
from notebook_utils import ChecklistWidget, get_default_doses_str, get_default_seeding_str
"""

# Find the setup cell and update it
for cell in nb['cells']:
    if cell['cell_type'] == 'code':
        source = ''.join(cell['source'])
        if 'sys.path.append' in source:
            cell['source'] = [line + '\n' for line in setup_content.strip().split('\n')]
            break

with open(nb_path, 'w') as f:
    json.dump(nb, f, indent=1)

print("Notebook setup cell updated (removed pip install).")
