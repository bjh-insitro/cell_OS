"""
Loop timing instrumentation for closed-loop optimization.

Per Feala's Closed-Loop Manifesto: "Shrinking loop times by orders of magnitude"
We can't optimize what we don't measure.

This module tracks per-cycle timing breakdown to identify bottlenecks.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict
import time
from contextlib import contextmanager


@dataclass
class CycleTiming:
    """Per-cycle timing breakdown."""
    cycle: int

    # Phase timing (in seconds)
    proposal_time: float = 0.0      # Agent thinking time
    execution_time: float = 0.0     # World simulation time
    observation_time: float = 0.0   # Data aggregation time
    belief_update_time: float = 0.0 # Learning step time
    logging_time: float = 0.0       # I/O overhead

    # Total
    total_cycle_time: float = 0.0

    # Metadata
    wells_processed: int = 0

    @property
    def bottleneck(self) -> str:
        """Identify the slowest phase."""
        times = {
            'proposal': self.proposal_time,
            'execution': self.execution_time,
            'observation': self.observation_time,
            'belief_update': self.belief_update_time,
            'logging': self.logging_time,
        }
        return max(times, key=times.get)

    @property
    def throughput_wells_per_sec(self) -> float:
        """Wells processed per second."""
        if self.total_cycle_time > 0:
            return self.wells_processed / self.total_cycle_time
        return 0.0

    def to_dict(self) -> Dict:
        return {
            'cycle': self.cycle,
            'proposal_time': self.proposal_time,
            'execution_time': self.execution_time,
            'observation_time': self.observation_time,
            'belief_update_time': self.belief_update_time,
            'logging_time': self.logging_time,
            'total_cycle_time': self.total_cycle_time,
            'wells_processed': self.wells_processed,
            'bottleneck': self.bottleneck,
            'throughput_wells_per_sec': self.throughput_wells_per_sec,
        }


@dataclass
class LoopTimingStats:
    """Aggregate timing statistics across all cycles.

    Key metric from Feala: bits_per_hour (learning rate per wall-clock time)
    """
    cycle_timings: List[CycleTiming] = field(default_factory=list)

    # Aggregate metrics
    total_wall_clock_sec: float = 0.0
    total_wells_processed: int = 0
    total_bits_learned: float = 0.0

    @property
    def mean_cycle_time(self) -> float:
        if not self.cycle_timings:
            return 0.0
        return sum(c.total_cycle_time for c in self.cycle_timings) / len(self.cycle_timings)

    @property
    def bottleneck_distribution(self) -> Dict[str, int]:
        """Count how often each phase was the bottleneck."""
        dist = {'proposal': 0, 'execution': 0, 'observation': 0, 'belief_update': 0, 'logging': 0}
        for ct in self.cycle_timings:
            dist[ct.bottleneck] += 1
        return dist

    @property
    def primary_bottleneck(self) -> str:
        """Most common bottleneck across all cycles."""
        dist = self.bottleneck_distribution
        return max(dist, key=dist.get) if dist else 'unknown'

    @property
    def bits_per_hour(self) -> float:
        """Key Feala metric: learning rate per wall-clock time."""
        hours = self.total_wall_clock_sec / 3600
        if hours > 0:
            return self.total_bits_learned / hours
        return 0.0

    @property
    def bits_per_plate(self) -> float:
        """Efficiency metric: bits per 96-well plate equivalent."""
        plates = self.total_wells_processed / 96.0
        if plates > 0:
            return self.total_bits_learned / plates
        return 0.0

    @property
    def wells_per_second(self) -> float:
        """Throughput metric."""
        if self.total_wall_clock_sec > 0:
            return self.total_wells_processed / self.total_wall_clock_sec
        return 0.0

    def add_cycle(self, timing: CycleTiming):
        """Add a cycle's timing data."""
        self.cycle_timings.append(timing)
        self.total_wall_clock_sec += timing.total_cycle_time
        self.total_wells_processed += timing.wells_processed

    def set_bits_learned(self, bits: float):
        """Set total bits learned (from episode summary)."""
        self.total_bits_learned = bits

    def summary(self) -> Dict:
        """Summary for logging/display."""
        return {
            'cycles': len(self.cycle_timings),
            'total_wall_clock_sec': self.total_wall_clock_sec,
            'mean_cycle_time_sec': self.mean_cycle_time,
            'total_wells_processed': self.total_wells_processed,
            'total_bits_learned': self.total_bits_learned,
            'bits_per_hour': self.bits_per_hour,
            'bits_per_plate': self.bits_per_plate,
            'wells_per_second': self.wells_per_second,
            'primary_bottleneck': self.primary_bottleneck,
            'bottleneck_distribution': self.bottleneck_distribution,
        }

    def format_summary(self) -> str:
        """Human-readable summary."""
        s = self.summary()
        lines = [
            "LOOP TIMING SUMMARY (Feala Metrics)",
            "=" * 40,
            f"Cycles: {s['cycles']}",
            f"Total wall clock: {s['total_wall_clock_sec']:.2f}s",
            f"Mean cycle time: {s['mean_cycle_time_sec']:.3f}s",
            f"Wells processed: {s['total_wells_processed']}",
            f"Throughput: {s['wells_per_second']:.1f} wells/sec",
            "",
            "LEARNING EFFICIENCY",
            f"Bits learned: {s['total_bits_learned']:.2f}",
            f"Bits per plate: {s['bits_per_plate']:.3f}",
            f"Bits per hour: {s['bits_per_hour']:.2f}",
            "",
            "BOTTLENECK ANALYSIS",
            f"Primary bottleneck: {s['primary_bottleneck']}",
        ]
        for phase, count in s['bottleneck_distribution'].items():
            if count > 0:
                lines.append(f"  {phase}: {count} cycles")
        return "\n".join(lines)


class LoopTimer:
    """Context manager for timing loop phases."""

    def __init__(self):
        self.stats = LoopTimingStats()
        self._current_cycle: Optional[CycleTiming] = None
        self._phase_start: float = 0.0

    def start_cycle(self, cycle: int):
        """Begin timing a new cycle."""
        self._current_cycle = CycleTiming(cycle=cycle)
        self._cycle_start = time.perf_counter()

    @contextmanager
    def phase(self, name: str):
        """Time a specific phase within the cycle."""
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed = time.perf_counter() - start
            if self._current_cycle:
                if name == 'proposal':
                    self._current_cycle.proposal_time = elapsed
                elif name == 'execution':
                    self._current_cycle.execution_time = elapsed
                elif name == 'observation':
                    self._current_cycle.observation_time = elapsed
                elif name == 'belief_update':
                    self._current_cycle.belief_update_time = elapsed
                elif name == 'logging':
                    self._current_cycle.logging_time = elapsed

    def end_cycle(self, wells_processed: int = 0):
        """Finish timing the current cycle."""
        if self._current_cycle:
            self._current_cycle.total_cycle_time = time.perf_counter() - self._cycle_start
            self._current_cycle.wells_processed = wells_processed
            self.stats.add_cycle(self._current_cycle)
            self._current_cycle = None

    def get_current_cycle_timing(self) -> Optional[CycleTiming]:
        """Get timing for current cycle (for logging mid-cycle)."""
        return self._current_cycle
