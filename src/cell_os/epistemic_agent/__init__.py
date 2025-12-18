"""
Epistemic Agency: Agent that learns about its world from scratch.

The agent starts knowing:
- What knobs it can turn (cell line, compound, dose, time, assay, position)
- That experiments are noisy and cost wells
- That budget is finite

The agent does NOT know:
- IC50 values, optimal doses, or that "mid-dose is special"
- That edge effects exist (it may hypothesize and test)
- That death signatures converge at high dose
- That 12h is the "mechanism window"

It must discover all of this through experiments.
"""

__version__ = "0.1.0"
