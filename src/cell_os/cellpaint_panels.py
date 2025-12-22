"""
Modular Cell Painting Panel System

Defines flexible, composable Cell Painting panels for different cell types and applications.
Panels can be used in POSH workflows or standalone immunofluorescence.

Design principles:
1. Core organelle markers (nucleus, ER, actin, Golgi, mito)
2. Specialized markers for cell types (neurons, hepatocytes, adipocytes, etc.)
3. Disease-specific markers (ALS, etc.)
4. Mix and match components
5. Automatic secondary antibody selection based on primary species
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from enum import Enum

class MarkerType(Enum):
    """Type of marker."""
    DYE = "dye"
    ANTIBODY_PRIMARY = "antibody_primary"
    ANTIBODY_SECONDARY = "antibody_secondary"
    FISH_PROBE = "fish_probe"

class Organelle(Enum):
    """Cellular organelle or structure."""
    NUCLEUS = "nucleus"
    ER = "endoplasmic_reticulum"
    GOLGI = "golgi"
    ACTIN = "actin"
    MITOCHONDRIA = "mitochondria"
    PLASMA_MEMBRANE = "plasma_membrane"
    LIPID_DROPLETS = "lipid_droplets"
    LYSOSOMES = "lysosomes"
    PEROXISOMES = "peroxisomes"
    MICROTUBULES = "microtubules"
    STRESS_GRANULES = "stress_granules"
    CUSTOM = "custom"

@dataclass
class CellPaintMarker:
    """Single marker in a Cell Painting panel."""
    name: str
    marker_type: MarkerType
    target: str  # What it stains (e.g., "DNA", "F-actin", "MAP2")
    organelle: Organelle
    fluorophore: str  # e.g., "Hoechst", "Alexa488", "Cy5"
    channel: str  # e.g., "DAPI", "FITC", "Cy5"
    species: Optional[str] = None  # For antibodies: "rabbit", "chicken", "mouse"
    concentration: Optional[float] = None  # Working concentration
    concentration_unit: Optional[str] = None  # "µg/mL", "µM", "units"
    vendor: Optional[str] = None
    catalog: Optional[str] = None
    notes: Optional[str] = None
    
    def requires_secondary(self) -> bool:
        """Check if this marker requires a secondary antibody."""
        return self.marker_type == MarkerType.ANTIBODY_PRIMARY
    
    def get_secondary_species(self) -> Optional[str]:
        """Get the species for secondary antibody selection."""
        if self.requires_secondary():
            return self.species
        return None

@dataclass
class CellPaintPanel:
    """Complete Cell Painting panel."""
    name: str
    description: str
    markers: List[CellPaintMarker]
    cell_types: List[str]  # Recommended cell types
    compatible_with_posh: bool = True
    notes: Optional[str] = None
    
    def get_channels(self) -> List[str]:
        """Get list of imaging channels needed."""
        return list(set([m.channel for m in self.markers]))
    
    def get_primary_antibodies(self) -> List[CellPaintMarker]:
        """Get all primary antibodies."""
        return [m for m in self.markers if m.marker_type == MarkerType.ANTIBODY_PRIMARY]
    
    def get_required_secondaries(self) -> Dict[str, str]:
        """Get required secondary antibodies by species."""
        primaries = self.get_primary_antibodies()
        species_to_fluorophore = {}
        for p in primaries:
            if p.species:
                species_to_fluorophore[p.species] = p.fluorophore
        return species_to_fluorophore
    
    def get_dyes(self) -> List[CellPaintMarker]:
        """Get all dyes."""
        return [m for m in self.markers if m.marker_type == MarkerType.DYE]
    
    def num_channels(self) -> int:
        """Get number of imaging channels."""
        return len(self.get_channels())


# ===================================================================
# CORE CELL PAINT PANELS
# ===================================================================

def get_core_cellpaint_panel() -> CellPaintPanel:
    """
    Core Cell Painting panel (5-channel).
    
    Standard organelle markers suitable for most cell types.
    Based on Carpenter lab's original Cell Painting protocol.
    """
    markers = [
        CellPaintMarker(
            name="Hoechst 33342",
            marker_type=MarkerType.DYE,
            target="DNA",
            organelle=Organelle.NUCLEUS,
            fluorophore="Hoechst",
            channel="DAPI",
            concentration=1.0,
            concentration_unit="µg/mL",
            vendor="ThermoFisher",
            catalog="33342"
        ),
        CellPaintMarker(
            name="Concanavalin A Alexa 488",
            marker_type=MarkerType.DYE,
            target="Mannose/Glucose residues (ER)",
            organelle=Organelle.ER,
            fluorophore="Alexa488",
            channel="FITC",
            concentration=12.5,
            concentration_unit="µg/mL",
            vendor="Invitrogen",
            catalog="C11252"
        ),
        CellPaintMarker(
            name="Phalloidin 568",
            marker_type=MarkerType.DYE,
            target="F-actin",
            organelle=Organelle.ACTIN,
            fluorophore="Alexa568",
            channel="TRITC",
            concentration=0.33,
            concentration_unit="µM",
            vendor="Invitrogen",
            catalog="A12380"
        ),
        CellPaintMarker(
            name="WGA Alexa 555",
            marker_type=MarkerType.DYE,
            target="Sialic acid/N-acetylglucosamine (Golgi/PM)",
            organelle=Organelle.GOLGI,
            fluorophore="Alexa555",
            channel="Cy3",
            concentration=1.5,
            concentration_unit="µg/mL",
            vendor="Invitrogen",
            catalog="W32464"
        ),
        CellPaintMarker(
            name="MitoTracker Deep Red",
            marker_type=MarkerType.DYE,
            target="Mitochondria",
            organelle=Organelle.MITOCHONDRIA,
            fluorophore="DeepRed",
            channel="Cy5",
            concentration=0.5,
            concentration_unit="µM",
            vendor="Invitrogen",
            catalog="M22426"
        ),
    ]
    
    return CellPaintPanel(
        name="Core CellPaint (5-channel)",
        description="Standard Cell Painting with 5 organelle markers",
        markers=markers,
        cell_types=["all"],
        compatible_with_posh=True
    )


def get_posh_cellpaint_panel(include_mitoprobe: bool = True) -> CellPaintPanel:
    """
    POSH-compatible Cell Painting panel (5-6 channel).
    
    Uses ISS-compatible dyes and MitoProbe instead of MitoTracker.
    """
    markers = [
        CellPaintMarker(
            name="Hoechst 33342",
            marker_type=MarkerType.DYE,
            target="DNA",
            organelle=Organelle.NUCLEUS,
            fluorophore="Hoechst",
            channel="DAPI",
            concentration=0.5,
            concentration_unit="µg/mL",
            vendor="ThermoFisher",
            catalog="33342"
        ),
        CellPaintMarker(
            name="Concanavalin A Alexa 488",
            marker_type=MarkerType.DYE,
            target="ER",
            organelle=Organelle.ER,
            fluorophore="Alexa488",
            channel="FITC",
            concentration=12.5,
            concentration_unit="µg/mL",
            vendor="Invitrogen",
            catalog="C11252"
        ),
        CellPaintMarker(
            name="WGA Alexa 555",
            marker_type=MarkerType.DYE,
            target="Golgi/Membrane",
            organelle=Organelle.GOLGI,
            fluorophore="Alexa555",
            channel="Cy3",
            concentration=1.5,
            concentration_unit="µg/mL",
            vendor="Invitrogen",
            catalog="W32464"
        ),
        CellPaintMarker(
            name="Phalloidin 568",
            marker_type=MarkerType.DYE,
            target="F-actin",
            organelle=Organelle.ACTIN,
            fluorophore="Alexa568",
            channel="TRITC",
            concentration=0.33,
            concentration_unit="µM",
            vendor="Invitrogen",
            catalog="A12380"
        ),
    ]
    
    if include_mitoprobe:
        # MitoProbe (FISH-based, ISS-compatible)
        markers.extend([
            CellPaintMarker(
                name="MitoProbe 12S Cy5",
                marker_type=MarkerType.FISH_PROBE,
                target="Mitochondrial 12S rRNA",
                organelle=Organelle.MITOCHONDRIA,
                fluorophore="Cy5",
                channel="Cy5",
                concentration=0.25,
                concentration_unit="µM",
                vendor="IDT",
                catalog="custom",
                notes="Sequence: /5Cy5/CTC TAT ATA AAT GCG TAG GG"
            ),
            CellPaintMarker(
                name="MitoProbe 16S Cy5",
                marker_type=MarkerType.FISH_PROBE,
                target="Mitochondrial 16S rRNA",
                organelle=Organelle.MITOCHONDRIA,
                fluorophore="Cy5",
                channel="Cy5",
                concentration=0.25,
                concentration_unit="µM",
                vendor="IDT",
                catalog="custom",
                notes="Sequence: /5Cy5/TAC TGT TTG CAT TAA TAA ATT AA"
            ),
        ])
    
    return CellPaintPanel(
        name=f"POSH CellPaint ({'6' if include_mitoprobe else '5'}-channel)",
        description="ISS-compatible Cell Painting for POSH",
        markers=markers,
        cell_types=["all"],
        compatible_with_posh=True,
        notes="Uses MitoProbe instead of MitoTracker for ISS compatibility"
    )


# ===================================================================
# SPECIALIZED PANELS
# ===================================================================

def get_neuropaint_panel() -> CellPaintPanel:
    """
    NeuroPaint panel for neurons and neural cells.
    
    Adds neuron-specific markers (MAP2, TUJ1) to core panel.
    """
    # Start with core markers
    core = get_core_cellpaint_panel()
    markers = core.markers.copy()
    
    # Add neuron-specific markers
    markers.extend([
        CellPaintMarker(
            name="MAP2 (Chicken)",
            marker_type=MarkerType.ANTIBODY_PRIMARY,
            target="Microtubule-associated protein 2 (dendrites)",
            organelle=Organelle.MICROTUBULES,
            fluorophore="Alexa647",  # Via secondary
            channel="Cy5",
            species="chicken",
            concentration=1.0,
            concentration_unit="µg/mL",
            vendor="NOVUS",
            catalog="NB300-213",
            notes="Dendritic marker, requires anti-chicken secondary"
        ),
        # TUJ1 could be added as alternative/additional marker
    ])
    
    return CellPaintPanel(
        name="NeuroPaint (6-channel)",
        description="Cell Painting optimized for neurons with MAP2",
        markers=markers,
        cell_types=["neurons", "iPSC-neurons", "neural_progenitors"],
        compatible_with_posh=True
    )


def get_hepatopaint_panel() -> CellPaintPanel:
    """
    HepatoPaint panel for hepatocytes.
    
    Adds lipid droplet marker (BODIPY) for hepatocyte/adipocyte biology.
    """
    core = get_core_cellpaint_panel()
    markers = core.markers.copy()
    
    # Add hepatocyte-specific markers
    markers.append(
        CellPaintMarker(
            name="BODIPY 493/503",
            marker_type=MarkerType.DYE,
            target="Neutral lipids (lipid droplets)",
            organelle=Organelle.LIPID_DROPLETS,
            fluorophore="BODIPY",
            channel="FITC",
            concentration=1.0,
            concentration_unit="µg/mL",
            vendor="Invitrogen",
            catalog="D3922",
            notes="Lipid droplet marker for hepatocytes/adipocytes"
        )
    )
    
    return CellPaintPanel(
        name="HepatoPaint (6-channel)",
        description="Cell Painting for hepatocytes with lipid droplet marker",
        markers=markers,
        cell_types=["hepatocytes", "adipocytes", "HepG2"],
        compatible_with_posh=True
    )


def get_als_paint_panel() -> CellPaintPanel:
    """
    ALSPaint panel for ALS disease modeling.
    
    Includes TDP-43 and STMN2 markers for ALS-relevant phenotypes.
    """
    neuro = get_neuropaint_panel()
    markers = neuro.markers.copy()
    
    # Add ALS-specific markers
    markers.extend([
        CellPaintMarker(
            name="TDP-43 (Rabbit)",
            marker_type=MarkerType.ANTIBODY_PRIMARY,
            target="TDP-43 protein (stress granules, mislocalization)",
            organelle=Organelle.STRESS_GRANULES,
            fluorophore="DyLight755",  # Via secondary
            channel="Cy7",
            species="rabbit",
            concentration=1.0,
            concentration_unit="µg/mL",
            vendor="Proteintech",
            catalog="10782-2-AP",
            notes="ALS marker, nuclear vs cytoplasmic localization"
        ),
        CellPaintMarker(
            name="STMN2 (Rabbit)",
            marker_type=MarkerType.ANTIBODY_PRIMARY,
            target="Stathmin-2 protein",
            organelle=Organelle.CUSTOM,
            fluorophore="Alexa594",  # Via secondary
            channel="TRITC",
            species="rabbit",
            concentration=1.0,
            concentration_unit="µg/mL",
            vendor="Novus",
            catalog="NBP2-49461",
            notes="ALS biomarker, can also use FISH for full-length vs cryptic exon"
        ),
    ])
    
    return CellPaintPanel(
        name="ALSPaint (8-channel)",
        description="Cell Painting for ALS with TDP-43 and STMN2",
        markers=markers,
        cell_types=["motor_neurons", "iPSC-neurons", "ALS_models"],
        compatible_with_posh=True,
        notes="Can add STMN2 FISH probes for splice variant detection"
    )


# ===================================================================
# SECONDARY ANTIBODY LIBRARY
# ===================================================================

SECONDARY_ANTIBODIES = {
    ("chicken", "Alexa488"): {
        "name": "Alexa Fluor 488 goat anti-chicken IgG (H+L)",
        "vendor": "Invitrogen",
        "catalog": "A11039",
        "concentration": 2.0,
        "concentration_unit": "mg/mL",
    },
    ("rabbit", "Alexa594"): {
        "name": "Alexa Fluor 594 goat anti-rabbit IgG (H+L)",
        "vendor": "Invitrogen",
        "catalog": "A11012",
        "concentration": 2.0,
        "concentration_unit": "mg/mL",
    },
    ("rabbit", "Alexa647"): {
        "name": "Alexa Fluor 647 goat anti-rabbit IgG (H+L)",
        "vendor": "Invitrogen",
        "catalog": "A21244",
        "concentration": 2.0,
        "concentration_unit": "mg/mL",
    },
    ("rabbit", "DyLight755"): {
        "name": "DyLight 755 Donkey Anti-Rabbit IgG (H+L)",
        "vendor": "Invitrogen",
        "catalog": "SA5-10043",
        "concentration": None,
        "concentration_unit": None,
        "notes": "CrossAdsorbed"
    },
    ("mouse", "Alexa488"): {
        "name": "Alexa Fluor 488 goat anti-mouse IgG (H+L)",
        "vendor": "Invitrogen",
        "catalog": "A11001",
        "concentration": 2.0,
        "concentration_unit": "mg/mL",
    },
    ("mouse", "Alexa647"): {
        "name": "Alexa Fluor 647 goat anti-mouse IgG (H+L)",
        "vendor": "Invitrogen",
        "catalog": "A21235",
        "concentration": 2.0,
        "concentration_unit": "mg/mL",
    },
}

def get_secondary_antibody(species: str, fluorophore: str) -> Optional[Dict]:
    """Get secondary antibody info for a given species and fluorophore."""
    return SECONDARY_ANTIBODIES.get((species.lower(), fluorophore))


def get_panel_cost(panel_name: str, volume_ml: float) -> float:
    """
    Calculate cost for a Cell Painting panel based on volume.

    Uses VERIFIED vendor pricing from inventory database (ThermoFisher, Dec 2024).
    Costs are calculated per well (50 µL) from working concentrations.

    Args:
        panel_name: Name of the marker/panel (e.g., "mitotracker", "core", "posh")
        volume_ml: Volume in mL

    Returns:
        Cost in USD based on verified pricing
    """
    # VERIFIED cost per well (50 µL) from ThermoFisher pricing + Broad protocol
    # All prices verified Dec 2024, calculated with proper dilutions
    cost_per_well_50ul = {
        "mitotracker": 0.007,      # MitoTracker Deep Red FM (M22426)
        "hoechst": 0.00006,        # Hoechst 33342 (H3570) - negligible
        "concanavalin": 0.026,     # ConA-Alexa488 (C11252)
        "phalloidin": 0.902,       # Phalloidin-568 (A12380) - EXPENSIVE!
        "wga": 0.006,              # WGA-Alexa555 (W32464)

        # Composite panels (sum of components)
        "core": 0.941,             # 5-channel: Hoechst + ConA + Phalloidin + WGA + Mito
        "standard_cocktail": 0.935, # 4-channel post-fix: Hoechst + ConA + Phalloidin + WGA

        # Other panels (approximations pending verification)
        "mitoprobe": 1.50,         # Custom FISH probes (not verified)
        "bodipy": 0.20,            # BODIPY 493/503 (not verified)
        "posh": 2.00,              # POSH panel with MitoProbe (not verified)
        "neuropaint": 2.50,        # NeuroPaint with antibodies (not verified)
        "hepatopaint": 1.70,       # HepatoPaint (not verified)
        "alspaint": 3.50,          # ALSPaint with multiple antibodies (not verified)
    }

    # Convert volume_ml to number of 50 µL wells
    # 1 mL = 1000 µL = 20 wells of 50 µL each
    wells_per_ml = 20.0
    n_wells = volume_ml * wells_per_ml

    # Get cost per well, default to $1/mL if unknown
    cost_per_well = cost_per_well_50ul.get(panel_name.lower(), 1.0 / wells_per_ml)

    return cost_per_well * n_wells



# ===================================================================
# PANEL BUILDER
# ===================================================================

class CellPaintPanelBuilder:
    """Builder for custom Cell Painting panels."""
    
    def __init__(self, base_panel: Optional[CellPaintPanel] = None):
        """Initialize with optional base panel."""
        if base_panel:
            self.markers = base_panel.markers.copy()
            self.name = f"{base_panel.name} (custom)"
            self.cell_types = base_panel.cell_types.copy()
        else:
            self.markers = []
            self.name = "Custom CellPaint"
            self.cell_types = []
    
    def add_marker(self, marker: CellPaintMarker) -> 'CellPaintPanelBuilder':
        """Add a marker to the panel."""
        self.markers.append(marker)
        return self
    
    def remove_marker(self, marker_name: str) -> 'CellPaintPanelBuilder':
        """Remove a marker by name."""
        self.markers = [m for m in self.markers if m.name != marker_name]
        return self
    
    def replace_marker(self, old_name: str, new_marker: CellPaintMarker) -> 'CellPaintPanelBuilder':
        """Replace a marker."""
        self.remove_marker(old_name)
        self.add_marker(new_marker)
        return self
    
    def build(self) -> CellPaintPanel:
        """Build the final panel."""
        return CellPaintPanel(
            name=self.name,
            description="Custom Cell Painting panel",
            markers=self.markers,
            cell_types=self.cell_types,
            compatible_with_posh=True
        )


# ===================================================================
# EXAMPLE USAGE
# ===================================================================

if __name__ == "__main__":
    print("=" * 80)
    print("MODULAR CELL PAINTING PANEL SYSTEM")
    print("=" * 80)
    
    # Example 1: Core CellPaint
    print("\n[1] Core CellPaint Panel")
    core = get_core_cellpaint_panel()
    print(f"  Name: {core.name}")
    print(f"  Channels: {core.num_channels()}")
    print(f"  Markers:")
    for m in core.markers:
        print(f"    - {m.name} ({m.channel}): {m.target}")
    
    # Example 2: POSH CellPaint
    print("\n[2] POSH CellPaint Panel (with MitoProbe)")
    posh = get_posh_cellpaint_panel(include_mitoprobe=True)
    print(f"  Name: {posh.name}")
    print(f"  Channels: {posh.num_channels()}")
    print(f"  FISH probes: {len([m for m in posh.markers if m.marker_type == MarkerType.FISH_PROBE])}")
    
    # Example 3: NeuroPaint
    print("\n[3] NeuroPaint Panel")
    neuro = get_neuropaint_panel()
    print(f"  Name: {neuro.name}")
    print(f"  Channels: {neuro.num_channels()}")
    print(f"  Primary antibodies:")
    for ab in neuro.get_primary_antibodies():
        print(f"    - {ab.name} ({ab.species}) → {ab.fluorophore}")
    print(f"  Required secondaries:")
    for species, fluor in neuro.get_required_secondaries().items():
        sec = get_secondary_antibody(species, fluor)
        if sec:
            print(f"    - {sec['name']} ({sec['catalog']})")
    
    # Example 4: ALSPaint
    print("\n[4] ALSPaint Panel")
    als = get_als_paint_panel()
    print(f"  Name: {als.name}")
    print(f"  Channels: {als.num_channels()}")
    print(f"  Cell types: {', '.join(als.cell_types)}")
    
    # Example 5: Custom panel using builder
    print("\n[5] Custom Panel (Core + BODIPY)")
    builder = CellPaintPanelBuilder(base_panel=get_core_cellpaint_panel())
    builder.add_marker(
        CellPaintMarker(
            name="BODIPY 493/503",
            marker_type=MarkerType.DYE,
            target="Lipid droplets",
            organelle=Organelle.LIPID_DROPLETS,
            fluorophore="BODIPY",
            channel="FITC",
            concentration=1.0,
            concentration_unit="µg/mL",
            vendor="Invitrogen",
            catalog="D3922"
        )
    )
    custom = builder.build()
    print(f"  Name: {custom.name}")
    print(f"  Channels: {custom.num_channels()}")
    
    print("\n" + "=" * 80)
