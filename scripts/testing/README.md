# Testing Scripts

Utilities for testing and validation of Cell OS components.

## Active Scripts

- `compare_designs.py` - Compare experimental designs
- `spatial_diagnostic.py` - Diagnose spatial artifacts in plates
- `verify_sentinel_scaffold.py` - Validate sentinel scaffold integrity

## Usage

Run test utilities directly:

```bash
python scripts/testing/[script_name].py
```

These complement the main test suite in `tests/`.

## Note

Some old testing scripts (imaging_loop_smoketest, qc_slope_test, etc.) have been moved to archive.
