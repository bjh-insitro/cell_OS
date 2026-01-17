"""
Biomarker registry - maps stress axes to relevant supplemental IF markers.

This registry determines which biomarkers are relevant for which stress contexts.
It enables the simulation to automatically suggest or include appropriate
supplemental channels based on the experimental design.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .gamma_h2ax import GammaH2AXModel


@dataclass
class BiomarkerInfo:
    """Information about a biomarker."""

    name: str
    marker_id: str
    description: str
    stress_axes: list[str]  # Which stress axes this marker is relevant for
    channel_name: str  # e.g., "AF488" for γ-H2AX
    stain_type: str  # "antibody", "dye", "probe"
    target: str  # What it binds to


# Registry of all available biomarkers
BIOMARKER_REGISTRY: dict[str, BiomarkerInfo] = {
    "gamma_h2ax": BiomarkerInfo(
        name="γ-H2AX",
        marker_id="gamma_h2ax",
        description="Phosphorylated histone H2AX - marker of DNA double-strand breaks",
        stress_axes=["dna_damage", "oxidative"],  # Oxidative stress causes DSBs
        channel_name="AF488",
        stain_type="antibody",
        target="Phospho-Histone H2A.X (Ser139)",
    ),
    # Future biomarkers can be added here:
    # "lc3": BiomarkerInfo(
    #     name="LC3",
    #     marker_id="lc3",
    #     description="Microtubule-associated protein light chain 3 - autophagy marker",
    #     stress_axes=["er_stress", "mitochondrial", "nutrient_depletion"],
    #     channel_name="AF555",
    #     stain_type="antibody",
    #     target="LC3B"
    # ),
    # "cleaved_caspase3": BiomarkerInfo(
    #     name="Cleaved Caspase-3",
    #     marker_id="cleaved_caspase3",
    #     description="Activated caspase-3 - marker of apoptosis",
    #     stress_axes=["dna_damage", "er_stress", "mitochondrial"],
    #     channel_name="AF647",
    #     stain_type="antibody",
    #     target="Cleaved Caspase-3 (Asp175)"
    # ),
}


class BiomarkerRegistry:
    """
    Registry for biomarker models.

    Provides:
    - Lookup of biomarkers by ID or stress axis
    - Factory method to instantiate biomarker models
    - Validation of biomarker configurations
    """

    def __init__(self):
        """Initialize the registry with available biomarkers."""
        self._models: dict[str, object] = {}

    @staticmethod
    def get_biomarker_info(marker_id: str) -> BiomarkerInfo | None:
        """Get information about a biomarker."""
        return BIOMARKER_REGISTRY.get(marker_id)

    @staticmethod
    def get_biomarkers_for_stress_axis(stress_axis: str) -> list[BiomarkerInfo]:
        """Get all biomarkers relevant for a given stress axis."""
        return [info for info in BIOMARKER_REGISTRY.values() if stress_axis in info.stress_axes]

    @staticmethod
    def list_all_biomarkers() -> list[str]:
        """List all available biomarker IDs."""
        return list(BIOMARKER_REGISTRY.keys())

    def get_model(self, marker_id: str) -> object | None:
        """
        Get or create a biomarker model instance.

        Args:
            marker_id: Biomarker identifier (e.g., "gamma_h2ax")

        Returns:
            Biomarker model instance or None if not found
        """
        if marker_id not in BIOMARKER_REGISTRY:
            return None

        if marker_id not in self._models:
            # Lazy instantiation
            if marker_id == "gamma_h2ax":
                from .gamma_h2ax import GammaH2AXModel

                self._models[marker_id] = GammaH2AXModel()
            # Add more model instantiations as they're implemented

        return self._models.get(marker_id)

    @staticmethod
    def suggest_biomarkers_for_compounds(compounds: list[str], compound_params: dict) -> list[str]:
        """
        Suggest relevant biomarkers based on compound stress axes.

        Args:
            compounds: List of compound names
            compound_params: Dict mapping compound name to params (with stress_axis)

        Returns:
            List of suggested biomarker IDs
        """
        stress_axes = set()
        for compound in compounds:
            params = compound_params.get(compound, {})
            axis = params.get("stress_axis")
            if axis:
                stress_axes.add(axis)

        suggested = set()
        for axis in stress_axes:
            for info in BIOMARKER_REGISTRY.values():
                if axis in info.stress_axes:
                    suggested.add(info.marker_id)

        return list(suggested)
