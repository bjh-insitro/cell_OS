"""
modeling.py

Gaussian process dose-response modeling and simple noise / drift estimation
for the cell-os-dose-loop project.

This module is intentionally small and focused:

1. Fit a GP to viability vs dose for a given (cell_line, compound, time_h)
2. Estimate replicate noise as a function of dose
3. Estimate plate drift from control wells

Everything is written to be:
- Notebook friendly
- Built on sklearn GaussianProcessRegressor
- Easy to extend later
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple, Dict, Any, Iterable

import numpy as np
import pandas as pd
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import (
    RBF,
    WhiteKernel,
    ConstantKernel,
)

# -------------------------------------------------------------------
# Helper types
# -------------------------------------------------------------------

ArrayLike = np.ndarray


@dataclass
class DoseResponseGPConfig:
    """Configuration for a single dose-response GP fit."""

    # Length scale in log10(dose) space
    length_scale: float = 0.5
    length_scale_bounds: Tuple[float, float] = (1e-2, 1e2)

    # Output scale
    constant_value: float = 1.0
    constant_value_bounds: Tuple[float, float] = (1e-3, 1e3)

    # Noise level (will still be refit)
    noise_level: float = 0.05
    noise_level_bounds: Tuple[float, float] = (1e-5, 1.0)

    # Number of restarts for optimizer
    n_restarts_optimizer: int = 5


@dataclass
class DoseResponseGP:
    """
    A GP model for a single dose-response slice:

      viability = f(log10(dose)) + noise

    Use:
        gp = DoseResponseGP.from_dataframe(df_slice, config)
        grid = gp.predict_on_grid(50)
    """

    cell_line: str
    compound: str
    time_h: float

    config: DoseResponseGPConfig
    model: GaussianProcessRegressor

    # Raw training data in log10-dose space
    X_train: ArrayLike
    y_train: ArrayLike

    # Optional prior model for transfer learning
    prior_model: Optional["DoseResponseGP"] = None

    @classmethod
    def empty(cls) -> "DoseResponseGP":
        """
        Create an empty GP model instance.
        Useful for initialization before any data is available.
        """
        config = DoseResponseGPConfig()
        model = _build_gp_model(config)

        # Initialize with dummy data to satisfy the type checker and structure
        # This is a placeholder state
        return cls(
            cell_line="None",
            compound="None",
            time_h=0.0,
            config=config,
            model=model,
            X_train=np.array([]).reshape(-1, 1),
            y_train=np.array([]),
        )

    @classmethod
    def from_dataframe(
        cls,
        df: pd.DataFrame,
        cell_line: str,
        compound: str,
        time_h: float,
        config: Optional[DoseResponseGPConfig] = None,
        dose_col: str = "dose_uM",
        viability_col: str = "viability",
        prior_model: Optional["DoseResponseGP"] = None,
    ) -> "DoseResponseGP":
        """
        Build and fit a GP from a long-format DataFrame.

        Expected columns:
            - 'cell_line'
            - 'compound'
            - 'time_h'  (or similar, numeric)
            - dose_col  (default 'dose_uM')
            - viability_col  (default 'viability')

        Rows should already correspond to a single plate type
        and readout (viability).
        """
        if config is None:
            config = DoseResponseGPConfig()

        # Filter down to the slice we care about
        mask = (
            (df["cell_line"] == cell_line)
            & (df["compound"] == compound)
            & (df["time_h"] == time_h)
        )
        df_slice = df.loc[mask].copy()

        if df_slice.empty:
            raise ValueError(
                f"No rows found for cell_line={cell_line}, compound={compound}, time_h={time_h}"
            )

        # Convert dose to log10 space to make GP easier to fit
        if (df_slice[dose_col] <= 0).any():
            raise ValueError("All doses must be positive to use log10 dose space.")

        X = np.log10(df_slice[dose_col].to_numpy()).reshape(-1, 1)
        y = df_slice[viability_col].to_numpy().astype(float)

        # If prior model exists, fit to residual
        if prior_model is not None:
            prior_mean, _ = prior_model.predict(
                df_slice[dose_col].to_numpy(), return_std=True
            )
            y = y - prior_mean

        model = _build_gp_model(config)
        model.fit(X, y)

        return cls(
            cell_line=cell_line,
            compound=compound,
            time_h=time_h,
            config=config,
            model=model,
            X_train=X,
            y_train=y,
            prior_model=prior_model,
        )

    def predict(
        self,
        dose_uM: ArrayLike,
        return_std: bool = True,
    ) -> Tuple[ArrayLike, Optional[ArrayLike]]:
        """
        Predict viability at arbitrary doses (in micromolar).

        Args:
            dose_uM: 1D numpy array of positive doses
            return_std: whether to return predictive std

        Returns:
            mean: predicted viability
            std: predictive standard deviation (or None)
        """
        dose_uM = np.asarray(dose_uM, dtype=float)
        if (dose_uM <= 0).any():
            raise ValueError("All doses must be positive to use log10 dose space.")

        X = np.log10(dose_uM).reshape(-1, 1)

        if return_std:
            mean, std = self.model.predict(X, return_std=True)

            # Add prior mean if exists
            if self.prior_model is not None:
                prior_mean, prior_std = self.prior_model.predict(
                    dose_uM, return_std=True
                )
                mean = mean + prior_mean
                # Combine uncertainties (assuming independence for simplicity)
                std = np.sqrt(std ** 2 + prior_std ** 2)

            return mean, std
        else:
            mean = self.model.predict(X, return_std=False)

            if self.prior_model is not None:
                prior_mean, _ = self.prior_model.predict(
                    dose_uM, return_std=False
                )
                mean = mean + prior_mean

            return mean, None

    def predict_on_grid(
        self,
        num_points: int = 50,
        dose_min: Optional[float] = None,
        dose_max: Optional[float] = None,
        grid_size: Optional[int] = None,
    ) -> Dict[str, ArrayLike]:
        """
        Predict on a regular grid between the min and max training dose
        (or user supplied dose_min and dose_max).

        Args:
            num_points: Number of points in the dose grid.
            dose_min: Minimum dose (uM). If None, uses min training dose.
            dose_max: Maximum dose (uM). If None, uses max training dose.
            grid_size: Backwards compatible alias for num_points.

        Returns:
            Dict with:
                - 'dose_uM'
                - 'mean'
                - 'std'
        """
        # Backwards compat: allow callers to pass grid_size instead of num_points
        if grid_size is not None:
            num_points = int(grid_size)

        # If no training data, return empty arrays
        if self.X_train.size == 0:
            return {
                "dose_uM": np.array([]),
                "mean": np.array([]),
                "std": np.array([]),
            }

        train_dose = 10 ** (self.X_train.flatten())
        if dose_min is None:
            dose_min = float(train_dose.min())
        if dose_max is None:
            dose_max = float(train_dose.max())

        grid = np.logspace(np.log10(dose_min), np.log10(dose_max), num_points)
        mean, std = self.predict(grid, return_std=True)

        return {
            "dose_uM": grid,
            "mean": mean,
            "std": std,
        }


def _build_gp_model(config: DoseResponseGPConfig) -> GaussianProcessRegressor:
    """
    Internal helper to create a GaussianProcessRegressor
    with reasonable defaults for dose-response curves.
    """
    kernel = ConstantKernel(
        constant_value=config.constant_value,
        constant_value_bounds=config.constant_value_bounds,
    ) * RBF(
        length_scale=config.length_scale,
        length_scale_bounds=config.length_scale_bounds,
    ) + WhiteKernel(
        noise_level=config.noise_level,
        noise_level_bounds=config.noise_level_bounds,
    )

    gp = GaussianProcessRegressor(
        kernel=kernel,
        n_restarts_optimizer=config.n_restarts_optimizer,
        normalize_y=True,
    )
    return gp


# -------------------------------------------------------------------
# Noise and drift estimation
# -------------------------------------------------------------------

def estimate_replicate_noise(
    df: pd.DataFrame,
    dose_col: str = "dose_uM",
    viability_col: str = "viability",
    group_cols: Iterable[str] = ("cell_line", "compound", "time_h", "dose_uM"),
) -> pd.DataFrame:
    """
    Estimate empirical noise from replicate wells.

    For each group defined by `group_cols` (default is per cell_line, compound,
    time, and dose), compute:
        - replicate count
        - mean viability
        - standard deviation of viability

    Returns a DataFrame with one row per group and columns:
        group columns + ['n_reps', 'viability_mean', 'viability_std']

    You can later use this to build a "noise vs dose" map.
    """
    group_cols = list(group_cols)

    agg = (
        df.groupby(group_cols)[viability_col]
        .agg(["count", "mean", "std"])
        .reset_index()
        .rename(
            columns={
                "count": "n_reps",
                "mean": "viability_mean",
                "std": "viability_std",
            }
        )
    )

    # Replace NaN std (single replicate) with zero
    agg["viability_std"] = agg["viability_std"].fillna(0.0)

    return agg


def estimate_plate_drift_from_controls(
    df: pd.DataFrame,
    plate_col: str = "plate_id",
    viability_col: str = "viability",
    is_control_col: str = "is_control",
) -> pd.DataFrame:
    """
    Estimate plate drift using control wells.

    Expected columns:
        - plate_col (for example 'plate_id')
        - viability_col (numeric)
        - is_control_col (boolean, True for control wells)

    This function:
        1. Selects only control wells
        2. Computes per-plate control mean
        3. Computes global control mean across plates
        4. Returns a DataFrame with:
              plate_id, control_mean, control_delta, control_zscore

    control_delta = plate_control_mean - global_control_mean
    control_zscore = control_delta / global_control_std

    You can subtract `control_delta` from all wells on that plate
    to correct for drift if you want a simple adjustment.
    """
    if is_control_col not in df.columns:
        raise ValueError(
            f"Expected a boolean '{is_control_col}' column to flag control wells."
        )

    controls = df.loc[df[is_control_col].astype(bool)].copy()
    if controls.empty:
        raise ValueError("No control wells found for drift estimation.")

    per_plate = (
        controls.groupby(plate_col)[viability_col]
        .agg(["count", "mean", "std"])
        .reset_index()
        .rename(
            columns={
                "count": "n_controls",
                "mean": "control_mean",
                "std": "control_std",
            }
        )
    )

    global_mean = controls[viability_col].mean()
    global_std = controls[viability_col].std()

    per_plate["control_delta"] = per_plate["control_mean"] - global_mean

    if global_std is None or np.isnan(global_std) or global_std == 0:
        # If controls are extremely tight, z-score is not informative
        per_plate["control_zscore"] = 0.0
    else:
        per_plate["control_zscore"] = per_plate["control_delta"] / global_std

    return per_plate


def apply_plate_drift_correction(
    df: pd.DataFrame,
    drift_df: pd.DataFrame,
    plate_col: str = "plate_id",
    viability_col: str = "viability",
    delta_col: str = "control_delta",
    corrected_col: str = "viability_corrected",
) -> pd.DataFrame:
    """
    Apply a simple plate drift correction to all wells.

    Args:
        df: full well-level DataFrame
        drift_df: output of estimate_plate_drift_from_controls
        plate_col: name of the plate identifier column
        viability_col: column to correct
        delta_col: column in drift_df that contains the plate-specific delta
        corrected_col: name of the new column with corrected viability

    Returns:
        A copy of df with an extra column `corrected_col`.
    """
    # Merge per-plate drift statistics
    merged = df.merge(
        drift_df[[plate_col, delta_col]],
        on=plate_col,
        how="left",
        validate="many_to_one",
    )

    # If some plates are missing drift info, assume zero delta
    merged[delta_col] = merged[delta_col].fillna(0.0)

    # Apply correction
    merged[corrected_col] = merged[viability_col] - merged[delta_col]

    return merged
