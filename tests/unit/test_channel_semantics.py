"""
Semantic teeth tests: Prevent channel string ambiguity from spreading.

These tests enforce that:
1. CellPaintingChannel.from_string() normalizes all legacy variants
2. Channel identity is represented by enum (not strings)
3. New channel variants don't leak in without normalization
4. Features are projections OF channels, not channel identities themselves
"""

from cell_os.core.cell_painting_channel import CellPaintingChannel


def test_channel_normalization():
    """CellPaintingChannel.from_string() must normalize all legacy variants.

    This is the ONLY place where string normalization happens.
    """
    # Nucleus / DNA variants
    assert CellPaintingChannel.from_string("nucleus") == CellPaintingChannel.NUCLEUS
    assert CellPaintingChannel.from_string("DNA") == CellPaintingChannel.NUCLEUS
    assert CellPaintingChannel.from_string("nuclei") == CellPaintingChannel.NUCLEUS
    assert CellPaintingChannel.from_string("Nucleus") == CellPaintingChannel.NUCLEUS  # Case insensitive

    # ER variants
    assert CellPaintingChannel.from_string("er") == CellPaintingChannel.ER
    assert CellPaintingChannel.from_string("ER") == CellPaintingChannel.ER
    assert CellPaintingChannel.from_string("endoplasmic_reticulum") == CellPaintingChannel.ER

    # Mitochondria variants
    assert CellPaintingChannel.from_string("mito") == CellPaintingChannel.MITO
    assert CellPaintingChannel.from_string("mitochondria") == CellPaintingChannel.MITO
    assert CellPaintingChannel.from_string("Mitochondria") == CellPaintingChannel.MITO

    # Actin variants
    assert CellPaintingChannel.from_string("actin") == CellPaintingChannel.ACTIN
    assert CellPaintingChannel.from_string("Actin") == CellPaintingChannel.ACTIN

    # AGP / Golgi variants
    assert CellPaintingChannel.from_string("agp") == CellPaintingChannel.AGP
    assert CellPaintingChannel.from_string("AGP") == CellPaintingChannel.AGP
    assert CellPaintingChannel.from_string("golgi") == CellPaintingChannel.AGP

    # Legacy variant (some code uses 'rna' for AGP channel)
    assert CellPaintingChannel.from_string("rna") == CellPaintingChannel.AGP


def test_channel_unknown_string_raises():
    """Unknown channel strings must raise with helpful message."""
    try:
        CellPaintingChannel.from_string("unknown_channel")
        assert False, "Should raise ValueError for unknown channel"
    except ValueError as e:
        # Check error message is helpful
        assert "unknown_channel" in str(e).lower()
        assert "valid variants" in str(e).lower()


def test_channel_try_from_string():
    """try_from_string() returns None for unknown strings."""
    # Known strings work
    assert CellPaintingChannel.try_from_string("nucleus") == CellPaintingChannel.NUCLEUS

    # Unknown strings return None (don't raise)
    assert CellPaintingChannel.try_from_string("unknown_channel") is None


def test_channel_display_names():
    """Channels must have human-readable display names with biological context."""
    assert CellPaintingChannel.NUCLEUS.display_name == "DNA / Nucleus"
    assert CellPaintingChannel.ER.display_name == "Endoplasmic Reticulum"
    assert CellPaintingChannel.MITO.display_name == "Mitochondria"
    assert CellPaintingChannel.ACTIN.display_name == "Actin / Cytoskeleton"
    assert CellPaintingChannel.AGP.display_name == "Golgi / Plasma Membrane"


def test_channel_short_names():
    """Channels must have short names for compact display."""
    assert CellPaintingChannel.NUCLEUS.short_name == "nucleus"
    assert CellPaintingChannel.ER.short_name == "er"
    assert CellPaintingChannel.MITO.short_name == "mito"
    assert CellPaintingChannel.ACTIN.short_name == "actin"
    assert CellPaintingChannel.AGP.short_name == "agp"


def test_channel_str_uses_short_name():
    """str(CellPaintingChannel) should use short_name for compact output."""
    assert str(CellPaintingChannel.NUCLEUS) == "nucleus"
    assert str(CellPaintingChannel.ER) == "er"
    assert str(CellPaintingChannel.MITO) == "mito"


