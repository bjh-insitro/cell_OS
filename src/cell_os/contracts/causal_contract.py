"""
Causal contract enforcement for measurement functions.

Enforces observer independence and prevents measurements from:
1. Mutating biological state
2. Reading forbidden ground truth
3. Leaking omniscient truth in outputs

The contract is enforced at runtime via decorators and read-only proxies.
"""

from __future__ import annotations

import os
import time
import warnings
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Set, List


class CausalContractViolation(RuntimeError):
    """Raised when a measurement violates its causal contract."""
    pass


# ----------------------------
# Modes
# ----------------------------

def _strict_mode() -> bool:
    """Check if strict enforcement is enabled (raises on violations)."""
    return os.getenv("CELL_OS_STRICT_CAUSAL_CONTRACT", "0") == "1"


def _record_mode() -> bool:
    """Check if violation recording is enabled (collects violations without raising)."""
    return os.getenv("CELL_OS_CONTRACT_RECORD", "0") == "1"


_CONTRACT_VIOLATIONS: List[str] = []


def get_recorded_contract_violations() -> List[str]:
    """Get list of recorded violations (when in record mode)."""
    return list(_CONTRACT_VIOLATIONS)


def clear_recorded_contract_violations() -> None:
    """Clear recorded violations list."""
    _CONTRACT_VIOLATIONS.clear()


def _violation(msg: str) -> None:
    """Handle a contract violation (record, raise, or warn based on mode)."""
    if _record_mode():
        _CONTRACT_VIOLATIONS.append(msg)
        return
    if _strict_mode():
        raise CausalContractViolation(msg)
    warnings.warn(msg, RuntimeWarning, stacklevel=3)


# ----------------------------
# Matching helpers
# ----------------------------

def _normalize_brackets(path: str) -> str:
    """Normalize any [whatever] into [*] so patterns can match."""
    out = []
    i = 0
    while i < len(path):
        if path[i] == "[":
            j = path.find("]", i + 1)
            if j == -1:
                out.append(path[i:])
                break
            out.append("[*]")
            i = j + 1
        else:
            out.append(path[i])
            i += 1
    return "".join(out)


def _matches(path: str, patterns: Set[str]) -> bool:
    """
    Check if access path matches any pattern.

    Supported patterns:
      - exact: "state.viability"
      - prefix wildcard: "state.washout_*"
      - bracket wildcard: "state.subpopulations[*].er_stress"
      - terminal wildcard: "state.subpopulations[*].*"
    """
    norm = _normalize_brackets(path)
    for pat in patterns:
        if pat == path or pat == norm:
            return True
        if pat.endswith("*"):
            # prefix wildcard
            if norm.startswith(pat[:-1]):
                return True
        if pat.endswith(".*"):
            if norm.startswith(pat[:-2]):
                return True
    return False


def _is_primitive(x: Any) -> bool:
    """Check if value is a primitive type (no nested access needed)."""
    return isinstance(x, (str, bytes, int, float, bool, type(None)))


@dataclass(frozen=True)
class MeasurementContract:
    """
    Declarative contract for a measurement function.

    Specifies:
    - Which state fields can be read (allow-list)
    - Which fields are explicitly forbidden (block-list)
    - Which RNG stream to use
    - Whether debug truth output is allowed
    - Which output keys are forbidden at top level
    """
    name: str
    allowed_reads: Set[str] = field(default_factory=set)
    forbidden_reads: Set[str] = field(default_factory=set)
    rng_stream: Optional[str] = "assay"

    # Output enforcement
    allow_debug_truth: bool = False
    forbidden_output_keys: Set[str] = field(default_factory=set)


@dataclass
class _AccessLog:
    """Log of all reads and writes during measurement execution."""
    reads: Set[str] = field(default_factory=set)
    writes: Set[str] = field(default_factory=set)


