"""
schema.py

Backwards compatibility shim for older code that used:

    from src.schema import SliceKey, Phase0WorldModel

The real definitions now live in posteriors.py.
"""

from __future__ import annotations

from src.posteriors import SliceKey, DoseResponsePosterior, Phase0WorldModel  # noqa: F401

__all__ = ["SliceKey", "DoseResponsePosterior", "Phase0WorldModel"]
