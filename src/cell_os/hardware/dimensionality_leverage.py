"""
Dimensionality Leverage per Feala's Closed-Loop Manifesto.

"High-dimensional control spaces become easier algorithmically than
intuitive reasoning predicts. The 'curse of dimensionality' is actually
an opportunity when coupled with fast feedback."

This module implements:
1. High-dimensional action space exploration
2. Random search baseline (surprisingly effective in high-D)
3. Evolutionary strategies for continuous optimization
4. Dimensionality analysis tools

Key insight: More knobs = more paths to objectives.
"""

from dataclasses import dataclass
from typing import List, Callable, Optional, Tuple, Dict, Any
import numpy as np
from enum import Enum


class SearchStrategy(str, Enum):
    """High-dimensional search strategies."""
    RANDOM = "random"           # Pure random sampling
    EVOLUTIONARY = "evolutionary"  # CMA-ES style
    BAYESIAN = "bayesian"       # Gaussian process
    GRID = "grid"               # Low-D only


@dataclass
class ActionDimension:
    """Single dimension in the action space."""
    name: str
    min_val: float
    max_val: float
    discrete_values: Optional[List[float]] = None  # If discrete
    log_scale: bool = False  # For dose-like parameters

    @property
    def is_discrete(self) -> bool:
        return self.discrete_values is not None

    def sample_random(self, rng: np.random.Generator) -> float:
        """Sample random value in this dimension."""
        if self.is_discrete:
            return rng.choice(self.discrete_values)
        elif self.log_scale:
            log_min = np.log10(max(self.min_val, 1e-10))
            log_max = np.log10(self.max_val)
            return 10 ** rng.uniform(log_min, log_max)
        else:
            return rng.uniform(self.min_val, self.max_val)

    def sample_gaussian(self, mean: float, std: float, rng: np.random.Generator) -> float:
        """Sample from Gaussian, clipped to bounds."""
        if self.is_discrete:
            # Find closest discrete value to Gaussian sample
            sample = rng.normal(mean, std)
            return min(self.discrete_values, key=lambda x: abs(x - sample))
        else:
            sample = rng.normal(mean, std)
            return np.clip(sample, self.min_val, self.max_val)


@dataclass
class HighDimActionSpace:
    """
    High-dimensional action space.

    Per Feala: More dimensions = more paths to objectives.
    """
    dimensions: List[ActionDimension]

    @property
    def n_dims(self) -> int:
        return len(self.dimensions)

    @property
    def dim_names(self) -> List[str]:
        return [d.name for d in self.dimensions]

    def sample_random(self, n: int = 1, seed: int = 42) -> np.ndarray:
        """Sample n random points in action space."""
        rng = np.random.default_rng(seed)
        samples = np.zeros((n, self.n_dims))

        for i in range(n):
            for j, dim in enumerate(self.dimensions):
                samples[i, j] = dim.sample_random(rng)

        return samples

    def to_dict(self, point: np.ndarray) -> Dict[str, float]:
        """Convert point array to named dict."""
        return {dim.name: point[i] for i, dim in enumerate(self.dimensions)}

    @classmethod
    def from_expanded_action(cls) -> 'HighDimActionSpace':
        """Create action space from ExpandedAction parameters."""
        return cls(dimensions=[
            # Primary treatment
            ActionDimension("dose_fraction", 0.0, 1.0, [0.0, 0.25, 0.5, 1.0]),
            ActionDimension("washout", 0.0, 1.0, [0.0, 1.0]),
            ActionDimension("feed", 0.0, 1.0, [0.0, 1.0]),
            # Environmental
            ActionDimension("temperature_c", 30.0, 42.0),
            ActionDimension("oxygen_pct", 1.0, 40.0, log_scale=True),
            ActionDimension("serum_pct", 0.5, 20.0),
            # Temporal
            ActionDimension("pulse_duration_h", 0.5, 24.0),
            ActionDimension("recovery_time_h", 0.0, 24.0),
            # Secondary compound
            ActionDimension("secondary_dose_um", 0.0, 100.0, log_scale=True),
        ])


class RandomSearchOptimizer:
    """
    Random search optimizer for high-dimensional spaces.

    Per Feala: Random search is surprisingly effective in high-D
    because it explores more uniformly than grid search.
    """

    def __init__(
        self,
        action_space: HighDimActionSpace,
        objective_fn: Callable[[np.ndarray], float],
        seed: int = 42
    ):
        self.action_space = action_space
        self.objective_fn = objective_fn
        self.rng = np.random.default_rng(seed)

        self.best_point = None
        self.best_score = float('-inf')
        self.history: List[Tuple[np.ndarray, float]] = []

    def optimize(self, n_iterations: int = 100) -> Tuple[np.ndarray, float]:
        """Run random search optimization."""
        for _ in range(n_iterations):
            # Sample random point
            point = self.action_space.sample_random(n=1, seed=self.rng.integers(1e9))[0]

            # Evaluate
            score = self.objective_fn(point)
            self.history.append((point.copy(), score))

            # Update best
            if score > self.best_score:
                self.best_score = score
                self.best_point = point.copy()

        return self.best_point, self.best_score