class _ReadOnlyProxy:
    """
    Read-only proxy with:
      - full traversal support (__iter__, items, keys, values, __len__, get)
      - access logging
      - forbidden-read enforcement
      - mutation prevention
    """

    __slots__ = ("_obj", "_path", "_log", "_contract", "_debug_truth_enabled")

    def __init__(self, obj: Any, path: str, log: _AccessLog, contract: MeasurementContract, debug_truth_enabled: bool):
        object.__setattr__(self, "_obj", obj)
        object.__setattr__(self, "_path", path)
        object.__setattr__(self, "_log", log)
        object.__setattr__(self, "_contract", contract)
        object.__setattr__(self, "_debug_truth_enabled", debug_truth_enabled)

    def _record_read(self, p: str) -> None:
        """Record a read and check if it's forbidden."""
        log = object.__getattribute__(self, "_log")
        contract = object.__getattribute__(self, "_contract")
        log.reads.add(p)
        if _matches(p, contract.forbidden_reads):
            _violation(f"[{contract.name}] forbidden read: {p}")

    def __getattr__(self, name: str) -> Any:
        """Attribute access with wrapping and logging."""
        obj = object.__getattribute__(self, "_obj")
        path = object.__getattribute__(self, "_path")
        p = f"{path}.{name}" if path else name
        self._record_read(p)

        val = getattr(obj, name)
        if _is_primitive(val):
            return val
        return _ReadOnlyProxy(val, p, object.__getattribute__(self, "_log"), object.__getattribute__(self, "_contract"),
                             object.__getattribute__(self, "_debug_truth_enabled"))

    def __getitem__(self, key: Any) -> Any:
        """Item access with wrapping and logging."""
        obj = object.__getattribute__(self, "_obj")
        path = object.__getattribute__(self, "_path")
        p = f"{path}[{repr(key)}]" if path else f"[{repr(key)}]"
        self._record_read(p)

        val = obj[key]
        if _is_primitive(val):
            return val
        return _ReadOnlyProxy(val, p, object.__getattribute__(self, "_log"), object.__getattribute__(self, "_contract"),
                             object.__getattribute__(self, "_debug_truth_enabled"))

    def __setattr__(self, name: str, value: Any) -> None:
        """Prevent attribute mutation."""
        contract = object.__getattribute__(self, "_contract")
        path = object.__getattribute__(self, "_path")
        object.__getattribute__(self, "_log").writes.add(f"{path}.{name}")
        _violation(f"[{contract.name}] attempted mutation: {path}.{name}")

    def __setitem__(self, key: Any, value: Any) -> None:
        """Prevent item mutation."""
        contract = object.__getattribute__(self, "_contract")
        path = object.__getattribute__(self, "_path")
        object.__getattribute__(self, "_log").writes.add(f"{path}[{repr(key)}]")
        _violation(f"[{contract.name}] attempted mutation: {path}[{repr(key)}]")

    def __iter__(self):
        """Iterate over container while preserving wrapping and logging."""
        obj = object.__getattribute__(self, "_obj")
        path = object.__getattribute__(self, "_path")
        self._record_read(f"{path}.__iter__")

        # Mapping-like
        if hasattr(obj, "keys") and callable(getattr(obj, "keys")):
            for k in obj.keys():
                yield k
            return

        # Sequence-like
        if isinstance(obj, (list, tuple)):
            for i in range(len(obj)):
                yield self[i]
            return

        # Fallback
        try:
            for item in obj:
                yield item
        except TypeError:
            return

    def items(self):
        """Iterate over dict items with wrapped values."""
        obj = object.__getattribute__(self, "_obj")
        path = object.__getattribute__(self, "_path")
        self._record_read(f"{path}.items")
        if hasattr(obj, "items") and callable(getattr(obj, "items")):
            for k, v in obj.items():
                p = f"{path}[{repr(k)}]"
                if _is_primitive(v):
                    yield k, v
                else:
                    yield k, _ReadOnlyProxy(v, p, object.__getattribute__(self, "_log"),
                                            object.__getattribute__(self, "_contract"),
                                            object.__getattribute__(self, "_debug_truth_enabled"))
        else:
            return

    def keys(self):
        """Return dict keys."""
        obj = object.__getattribute__(self, "_obj")
        path = object.__getattribute__(self, "_path")
        self._record_read(f"{path}.keys")
        if hasattr(obj, "keys") and callable(getattr(obj, "keys")):
            return obj.keys()
        return []

    def values(self):
        """Iterate over dict values with wrapping."""
        obj = object.__getattribute__(self, "_obj")
        path = object.__getattribute__(self, "_path")
        self._record_read(f"{path}.values")
        if hasattr(obj, "values") and callable(getattr(obj, "values")):
            for v in obj.values():
                if _is_primitive(v):
                    yield v
                else:
                    yield _ReadOnlyProxy(v, f"{path}[*]", object.__getattribute__(self, "_log"),
                                         object.__getattribute__(self, "_contract"),
                                         object.__getattribute__(self, "_debug_truth_enabled"))
        else:
            for item in self:
                yield item

    def __len__(self) -> int:
        """Return length of container."""
        obj = object.__getattribute__(self, "_obj")
        path = object.__getattribute__(self, "_path")
        self._record_read(f"{path}.__len__")
        try:
            return len(obj)
        except TypeError:
            return 0

    def get(self, key: Any, default: Any = None) -> Any:
        """Get item with default (dict-like)."""
        path = object.__getattribute__(self, "_path")
        self._record_read(f"{path}.get")
        try:
            return self[key]
        except Exception:
            return default


