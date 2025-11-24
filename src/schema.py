"""
schema.py

Temporary compatibility shim.

Historically this file defined `Phase0WorldModel` and related types.
Those inference artifacts now live in `posteriors.py`.

New code should import from `src.posteriors` directly:
    from src.posteriors import DoseResponsePosterior, SliceKey

This file exists so older imports keep working while the repo is migrated.
"""

from __future__ import annotations

from src.posteriors import SliceKey, DoseResponsePosterior, Phase0WorldModel  # noqa: F401
