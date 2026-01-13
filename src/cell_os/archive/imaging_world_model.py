# -*- coding: utf-8 -*-
"""ImagingWorldModel

A thin world model wrapper for the ImagingDoseLoop.

It implements the ``WorldModelLike`` protocol defined in ``imaging_loop.py`` and
is intentionally simple:

* Stores dictionaries of GP models for viability and stress keyed by ``SliceKey``.
* Exposes ``get_viability_gps()`` and ``get_stress_gps()``.
* Appends new results into a history ``DataFrame`` via ``update_with_results()``.

You can later extend this to actually refit the GPs when new data arrives or
to adapt it to a more complex ``LabWorldModel``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

import pandas as pd

from cell_os.posteriors import DoseResponseGP, SliceKey
from cell_os.imaging.loop import WorldModelLike


@dataclass
class ImagingWorldModel(WorldModelLike):
    """Minimal world model for the imaging dose loop.

    Parameters
    ----------
    viability_gps:
        Mapping from ``SliceKey`` to a GP over the viability metric for that slice.
    stress_gps:
        Mapping from ``SliceKey`` to a GP over the stress metric (e.g. CellROX) for that slice.
    history:
        Tidy experiment history. Each call to ``update_with_results()`` appends rows
        to this ``DataFrame``.

    Notes
    -----
    This class does **not** refit the GPs yet. It only collects data and exposes the
    GP models provided at construction time. In a real system you would either:

    * add logic in ``update_with_results()`` to update or refit the ``DoseResponseGP``
      models, or
    * treat this as an adapter that delegates to a richer ``LabWorldModel`` object.
    """

    viability_gps: Dict[SliceKey, DoseResponseGP] = field(default_factory=dict)
    stress_gps: Dict[SliceKey, DoseResponseGP] = field(default_factory=dict)
    qc_gps: Dict[SliceKey, DoseResponseGP] = field(default_factory=dict)
    history: pd.DataFrame = field(default_factory=lambda: pd.DataFrame())

    # Protocol methods used by ImagingDoseLoop -------------------------------

    def update_with_results(self, results: list | pd.DataFrame) -> None:
        """Append new experimental results to the history and refit GPs."""
        if isinstance(results, list):
            # Convert list of ExperimentResult objects to DataFrame
            data = []
            for r in results:
                row = {
                    "cell_line": r.slice_key.cell_line,
                    "compound": r.slice_key.compound,
                    "time_h": r.slice_key.time_h,
                    "dose_uM": r.dose_uM,
                    "viability": r.viability_value,
                    "stress": r.stress_value,
                    "cells_per_field": r.cells_per_field_observed,
                    "good_fields_per_well": r.good_fields_per_well_observed
                }
                data.append(row)
            df = pd.DataFrame(data)
        else:
            df = results

        if self.history.empty:
            self.history = df.copy()
        else:
            self.history = pd.concat([self.history, df.copy()], ignore_index=True)
        
        self.refit_gps()

    def refit_gps(self) -> None:
        """Refit all GPs using the current history."""
        if self.history.empty:
            return

        # Helper to refit a dict of GPs
        def _refit_dict(gp_dict: Dict[SliceKey, DoseResponseGP], metric_col: str):
            for key, old_gp in gp_dict.items():
                # We need to find data for this slice
                # The history might have multiple readouts, but we only care about the one matching the key?
                # Actually, SliceKey has 'readout'.
                # But DoseResponseGP.from_dataframe needs to know which column is the value.
                # In our history (from SimulatedExecutor), we have columns like "viability_fraction", "cellrox_mean", etc.
                # The SliceKey.readout field should match the column name in the history.
                
                try:
                    new_gp = DoseResponseGP.from_dataframe(
                        self.history,
                        cell_line=key.cell_line,
                        compound=key.compound,
                        time_h=key.time_h,
                        viability_col=key.readout, # Use the readout name as the column name
                        config=old_gp.config if old_gp else None
                    )
                    gp_dict[key] = new_gp
                except ValueError:
                    # No data for this slice yet, keep the old one (or empty)
                    pass
                except Exception as e:
                    print(f"Warning: Failed to refit GP for {key}: {e}")

        _refit_dict(self.viability_gps, "viability") # The metric col is derived from key.readout
        _refit_dict(self.stress_gps, "stress")
        _refit_dict(self.qc_gps, "qc")

    def get_viability_gps(self) -> Dict[SliceKey, DoseResponseGP]:
        """Return the viability GP models keyed by ``SliceKey``."""
        return self.viability_gps

    def get_stress_gps(self) -> Dict[SliceKey, DoseResponseGP]:
        """Return the stress GP models keyed by ``SliceKey``."""
        return self.stress_gps

    def get_qc_gps(self) -> Dict[SliceKey, DoseResponseGP]:
        """Return the QC GP models keyed by ``SliceKey``."""
        return self.qc_gps

    # Convenience helpers ----------------------------------------------------

    @classmethod
    def from_dicts(
        cls,
        viability_gps: Dict[SliceKey, DoseResponseGP],
        stress_gps: Dict[SliceKey, DoseResponseGP],
        qc_gps: Dict[SliceKey, DoseResponseGP] = {},
    ) -> "ImagingWorldModel":
        """Construct an ``ImagingWorldModel`` from two GP dictionaries.

        This is a minor convenience when wiring in notebooks or demos.
        """
        return cls(
            viability_gps=dict(viability_gps),
            stress_gps=dict(stress_gps),
            qc_gps=dict(qc_gps),
        )
