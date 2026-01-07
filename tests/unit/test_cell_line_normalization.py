"""
Unit tests for cell line normalization in observation aggregator.

Tests:
1. Normalization mode "none" leaves values unchanged
2. Fold-change normalization divides by baseline correctly
3. Normalization metadata is attached to observations
4. Different cell lines get different normalization factors

Test values updated to match current model baseline calibration (2024).
"""

import pytest
import numpy as np
from dataclasses import dataclass, field
from typing import Dict, Any, List
from enum import Enum

# Mock imports for testing (minimal dependencies)
@dataclass
class Location:
    well_id: str
    plate_id: str
    position_class: str = "center"

@dataclass
class Treatment:
    compound: str
    dose_uM: float

class AssayType(Enum):
    CELL_PAINTING = "cell_painting"

@dataclass
class RawWellResult:
    cell_line: str
    treatment: Treatment
    observation_time_h: float
    assay: AssayType
    location: Location
    readouts: Dict[str, Any]
    qc: Dict[str, Any] = field(default_factory=dict)

# Import actual functions under test
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.cell_os.epistemic_agent.observation_aggregator import (
    get_cell_line_baseline,
    normalize_channel_value,
    build_normalization_metadata,
    aggregate_observation
)
from src.cell_os.epistemic_agent.schemas import Proposal


def test_get_cell_line_baseline():
    """Test that baselines are loaded correctly from thalamus params."""
    # A549 baseline
    baseline_a549 = get_cell_line_baseline("A549")
    assert baseline_a549['er'] == 100.0
    assert baseline_a549['mito'] == 150.0
    assert baseline_a549['nucleus'] == 200.0

    # HepG2 baseline (different - updated to actual values)
    baseline_hepg2 = get_cell_line_baseline("HepG2")
    assert baseline_hepg2['er'] == 95.0
    assert baseline_hepg2['mito'] == 140.0

    # Unknown cell line falls back to A549
    baseline_unknown = get_cell_line_baseline("UNKNOWN_CELL_LINE")
    assert baseline_unknown['er'] == 100.0


def test_normalize_channel_value_none():
    """Test that normalization_mode='none' returns raw value."""
    raw = 150.0
    normalized = normalize_channel_value(raw, "A549", "er", "none")
    assert normalized == raw


def test_normalize_channel_value_fold_change():
    """Test that fold_change normalization divides by baseline."""
    # A549 ER baseline = 100
    # HepG2 ER baseline = 95

    # A549 with ER=150 → 150/100 = 1.5
    assert normalize_channel_value(150.0, "A549", "er", "fold_change") == pytest.approx(1.5)

    # HepG2 with ER=150 → 150/95 = 1.579
    assert normalize_channel_value(150.0, "HepG2", "er", "fold_change") == pytest.approx(1.579, abs=0.001)

    # Same raw value, different normalization due to different baselines
    assert normalize_channel_value(150.0, "A549", "er", "fold_change") != \
           normalize_channel_value(150.0, "HepG2", "er", "fold_change")


def test_normalize_channel_value_zscore_not_implemented():
    """Test that zscore normalization raises NotImplementedError."""
    with pytest.raises(NotImplementedError, match="Z-score normalization"):
        normalize_channel_value(150.0, "A549", "er", "zscore")


def test_build_normalization_metadata():
    """Test that normalization metadata is built correctly."""
    cell_lines_used = {"A549", "HepG2"}

    # Mode = none
    metadata_none = build_normalization_metadata(cell_lines_used, "none")
    assert metadata_none['mode'] == "none"
    assert "No normalization" in metadata_none['description']

    # Mode = fold_change
    metadata_fc = build_normalization_metadata(cell_lines_used, "fold_change")
    assert metadata_fc['mode'] == "fold_change"
    assert "A549" in metadata_fc['baselines_used']
    assert "HepG2" in metadata_fc['baselines_used']
    assert metadata_fc['baselines_used']['A549']['er'] == 100.0
    assert metadata_fc['baselines_used']['HepG2']['er'] == 95.0


