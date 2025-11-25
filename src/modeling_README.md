# `modeling.py`

Gaussian process dose-response modeling plus simple noise and plate drift estimation for the `cell_os_dose_loop` project.

This module is meant to be:

- Focused on dose → viability curves
- Friendly to notebooks
- Built on `sklearn.GaussianProcessRegressor`
- Easy to extend later

It does **three** main things:

1. Fit a GP dose-response curve for a given `(cell_line, compound, time_h)`
2. Estimate replicate noise as a function of dose
3. Estimate plate drift using control wells and apply a simple correction

---

## 1. Core idea

We assume that viability is a smooth function of log10(dose):

> `viability = f(log10(dose_uM)) + noise`

The Gaussian Process models `f`.  
We work in log10(dose) space, but keep the public API in micromolar.

---

## 2. Main classes

### `DoseResponseGPConfig`

Configuration object for a single GP fit.

Key fields:

- `length_scale`: smoothness in log10(dose) space  
- `length_scale_bounds`: allowed search range during hyperparameter optimization  
- `constant_value`: output scale of the GP  
- `constant_value_bounds`: allowed range for the constant kernel  
- `noise_level`: initial noise level for the white kernel  
- `noise_level_bounds`: allowed range for noise  
- `n_restarts_optimizer`: hyperparameter optimizer restarts

Most use cases can rely on the defaults.

---

### `DoseResponseGP`

A fitted GP model for one slice:

> one cell line + one compound + one time point

It stores:

- `cell_line`, `compound`, `time_h`
- `config`
- `model`: `GaussianProcessRegressor`
- `X_train`: log10(dose_uM), shape `(n, 1)`
- `y_train`: viability
- `prior_model`: optional `DoseResponseGP` used to build a shrinkage prior
- `is_fitted`: flag that the model fit succeeded

#### Constructors

##### `DoseResponseGP.empty()`

Create an unfitted placeholder.

- Has no training data
- `is_fitted = False`
- Any call to `predict` returns arrays of `NaN` and raises a warning

Useful when you want to keep a slot for a GP but do not have data yet.

##### `DoseResponseGP.from_dataframe(...)`

Fit a GP from a well-level DataFrame.

Required columns:

- `"cell_line"`
- `"compound"`
- `"time_h"`
- dose column, default `"dose_uM"`
- viability column, default `"viability"`

Typical usage:

```python
from src.modeling import DoseResponseGP, DoseResponseGPConfig

config = DoseResponseGPConfig()
gp = DoseResponseGP.from_dataframe(
    df,
    cell_line="HepG2",
    compound="staurosporine",
    time_h=24.0,
    config=config,
    dose_col="dose_uM",
    viability_col="viability",
)
