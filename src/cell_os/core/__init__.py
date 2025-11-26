"""
Compatibility shim for the legacy `core` package.

This exposes `cell_os.core.world_model` so imports like
`from cell_os.core.world_model import WorldModel` keep working
while the codebase migrates fully into `cell_os`.
"""

from . import world_model

__all__ = ["world_model"]
