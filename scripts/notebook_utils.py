import ipywidgets as widgets
from IPython.display import display

class ChecklistWidget(widgets.VBox):
    def __init__(self, options, value=None, description=""):
        self.options = options
        self.description_label = widgets.Label(value=description)
        self.checkboxes = [
            widgets.Checkbox(value=(opt in (value or [])), description=opt, style={'description_width': 'initial'})
            for opt in options
        ]
        super().__init__([self.description_label] + self.checkboxes)
        self._observers = []
        
        for cb in self.checkboxes:
            cb.observe(self._on_change, names='value')
            
    def _on_change(self, change):
        for callback in self._observers:
            callback(self.value)
            
    def observe_changes(self, callback):
        self._observers.append(callback)
        
    @property
    def value(self):
        return [cb.description for cb in self.checkboxes if cb.value]

def get_default_doses_str(stressors):
    # Default doses for common stressors
    defaults = {
        'Tunicamycin': 10.0,
        'Thapsigargin': 2.0,
        'CCCP': 20.0,
        'MG-132': 5.0,
        '2-DG': 5000.0,
        'Oligomycin A': 10.0,
        'Brefeldin A': 10.0,
        'tBHQ': 50.0,
        'H2O2': 500.0,
        'Etoposide': 50.0,
        'Nocodazole': 10.0,
        'Rigosertib': 1.0,
        'Trichostatin A': 10.0
    }
    return ", ".join([str(defaults.get(s, 10.0)) for s in stressors])

def get_default_seeding_str(cell_lines):
    import os
    import csv
    
    # Path relative to this script: ../data/cell_seeding_densities.csv
    # But we should try to find it robustly
    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(script_dir, "..", "data", "cell_seeding_densities.csv")
    
    densities = {}
    try:
        if os.path.exists(csv_path):
            with open(csv_path, mode='r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    cl = row.get('Cell Line')
                    density = row.get('Target Cells/Well')
                    if cl and density:
                        densities[cl] = density
    except Exception as e:
        print(f"Warning: Could not load seeding densities from {csv_path}: {e}")
    
    return ", ".join([str(densities.get(cl, "5000")) for cl in cell_lines])