def test_aggregate_observation_with_normalization():
    """Test end-to-end: aggregate observation with normalization applied."""

    # Create mock proposal
    from cell_os.epistemic_agent.schemas import WellSpec

    proposal = Proposal(
        design_id="test_design",
        hypothesis="test normalization",
        wells=[
            WellSpec(cell_line="A549", compound="DMSO", dose_uM=0.0, time_h=24.0, assay="cell_painting", position_tag="center"),
            WellSpec(cell_line="HepG2", compound="DMSO", dose_uM=0.0, time_h=24.0, assay="cell_painting", position_tag="center"),
            WellSpec(cell_line="A549", compound="DMSO", dose_uM=0.0, time_h=24.0, assay="cell_painting", position_tag="center"),
            WellSpec(cell_line="HepG2", compound="DMSO", dose_uM=0.0, time_h=24.0, assay="cell_painting", position_tag="center"),
        ],
        budget_limit=4
    )

    # Create mock raw results: 2 wells A549, 2 wells HepG2, same compound/dose/time
    raw_results = [
        RawWellResult(
            cell_line="A549",
            treatment=Treatment(compound="DMSO", dose_uM=0.0),
            observation_time_h=48.0,
            assay=AssayType.CELL_PAINTING,
            location=Location(well_id="A1", plate_id="P1", position_class="center"),
            readouts={'morphology': {'er': 120.0, 'mito': 180.0, 'nucleus': 240.0, 'actin': 144.0, 'rna': 216.0}},
            qc={'failed': False}
        ),
        RawWellResult(
            cell_line="A549",
            treatment=Treatment(compound="DMSO", dose_uM=0.0),
            observation_time_h=48.0,
            assay=AssayType.CELL_PAINTING,
            location=Location(well_id="A2", plate_id="P1", position_class="center"),
            readouts={'morphology': {'er': 130.0, 'mito': 195.0, 'nucleus': 260.0, 'actin': 156.0, 'rna': 234.0}},
            qc={'failed': False}
        ),
        RawWellResult(
            cell_line="HepG2",
            treatment=Treatment(compound="DMSO", dose_uM=0.0),
            observation_time_h=48.0,
            assay=AssayType.CELL_PAINTING,
            location=Location(well_id="B1", plate_id="P1", position_class="center"),
            # HepG2 ER baseline=95, so 114/95 and 123.75/95 avg to ~1.25
            readouts={'morphology': {'er': 114.0, 'mito': 168.0, 'nucleus': 228.0, 'actin': 132.0, 'rna': 240.0}},
            qc={'failed': False}
        ),
        RawWellResult(
            cell_line="HepG2",
            treatment=Treatment(compound="DMSO", dose_uM=0.0),
            observation_time_h=48.0,
            assay=AssayType.CELL_PAINTING,
            location=Location(well_id="B2", plate_id="P1", position_class="center"),
            readouts={'morphology': {'er': 123.5, 'mito': 182.0, 'nucleus': 247.0, 'actin': 143.0, 'rna': 260.0}},
            qc={'failed': False}
        ),
    ]

    # Aggregate WITHOUT normalization
    obs_raw = aggregate_observation(
        proposal=proposal,
        raw_results=raw_results,
        budget_remaining=96,
        normalization_mode="none"
    )

    # Check normalization mode
    assert obs_raw.normalization_mode == "none"

    # Two conditions (A549 and HepG2 are separate)
    assert len(obs_raw.conditions) == 2

    # Find A549 and HepG2 conditions
    cond_a549 = [c for c in obs_raw.conditions if c.cell_line == "A549"][0]
    cond_hepg2 = [c for c in obs_raw.conditions if c.cell_line == "HepG2"][0]

    # Raw values: A549 ER mean = (120 + 130) / 2 = 125, HepG2 ER mean = (114 + 123.5) / 2 = 118.75
    assert cond_a549.feature_means['er'] == pytest.approx(125.0)
    assert cond_hepg2.feature_means['er'] == pytest.approx(118.75)

    # WITHOUT normalization, A549 > HepG2 in raw values
    assert cond_a549.feature_means['er'] > cond_hepg2.feature_means['er']

    # Aggregate WITH fold-change normalization
    obs_norm = aggregate_observation(
        proposal=proposal,
        raw_results=raw_results,
        budget_remaining=96,
        normalization_mode="fold_change"
    )

    # Check normalization mode
    assert obs_norm.normalization_mode == "fold_change"

    # Check metadata
    assert obs_norm.normalization_metadata is not None
    assert obs_norm.normalization_metadata['mode'] == "fold_change"
    assert "A549" in obs_norm.normalization_metadata['baselines_used']
    assert "HepG2" in obs_norm.normalization_metadata['baselines_used']

    # Find normalized conditions
    cond_a549_norm = [c for c in obs_norm.conditions if c.cell_line == "A549"][0]
    cond_hepg2_norm = [c for c in obs_norm.conditions if c.cell_line == "HepG2"][0]

    # Normalized values:
    # A549 ER = 125 / 100 = 1.25
    # HepG2 ER = 162.5 / 130 = 1.25
    assert cond_a549_norm.feature_means['er'] == pytest.approx(1.25)
    assert cond_hepg2_norm.feature_means['er'] == pytest.approx(1.25, abs=0.001)

    # WITH normalization, values are now comparable (both ~1.25 = ~25% above baseline)
    assert abs(cond_a549_norm.feature_means['er'] - cond_hepg2_norm.feature_means['er']) < 0.01


