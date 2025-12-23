"""
Pytest configuration for cell_OS tests.
"""
import sys
import os
import pytest

# Add src directory to Python path so tests can import cell_os modules
src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../src"))
sys.path.insert(0, src_path)


# ==============================================================================
# Seeding Density Fixtures
# ==============================================================================

@pytest.fixture
def seeding_repository():
    """Get seeding density repository for database lookups."""
    from cell_os.database.repositories.seeding_density import SeedingDensityRepository
    return SeedingDensityRepository()


@pytest.fixture
def seed_384_well_a549():
    """Standard seeding density for A549 in 384-well plates."""
    from cell_os.database.repositories.seeding_density import get_cells_to_seed
    return get_cells_to_seed("A549", "384-well", "NOMINAL")


@pytest.fixture
def seed_384_well_hepg2():
    """Standard seeding density for HepG2 in 384-well plates."""
    from cell_os.database.repositories.seeding_density import get_cells_to_seed
    return get_cells_to_seed("HepG2", "384-well", "NOMINAL")


@pytest.fixture
def seed_96_well_a549():
    """Standard seeding density for A549 in 96-well plates."""
    from cell_os.database.repositories.seeding_density import get_cells_to_seed
    return get_cells_to_seed("A549", "96-well", "NOMINAL")


@pytest.fixture
def seed_96_well_hepg2():
    """Standard seeding density for HepG2 in 96-well plates."""
    from cell_os.database.repositories.seeding_density import get_cells_to_seed
    return get_cells_to_seed("HepG2", "96-well", "NOMINAL")


@pytest.fixture
def seed_t75_a549():
    """Standard seeding density for A549 in T75 flasks."""
    from cell_os.database.repositories.seeding_density import get_cells_to_seed
    return get_cells_to_seed("A549", "T75", "NOMINAL")


@pytest.fixture
def seed_t75_hepg2():
    """Standard seeding density for HepG2 in T75 flasks."""
    from cell_os.database.repositories.seeding_density import get_cells_to_seed
    return get_cells_to_seed("HepG2", "T75", "NOMINAL")


@pytest.fixture
def get_seeding_density():
    """
    Convenience fixture that returns the get_cells_to_seed function.

    Usage in tests:
        def test_something(get_seeding_density):
            cells = get_seeding_density("A549", "384-well", "NOMINAL")
            assert cells == 3000
    """
    from cell_os.database.repositories.seeding_density import get_cells_to_seed
    return get_cells_to_seed