class EvolutionaryOptimizer:
    """
    Evolutionary strategies optimizer (CMA-ES inspired).

    Better than random for exploiting promising regions.
    """

    def __init__(
        self,
        action_space: HighDimActionSpace,
        objective_fn: Callable[[np.ndarray], float],
        population_size: int = 20,
        seed: int = 42
    ):
        self.action_space = action_space
        self.objective_fn = objective_fn
        self.population_size = population_size
        self.rng = np.random.default_rng(seed)

        # Initialize population parameters
        self.mean = np.array([
            (d.max_val + d.min_val) / 2 for d in action_space.dimensions
        ])
        self.sigma = 0.3  # Step size

        self.best_point = None
        self.best_score = float('-inf')
        self.generation = 0

    def step(self) -> Tuple[np.ndarray, float]:
        """Run one generation of evolution."""
        n_dims = self.action_space.n_dims

        # Generate population
        population = []
        scores = []

        for _ in range(self.population_size):
            # Sample from Gaussian around mean
            point = np.zeros(n_dims)
            for j, dim in enumerate(self.action_space.dimensions):
                point[j] = dim.sample_gaussian(
                    self.mean[j], self.sigma * (dim.max_val - dim.min_val),
                    self.rng
                )

            score = self.objective_fn(point)
            population.append(point)
            scores.append(score)

            if score > self.best_score:
                self.best_score = score
                self.best_point = point.copy()

        # Select top half
        indices = np.argsort(scores)[::-1][:self.population_size // 2]
        elite = [population[i] for i in indices]

        # Update mean (recombination)
        self.mean = np.mean(elite, axis=0)

        self.generation += 1
        return self.best_point, self.best_score

    def optimize(self, n_generations: int = 50) -> Tuple[np.ndarray, float]:
        """Run full optimization."""
        for _ in range(n_generations):
            self.step()
        return self.best_point, self.best_score


@dataclass
class DimensionalityAnalysis:
    """Analysis of how dimensionality affects optimization."""
    n_dims: int
    n_evaluations: int
    best_score: float
    mean_score: float
    std_score: float

    # Feala's insight: higher dims can be easier
    effective_dimensionality: float  # Estimated from gradient variance


def analyze_dimensionality_effect(
    objective_fn: Callable[[np.ndarray], float],
    max_dims: int = 10,
    n_samples: int = 100,
    seed: int = 42
) -> List[DimensionalityAnalysis]:
    """
    Analyze how adding dimensions affects optimization.

    Tests Feala's hypothesis that more dimensions = more paths.
    """
    results = []
    rng = np.random.default_rng(seed)

    for n_dims in range(1, max_dims + 1):
        # Create action space with n_dims
        dims = [
            ActionDimension(f"dim_{i}", 0.0, 1.0)
            for i in range(n_dims)
        ]
        space = HighDimActionSpace(dims)

        # Random search
        scores = []
        for _ in range(n_samples):
            point = space.sample_random(n=1, seed=rng.integers(1e9))[0]
            # Pad to max_dims for consistent objective
            padded = np.zeros(max_dims)
            padded[:n_dims] = point
            score = objective_fn(padded)
            scores.append(score)

        results.append(DimensionalityAnalysis(
            n_dims=n_dims,
            n_evaluations=n_samples,
            best_score=max(scores),
            mean_score=np.mean(scores),
            std_score=np.std(scores),
            effective_dimensionality=n_dims  # Would need gradient analysis
        ))

    return results


def demonstrate_curse_is_blessing():
    """
    Demonstrate that high dimensionality helps optimization.

    The 'curse' becomes a blessing with enough samples.
    """
    # Objective: find any point above threshold (easier in high-D)
    threshold = 0.8

    def objective(x: np.ndarray) -> float:
        # Success if ANY dimension > threshold
        return 1.0 if np.any(x > threshold) else 0.0

    results = analyze_dimensionality_effect(objective, max_dims=10, n_samples=100)

    print("Dimensionality vs Success Rate")
    print("=" * 40)
    for r in results:
        print(f"D={r.n_dims:2d}: success_rate={r.mean_score:.1%}, best={r.best_score}")

    # Key insight: success rate increases with dimensions!
    return results
