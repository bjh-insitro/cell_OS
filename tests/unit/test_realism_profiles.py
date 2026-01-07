"""
Tests for realism profiles (Issue #8).

Tests that:
1. ER-mito coupling profile computes correct factors
2. Disabled coupling returns factor of 1.0
3. Sigmoid shape matches expected behavior
4. Profile presets have correct values
"""

import pytest
import numpy as np

from cell_os.hardware.realism_profiles import (
    ERMitoCouplingProfile,
    RealismProfile,
    DEFAULT_ER_MITO_COUPLING,
    REALISTIC_ER_MITO_COUPLING,
    IDENTIFIABLE_ER_MITO_COUPLING,
    WEAK_ER_MITO_COUPLING,
    DEFAULT_PROFILE,
    REALISTIC_PROFILE,
    IDENTIFIABLE_PROFILE,
)


class TestERMitoCouplingProfile:
    """Test ER-mito coupling profile."""

    def test_disabled_returns_unity(self):
        """Disabled coupling returns factor of 1.0."""
        profile = ERMitoCouplingProfile(enabled=False)

        assert profile.coupling_factor(0.0) == 1.0
        assert profile.coupling_factor(0.5) == 1.0
        assert profile.coupling_factor(1.0) == 1.0

    def test_zero_damage_minimal_coupling(self):
        """Zero ER damage gives minimal coupling."""
        profile = DEFAULT_ER_MITO_COUPLING

        factor = profile.coupling_factor(0.0)
        # At damage=0 with d0=0.3, sigmoid(-0.3*8) ≈ 0.08, factor ≈ 1.25
        # This is sub-maximal coupling
        assert factor < 1.0 + profile.coupling_k / 2  # Less than half max

    def test_high_damage_strong_coupling(self):
        """High ER damage gives strong coupling."""
        profile = DEFAULT_ER_MITO_COUPLING

        factor = profile.coupling_factor(1.0)
        # At damage=1, sigmoid is near 1, so factor ≈ 1 + k
        assert factor > 1.0 + profile.coupling_k * 0.9

    def test_midpoint_half_coupling(self):
        """At midpoint (d0), coupling is approximately half."""
        profile = DEFAULT_ER_MITO_COUPLING

        factor = profile.coupling_factor(profile.coupling_d0)
        # At midpoint, sigmoid = 0.5, so factor ≈ 1 + k/2
        expected = 1.0 + profile.coupling_k * 0.5
        assert abs(factor - expected) < 0.1

    def test_monotonic_increase(self):
        """Coupling factor increases monotonically with damage."""
        profile = DEFAULT_ER_MITO_COUPLING

        damages = np.linspace(0, 1, 11)
        factors = [profile.coupling_factor(d) for d in damages]

        # Each factor should be >= previous
        for i in range(1, len(factors)):
            assert factors[i] >= factors[i-1], f"Non-monotonic at damage={damages[i]}"

    def test_to_dict_serialization(self):
        """Profile serializes to dict."""
        d = DEFAULT_ER_MITO_COUPLING.to_dict()

        assert "enabled" in d
        assert d["enabled"] is True
        assert d["coupling_k"] == 3.0


class TestRealismProfilePresets:
    """Test preset profiles."""

    def test_identifiable_no_coupling(self):
        """Identifiable profile has no coupling."""
        assert IDENTIFIABLE_ER_MITO_COUPLING.enabled is False
        assert IDENTIFIABLE_ER_MITO_COUPLING.coupling_factor(1.0) == 1.0

    def test_realistic_stronger_coupling(self):
        """Realistic profile has stronger coupling than default."""
        default_factor = DEFAULT_ER_MITO_COUPLING.coupling_factor(1.0)
        realistic_factor = REALISTIC_ER_MITO_COUPLING.coupling_factor(1.0)

        assert realistic_factor > default_factor

    def test_weak_weaker_coupling(self):
        """Weak profile has weaker coupling than default."""
        default_factor = DEFAULT_ER_MITO_COUPLING.coupling_factor(0.5)
        weak_factor = WEAK_ER_MITO_COUPLING.coupling_factor(0.5)

        assert weak_factor < default_factor

    def test_profiles_immutable(self):
        """Profiles are frozen (immutable)."""
        with pytest.raises(AttributeError):
            DEFAULT_ER_MITO_COUPLING.coupling_k = 10.0


class TestRealismProfile:
    """Test top-level realism profile."""

    def test_profile_contains_coupling(self):
        """RealismProfile contains ER-mito coupling."""
        assert DEFAULT_PROFILE.er_mito_coupling is not None
        assert isinstance(DEFAULT_PROFILE.er_mito_coupling, ERMitoCouplingProfile)

    def test_profile_names(self):
        """Profile names are descriptive."""
        assert DEFAULT_PROFILE.name == "default"
        assert REALISTIC_PROFILE.name == "realistic"
        assert IDENTIFIABLE_PROFILE.name == "identifiable"

    def test_profile_to_dict(self):
        """Profile serializes to dict."""
        d = DEFAULT_PROFILE.to_dict()

        assert d["name"] == "default"
        assert "er_mito_coupling" in d


class TestCouplingBehavior:
    """Test coupling factor behavior across scenarios."""

    def test_early_damage_minimal_effect(self):
        """Early damage (< d0) has minimal coupling effect."""
        profile = DEFAULT_ER_MITO_COUPLING

        # Damage well below midpoint
        factor_low = profile.coupling_factor(0.1)
        factor_high = profile.coupling_factor(0.9)

        # Low damage should give less coupling than high damage
        assert factor_low < factor_high
        # Low damage should be less than max coupling
        assert factor_low < 1.0 + profile.coupling_k

    def test_late_damage_saturates(self):
        """Late damage saturates at max coupling."""
        profile = DEFAULT_ER_MITO_COUPLING

        factor_09 = profile.coupling_factor(0.9)
        factor_10 = profile.coupling_factor(1.0)

        # Should be nearly the same (saturation)
        assert abs(factor_10 - factor_09) < 0.1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
