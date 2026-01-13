# -*- coding: utf-8 -*-
"""Tests for the imaging acquisition utilities.

Ensures that ``propose_imaging_doses`` respects the viability band and
max_std constraints defined in :class:`ImagingWindowGoal`.
"""

import numpy as np
from unittest.mock import MagicMock

from cell_os.imaging.goal import ImagingWindowGoal
from cell_os.imaging.acquisition import propose_imaging_doses
from cell_os.posteriors import DoseResponseGP, SliceKey


def make_mock_gp(doses, mean_vals, std_vals):
    """Create a MagicMock mimicking a DoseResponseGP.

    The mock's ``predict`` method returns the supplied ``mean_vals`` and
    ``std_vals`` regardless of the input dose array. This is sufficient for the
    deterministic unit test.
    """
    gp = MagicMock(spec=DoseResponseGP)
    def _predict(x, return_std=False):
        m = np.array(mean_vals, dtype=float)
        if return_std:
            s = np.array(std_vals, dtype=float)
            return m, s
        return m
    gp.predict.side_effect = _predict
    return gp


def test_propose_imaging_doses_respects_viability_band_and_max_std():
    # Define slice keys for viability and stress
    sk_viab = SliceKey(
        cell_line="U2OS",
        compound="TBHP",
        time_h=24.0,
        readout="viability_fraction",
    )
    sk_stress = SliceKey(
        cell_line="U2OS",
        compound="TBHP",
        time_h=24.0,
        readout="cellrox_mean",
    )

    # Dose grid to test against
    doses = np.array([0.1, 1.0, 10.0], dtype=float)

    # Viability: only the middle dose falls inside the band [0.8, 1.0]
    viab_mean = [0.3, 0.85, 0.2]
    viab_std = [0.05, 0.05, 0.05]

    # Stress: increasing with dose (just for illustration)
    stress_mean = [0.2, 0.8, 1.0]
    stress_std = [0.0, 0.0, 0.0]

    viab_gp = make_mock_gp(doses, viab_mean, viab_std)
    stress_gp = make_mock_gp(doses, stress_mean, stress_std)

    goal = ImagingWindowGoal(
        viability_min=0.8,
        viability_max=1.0,
        max_std=0.2,
        stress_min=None,
        viability_metric="viability_fraction",
        stress_metric="cellrox_mean",
    )

    plans = propose_imaging_doses(
        viability_gps={sk_viab: viab_gp},
        stress_gps={sk_stress: stress_gp},
        goal=goal,
        dose_grid=doses,
    )

    # Expect all 3 doses returned, sorted by score
    assert len(plans) == 3
    
    # The best plan should be the middle dose (1.0) which satisfies constraints
    best_plan = plans[0]
    assert best_plan.dose_uM == 1.0
    assert best_plan.viability_value == 0.85
    
    # Verify it has a better score than the others
    assert best_plan.score > plans[1].score
    assert best_plan.score > plans[2].score
    assert plans[0].dose_uM == 1.0
    assert plans[0].stress_value == 0.8