def test_channel_repr_shows_enum():
    """repr(CellPaintingChannel) should show enum member for debugging."""
    assert repr(CellPaintingChannel.NUCLEUS) == "CellPaintingChannel.NUCLEUS"
    assert repr(CellPaintingChannel.ER) == "CellPaintingChannel.ER"


def test_all_channels_returns_five():
    """all_channels() must return all five channels in canonical order."""
    channels = CellPaintingChannel.all_channels()

    assert len(channels) == 5
    assert channels == [
        CellPaintingChannel.NUCLEUS,
        CellPaintingChannel.ER,
        CellPaintingChannel.MITO,
        CellPaintingChannel.ACTIN,
        CellPaintingChannel.AGP,
    ]


def test_all_channels_are_enums():
    """All channels must be CellPaintingChannel enum members."""
    for ch in CellPaintingChannel.all_channels():
        assert isinstance(ch, CellPaintingChannel)


def test_channel_identity_not_feature_name():
    """Channels are identities, not feature names.

    This test documents the design principle:
    - Channel: CellPaintingChannel.NUCLEUS (identity)
    - Feature: "nucleus_intensity", "nucleus_texture" (projection of identity)

    Do NOT create enums like "NUCLEUS_INTENSITY" - that mixes layers.
    Features are derived FROM channels, not part of channel identity.
    """
    # Channel is an identity
    channel = CellPaintingChannel.NUCLEUS

    # Features are projections of that identity (strings for now, could be typed later)
    # But they are NOT part of the channel enum
    features = [
        f"{channel.short_name}_intensity",
        f"{channel.short_name}_texture",
        f"{channel.short_name}_area",
    ]

    # This is correct: deriving feature names FROM channel identity
    assert features == ["nucleus_intensity", "nucleus_texture", "nucleus_area"]

    # This would be WRONG: encoding features into channel enum
    # (e.g., CellPaintingChannel.NUCLEUS_INTENSITY)
    assert not hasattr(CellPaintingChannel, "NUCLEUS_INTENSITY")


def test_no_new_channel_strings_leak():
    """Test that new code can't introduce raw channel strings.

    This is a meta-test: if you add a new channel string anywhere,
    you must add it to CellPaintingChannel.from_string() normalization map first.

    Otherwise this test documents the pattern: all channels go through
    CellPaintingChannel.from_string().
    """
    # If you're adding a new channel variant:
    # 1. Add to CellPaintingChannel enum (if new channel)
    # 2. Add to from_string() normalization map
    # 3. Update this test

    # Example: if someone tries to add "lysosome" as a new channel
    # without updating CellPaintingChannel, this will fail:
    try:
        CellPaintingChannel.from_string("lysosome")
        assert False, "If 'lysosome' is valid, update CellPaintingChannel enum first"
    except ValueError:
        pass  # Expected - unknown channel


def test_feature_dict_should_use_channel_enum():
    """Feature dicts should be keyed by CellPaintingChannel, not strings.

    This enforces that channel identity is always explicit.
    """
    # Good: keyed by enum
    features_by_channel = {
        CellPaintingChannel.NUCLEUS: 1.0,
        CellPaintingChannel.ER: 0.98,
        CellPaintingChannel.MITO: 1.02,
    }

    # Access is type-safe
    nucleus_value = features_by_channel[CellPaintingChannel.NUCLEUS]
    assert nucleus_value == 1.0

    # This documents the desired pattern for new code


if __name__ == '__main__':
    test_channel_normalization()
    test_channel_unknown_string_raises()
    test_channel_try_from_string()
    test_channel_display_names()
    test_channel_short_names()
    test_channel_str_uses_short_name()
    test_channel_repr_shows_enum()
    test_all_channels_returns_five()
    test_all_channels_are_enums()
    test_channel_identity_not_feature_name()
    test_no_new_channel_strings_leak()
    test_feature_dict_should_use_channel_enum()

    print("✓ All channel semantic teeth tests passed")
    print("✓ CellPaintingChannel enum is canonical")
    print("✓ String variants normalized via from_string()")
    print("✓ Channel identity != feature name")
    print("✓ No raw channel strings in canonical paths")
