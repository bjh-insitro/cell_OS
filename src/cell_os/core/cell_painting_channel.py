"""
Cell Painting channel identities.

Channels are NOT feature names. They are identities.
Features (intensity, texture, etc.) are projections of channel identity.

This enum is the single source of truth for what channels exist.
All legacy string variants must be normalized through from_string().
"""

from enum import Enum
from typing import Optional


class CellPaintingChannel(Enum):
    """Canonical Cell Painting channel identities.

    Cell Painting uses five fluorescent channels to measure distinct
    cellular compartments. Each channel has:
    - Canonical internal name (enum value)
    - Display name for human-readable output
    - Normalization map via from_string() to handle legacy variants

    Channels are identities, not features.
    Features (intensity, texture, etc.) are computed FROM channels.
    """

    # Five standard Cell Painting channels
    NUCLEUS = "nucleus"
    ER = "er"
    MITO = "mito"
    ACTIN = "actin"
    AGP = "agp"

    @property
    def display_name(self) -> str:
        """Human-readable display name with biological context."""
        _DISPLAY_NAMES = {
            CellPaintingChannel.NUCLEUS: "DNA / Nucleus",
            CellPaintingChannel.ER: "Endoplasmic Reticulum",
            CellPaintingChannel.MITO: "Mitochondria",
            CellPaintingChannel.ACTIN: "Actin / Cytoskeleton",
            CellPaintingChannel.AGP: "Golgi / Plasma Membrane",
        }
        return _DISPLAY_NAMES[self]

    @property
    def short_name(self) -> str:
        """Short name for compact display (matches enum value)."""
        return self.value

    @classmethod
    def from_string(cls, s: str) -> "CellPaintingChannel":
        """Normalize legacy string variants to canonical CellPaintingChannel.

        This is the ONLY place where string normalization happens.
        All legacy code must go through this function.

        Args:
            s: Channel string (any legacy variant)

        Returns:
            Canonical CellPaintingChannel

        Raises:
            ValueError: If string doesn't match any known variant

        Normalization map (case-insensitive):
        - "nucleus", "DNA", "nuclei" → NUCLEUS
        - "er", "endoplasmic_reticulum", "ER" → ER
        - "mito", "mitochondria", "Mitochondria" → MITO
        - "actin", "Actin" → ACTIN
        - "agp", "golgi", "AGP" → AGP
        """
        # Normalize to lowercase for comparison
        s_lower = s.lower().strip()

        # Normalization table
        _NORMALIZATION_MAP = {
            # Nucleus / DNA variants
            "nucleus": cls.NUCLEUS,
            "dna": cls.NUCLEUS,
            "nuclei": cls.NUCLEUS,
            # ER variants
            "er": cls.ER,
            "endoplasmic_reticulum": cls.ER,
            # Mitochondria variants
            "mito": cls.MITO,
            "mitochondria": cls.MITO,
            # Actin variants
            "actin": cls.ACTIN,
            # AGP / Golgi variants
            "agp": cls.AGP,
            "golgi": cls.AGP,
            "plasma_membrane": cls.AGP,
            # Legacy variant that appears in some code
            "rna": cls.AGP,  # Some code uses 'rna' to refer to AGP channel
        }

        if s_lower in _NORMALIZATION_MAP:
            return _NORMALIZATION_MAP[s_lower]

        # If not found, raise with helpful error
        valid_variants = list(_NORMALIZATION_MAP.keys())
        raise ValueError(
            f"Unknown Cell Painting channel: '{s}'. "
            f"Valid variants (case-insensitive): {valid_variants}"
        )

    @classmethod
    def try_from_string(cls, s: str) -> Optional["CellPaintingChannel"]:
        """Try to normalize string, return None if invalid.

        Use this when you want to handle unknown channels gracefully.
        """
        try:
            return cls.from_string(s)
        except ValueError:
            return None

    @classmethod
    def all_channels(cls) -> list["CellPaintingChannel"]:
        """Return all five channels in canonical order.

        Use this instead of hardcoding lists of channel strings.
        """
        return [cls.NUCLEUS, cls.ER, cls.MITO, cls.ACTIN, cls.AGP]

    def __str__(self) -> str:
        """String representation uses short name for compact output."""
        return self.short_name

    def __repr__(self) -> str:
        """Repr shows enum member name."""
        return f"CellPaintingChannel.{self.name}"