def _enforce_allow_list(contract: MeasurementContract, log: _AccessLog) -> None:
    """Enforce allow-list: all reads must match allowed patterns."""
    if not contract.allowed_reads:
        return

    for p in log.reads:
        if _matches(p, contract.allowed_reads):
            continue
        # allow some basic python/meta
        if p.endswith(".__class__") or p.endswith(".__dict__"):
            continue
        _violation(f"[{contract.name}] read not in allow-list: {p}")


def validate_measurement_output(contract: MeasurementContract, out: Any, debug_truth_enabled: bool) -> None:
    """
    Validate measurement output against contract.

    Checks:
    - No forbidden keys at top level
    - Debug truth only present when enabled
    - Debug truth is properly formatted
    """
    if not isinstance(out, dict):
        return

    for k in contract.forbidden_output_keys:
        if k in out:
            _violation(f"[{contract.name}] forbidden output key leaked: {k}")

    if "_debug_truth" in out:
        if not contract.allow_debug_truth:
            _violation(f"[{contract.name}] _debug_truth present but contract forbids it")
        if not debug_truth_enabled:
            _violation(f"[{contract.name}] _debug_truth present but debug_truth_enabled is False")
        if not isinstance(out["_debug_truth"], dict):
            _violation(f"[{contract.name}] _debug_truth must be a dict")


def _emit_contract_report(
    run_context: Any,
    contract: MeasurementContract,
    log: _AccessLog,
    violations: List[str],
    debug_truth_enabled: bool,
    timing_ms: float
) -> None:
    """Emit contract report to run_context for forensic trail."""
    if run_context is None:
        return

    read_counts = Counter(log.reads)
    reads_top = dict(read_counts.most_common(25))

    mode = "strict" if _strict_mode() else ("record" if _record_mode() else "warn")
    cycle = getattr(run_context, "cycle", 0)

    try:
        from ..epistemic_agent.beliefs.ledger import ContractReport

        report = ContractReport(
            cycle=cycle,
            assay_name=contract.name,
            mode=mode,
            reads_top=reads_top,
            violations=list(violations),
            writes_detected=list(log.writes),
            decorator_present=True,
            debug_truth_enabled=debug_truth_enabled,
            timing_ms=timing_ms,
        )

        if not hasattr(run_context, "contract_reports"):
            run_context.contract_reports = []

        run_context.contract_reports.append(report)
    except ImportError:
        pass


def enforce_measurement_contract(contract: MeasurementContract, vessel_arg_index: int = 1) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator for VM assay entrypoints.

    Expected signature:
        def measure(self, vessel, *args, **kwargs) -> dict

    Args:
        contract: The measurement contract to enforce
        vessel_arg_index: Position of vessel argument (default 1, after self)

    Returns:
        Decorated function that enforces the contract
    """
    def deco(fn: Callable[..., Any]) -> Callable[..., Any]:
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            if len(args) <= vessel_arg_index:
                return fn(*args, **kwargs)

            self_obj = args[0]
            vessel = args[vessel_arg_index]

            # Get run_context from VM (self_obj.vm.run_context for assays)
            vm = getattr(self_obj, "vm", None)
            run_context = getattr(vm, "run_context", None) if vm is not None else None
            debug_truth_enabled = bool(getattr(run_context, "debug_truth_enabled", False)) if run_context is not None else False

            start_time = time.time()

            log = _AccessLog()
            ro_vessel = _ReadOnlyProxy(vessel, "state", log, contract, debug_truth_enabled)

            new_args = list(args)
            new_args[vessel_arg_index] = ro_vessel

            violations_list = []
            if _record_mode():
                old_violations = list(_CONTRACT_VIOLATIONS)

            out = fn(*tuple(new_args), **kwargs)

            _enforce_allow_list(contract, log)
            validate_measurement_output(contract, out, debug_truth_enabled)

            if log.writes:
                _violation(f"[{contract.name}] writes detected: {sorted(log.writes)[:5]}")

            if _record_mode():
                new_violations = _CONTRACT_VIOLATIONS[len(old_violations):]
                violations_list = list(new_violations)

            elapsed_ms = (time.time() - start_time) * 1000.0

            _emit_contract_report(
                run_context=run_context,
                contract=contract,
                log=log,
                violations=violations_list,
                debug_truth_enabled=debug_truth_enabled,
                timing_ms=elapsed_ms
            )

            return out

        wrapped.__name__ = getattr(fn, "__name__", "wrapped")
        wrapped.__doc__ = fn.__doc__
        return wrapped
    return deco