def test_normalization_reduces_variance():
    """Test that fold-change normalization reduces cell line variance."""

    from cell_os.epistemic_agent.schemas import WellSpec

    proposal = Proposal(
        design_id="variance_test",
        hypothesis="test variance reduction",
        wells=[
            WellSpec(cell_line="A549", compound="DMSO", dose_uM=0.0, time_h=24.0, assay="cell_painting", position_tag="center"),
            WellSpec(cell_line="HepG2", compound="DMSO", dose_uM=0.0, time_h=24.0, assay="cell_painting", position_tag="center"),
            WellSpec(cell_line="A549", compound="tunicamycin", dose_uM=10.0, time_h=24.0, assay="cell_painting", position_tag="center"),
            WellSpec(cell_line="HepG2", compound="tunicamycin", dose_uM=10.0, time_h=24.0, assay="cell_painting", position_tag="center"),
            WellSpec(cell_line="A549", compound="DMSO", dose_uM=0.0, time_h=24.0, assay="cell_painting", position_tag="center"),
            WellSpec(cell_line="HepG2", compound="DMSO", dose_uM=0.0, time_h=24.0, assay="cell_painting", position_tag="center"),
        ],
        budget_limit=6
    )

    # Create 3 cell lines (A549, HepG2, U2OS) with DMSO (no treatment effect)
    # All should have ~20% increase over baseline (120% of baseline)
    # WITHOUT normalization: large variance due to baseline differences
    # WITH normalization: all ~1.2, much smaller variance

    raw_results = []
    # Actual baselines: A549=100, HepG2=95, U2OS=105
    for cell_line, er_baseline in [("A549", 100.0), ("HepG2", 95.0), ("U2OS", 105.0)]:
        for i in range(2):
            er_value = er_baseline * 1.2  # 20% increase
            raw_results.append(
                RawWellResult(
                    cell_line=cell_line,
                    treatment=Treatment(compound="DMSO", dose_uM=0.0),
                    observation_time_h=48.0,
                    assay=AssayType.CELL_PAINTING,
                    location=Location(well_id=f"{cell_line}_{i}", plate_id="P1"),
                    readouts={'morphology': {
                        'er': er_value, 'mito': 150.0, 'nucleus': 200.0, 'actin': 120.0, 'rna': 180.0
                    }},
                    qc={'failed': False}
                )
            )

    # Aggregate without normalization
    obs_raw = aggregate_observation(
        proposal=proposal,
        raw_results=raw_results,
        budget_remaining=90,
        normalization_mode="none"
    )

    # Extract ER means for each cell line
    er_means_raw = [c.feature_means['er'] for c in obs_raw.conditions]
    variance_raw = np.var(er_means_raw)

    # Aggregate with normalization
    obs_norm = aggregate_observation(
        proposal=proposal,
        raw_results=raw_results,
        budget_remaining=90,
        normalization_mode="fold_change"
    )

    # Extract normalized ER means
    er_means_norm = [c.feature_means['er'] for c in obs_norm.conditions]
    variance_norm = np.var(er_means_norm)

    # Variance should be MUCH smaller with normalization
    # Raw values: A549=120, HepG2=114, U2OS=126 → some variance
    # Normalized: all ~1.2 → near-zero variance
    assert variance_norm < variance_raw * 0.1  # At least 10× reduction

    # All normalized values should be close to 1.2
    for mean_norm in er_means_norm:
        assert mean_norm == pytest.approx(1.2, abs=0.01)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
