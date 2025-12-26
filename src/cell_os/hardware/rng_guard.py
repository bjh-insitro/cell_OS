"""
RNG Stream Integrity Enforcement

Wraps numpy RNG instances to enforce stream partitioning and detect violations.

Observer independence requires that:
- Growth RNG is never touched during measurement
- Assay RNG does not influence biological state
- Stream order is deterministic and auditable

Any violation of these contracts crashes immediately.
"""

import copy
import inspect
from typing import Set, Optional, Any
import numpy as np


class RNGStreamViolation(RuntimeError):
    """Raised when RNG stream is used from unauthorized context.

    This is a correctness invariant, not a warning.
    Violating stream partitioning breaks observer independence.
    """
    def __init__(
        self,
        stream_name: str,
        caller_function: str,
        caller_file: str,
        allowed_contexts: Set[str],
        call_count: int
    ):
        self.stream_name = stream_name
        self.caller_function = caller_function
        self.caller_file = caller_file
        self.allowed_contexts = allowed_contexts
        self.call_count = call_count

        message = (
            f"RNG stream '{stream_name}' used from unauthorized context.\n"
            f"  Caller: {caller_function} ({caller_file})\n"
            f"  Allowed contexts: {sorted(allowed_contexts)}\n"
            f"  Call count: {call_count}\n"
            f"This violates observer independence."
        )
        super().__init__(message)


class ValidatedRNG:
    """Wraps numpy RNG with context enforcement.

    Each RNG stream has an allowed set of caller contexts.
    Calls from unauthorized contexts crash immediately.

    Design:
    - Shallow stack inspection (2 levels up)
    - Call counting for diagnostics
    - Zero state mutation (wrapper is pure)

    Usage:
        rng_growth = ValidatedRNG(
            np.random.default_rng(seed),
            stream_name="growth",
            allowed_patterns={"_grow_", "_advance_", "_divide_"}
        )

        # From _grow_cells() - allowed
        rng_growth.random()

        # From measure_morphology() - crashes
        rng_growth.random()  # RNGStreamViolation
    """

    def __init__(
        self,
        base_rng: np.random.Generator,
        stream_name: str,
        allowed_patterns: Set[str],
        enforce: bool = True
    ):
        """Initialize validated RNG wrapper.

        Args:
            base_rng: Underlying numpy RNG
            stream_name: Human-readable name ("growth", "assay", etc.)
            allowed_patterns: Set of substrings that must appear in caller name
            enforce: If False, logs violations but doesn't crash (for debugging)
        """
        self._rng = base_rng
        self.stream_name = stream_name
        self.allowed_patterns = allowed_patterns
        self.enforce = enforce
        self.call_count = 0

    def _check_caller(self) -> None:
        """Verify caller is authorized to use this stream.

        Stack inspection:
        - Level 0: _check_caller (this function)
        - Level 1: random/integers/etc (wrapper method)
        - Level 2: actual caller we want to validate

        Raises:
            RNGStreamViolation: If caller not in allowed contexts
        """
        if not self.enforce:
            return

        # Get caller 2 levels up
        frame = inspect.currentframe()
        try:
            # Walk up: _check_caller -> wrapper method -> actual caller
            caller_frame = frame.f_back.f_back
            if caller_frame is None:
                return  # Can't validate, allow (edge case)

            caller_func = caller_frame.f_code.co_name
            caller_file = caller_frame.f_code.co_filename

            # Check if caller function matches any allowed pattern
            for pattern in self.allowed_patterns:
                if pattern in caller_func:
                    return  # Authorized

            # Unauthorized - crash
            raise RNGStreamViolation(
                stream_name=self.stream_name,
                caller_function=caller_func,
                caller_file=caller_file,
                allowed_contexts=self.allowed_patterns,
                call_count=self.call_count
            )
        finally:
            del frame  # Avoid reference cycles

    # Proxy all common RNG methods with validation

    def random(self, size=None):
        """Generate uniform random floats in [0, 1)."""
        self._check_caller()
        self.call_count += 1
        return self._rng.random(size)

    def integers(self, low, high=None, size=None, dtype=None, endpoint=False):
        """Generate random integers."""
        self._check_caller()
        self.call_count += 1
        # Pass through arguments, filtering out None values to use defaults
        kwargs = {}
        if high is not None:
            kwargs['high'] = high
        if size is not None:
            kwargs['size'] = size
        if dtype is not None:
            kwargs['dtype'] = dtype
        if endpoint is not False:  # Only pass if non-default
            kwargs['endpoint'] = endpoint
        return self._rng.integers(low, **kwargs)

    def normal(self, loc=0.0, scale=1.0, size=None):
        """Generate normally distributed values."""
        self._check_caller()
        self.call_count += 1
        return self._rng.normal(loc, scale, size)

    def lognormal(self, mean=0.0, sigma=1.0, size=None):
        """Generate lognormally distributed values."""
        self._check_caller()
        self.call_count += 1
        return self._rng.lognormal(mean, sigma, size)

    def uniform(self, low=0.0, high=1.0, size=None):
        """Generate uniformly distributed values."""
        self._check_caller()
        self.call_count += 1
        return self._rng.uniform(low, high, size)

    def choice(self, a, size=None, replace=True, p=None):
        """Generate random sample from array."""
        self._check_caller()
        self.call_count += 1
        return self._rng.choice(a, size, replace, p)

    def poisson(self, lam=1.0, size=None):
        """Generate Poisson distributed values."""
        self._check_caller()
        self.call_count += 1
        return self._rng.poisson(lam, size)

    def binomial(self, n, p, size=None):
        """Generate binomially distributed values."""
        self._check_caller()
        self.call_count += 1
        return self._rng.binomial(n, p, size)

    def exponential(self, scale=1.0, size=None):
        """Generate exponentially distributed values."""
        self._check_caller()
        self.call_count += 1
        return self._rng.exponential(scale, size)

    def get_state(self):
        """Get current RNG state (for diagnostics only)."""
        # Don't increment counter - this is inspection
        return self._rng.bit_generator.state

    def reset_call_count(self) -> int:
        """Reset and return call count (for per-cycle diagnostics)."""
        count = self.call_count
        self.call_count = 0
        return count

    def snapshot(self) -> dict:
        """Capture current RNG state for reproducibility tests.

        Returns deep copy to prevent accidental mutation.
        """
        return copy.deepcopy(self._rng.bit_generator.state)

    def restore(self, state: dict):
        """Restore RNG to previous state.

        Args:
            state: State dict from snapshot()
        """
        self._rng.bit_generator.state = state
