"""
Model Retraining Loop per Feala's Closed-Loop Manifesto.

"Generate sequences → measure lab properties → retrain model → repeat"

This module implements continuous model improvement:
1. Collect new observations during experiments
2. Periodically retrain calibration models
3. Track model drift and performance
4. Trigger retraining when performance degrades

Design principle: The model should get smarter with every experiment.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from pathlib import Path
import json
import numpy as np


@dataclass
class RetrainingTrigger:
    """Conditions that trigger model retraining."""
    min_new_observations: int = 100          # Minimum new obs before retrain
    max_time_since_retrain_h: float = 168.0  # Max 1 week between retrains
    performance_degradation_threshold: float = 0.1  # Trigger if accuracy drops 10%
    calibration_error_threshold: float = 0.15      # Trigger if ECE > 15%


@dataclass
class ModelPerformanceMetrics:
    """Track model performance over time."""
    timestamp: str
    accuracy: float
    calibration_error: float  # Expected Calibration Error
    brier_score: float
    n_predictions: int
    n_correct: int


@dataclass
class RetrainingEvent:
    """Record of a model retraining."""
    timestamp: str
    trigger_reason: str
    n_training_examples: int
    performance_before: ModelPerformanceMetrics
    performance_after: ModelPerformanceMetrics
    improvement: float  # Accuracy improvement


class ModelRetrainingLoop:
    """
    Continuous model improvement loop.

    Monitors model performance and triggers retraining when needed.
    """

    def __init__(
        self,
        model_dir: Optional[Path] = None,
        triggers: Optional[RetrainingTrigger] = None
    ):
        self.model_dir = Path(model_dir) if model_dir else Path("results/models")
        self.model_dir.mkdir(parents=True, exist_ok=True)

        self.triggers = triggers or RetrainingTrigger()

        # Tracking state
        self.observations_since_retrain: List[Dict] = []
        self.last_retrain_time: Optional[datetime] = None
        self.performance_history: List[ModelPerformanceMetrics] = []
        self.retraining_events: List[RetrainingEvent] = []

        # Current model state
        self.current_model_version: int = 0
        self.current_model_accuracy: float = 0.0

    def record_prediction(
        self,
        features: Dict[str, float],
        predicted: str,
        confidence: float,
        actual: Optional[str] = None
    ):
        """Record a prediction for performance tracking."""
        self.observations_since_retrain.append({
            'timestamp': datetime.now().isoformat(),
            'features': features,
            'predicted': predicted,
            'confidence': confidence,
            'actual': actual,
            'correct': (predicted == actual) if actual else None
        })

    def should_retrain(self) -> Tuple[bool, str]:
        """
        Check if retraining should be triggered.

        Returns (should_retrain, reason).
        """
        # Check observation count
        if len(self.observations_since_retrain) >= self.triggers.min_new_observations:
            return True, f"Accumulated {len(self.observations_since_retrain)} new observations"

        # Check time since last retrain
        if self.last_retrain_time:
            hours_since = (datetime.now() - self.last_retrain_time).total_seconds() / 3600
            if hours_since >= self.triggers.max_time_since_retrain_h:
                return True, f"Time since retrain: {hours_since:.1f}h"

        # Check performance degradation
        recent_performance = self._compute_recent_performance()
        if recent_performance:
            if self.current_model_accuracy - recent_performance.accuracy > \
               self.triggers.performance_degradation_threshold:
                return True, f"Accuracy degraded from {self.current_model_accuracy:.2%} to {recent_performance.accuracy:.2%}"

            if recent_performance.calibration_error > self.triggers.calibration_error_threshold:
                return True, f"Calibration error {recent_performance.calibration_error:.2%} > threshold"

        return False, "No trigger condition met"

    def _compute_recent_performance(self) -> Optional[ModelPerformanceMetrics]:
        """Compute performance metrics from recent predictions."""
        # Filter to observations with ground truth
        labeled = [o for o in self.observations_since_retrain if o['actual'] is not None]

        if len(labeled) < 10:  # Need minimum observations
            return None

        n_correct = sum(1 for o in labeled if o['correct'])
        accuracy = n_correct / len(labeled)

        # Compute calibration error (simplified ECE)
        # Group by confidence bins and compare to actual accuracy
        bins = np.linspace(0, 1, 11)
        ece = 0.0
        for i in range(len(bins) - 1):
            bin_obs = [o for o in labeled if bins[i] <= o['confidence'] < bins[i+1]]
            if bin_obs:
                bin_acc = sum(1 for o in bin_obs if o['correct']) / len(bin_obs)
                bin_conf = np.mean([o['confidence'] for o in bin_obs])
                ece += abs(bin_acc - bin_conf) * len(bin_obs) / len(labeled)

        # Brier score
        brier = np.mean([
            (o['confidence'] - (1 if o['correct'] else 0)) ** 2
            for o in labeled
        ])

        return ModelPerformanceMetrics(
            timestamp=datetime.now().isoformat(),
            accuracy=accuracy,
            calibration_error=ece,
            brier_score=brier,
            n_predictions=len(labeled),
            n_correct=n_correct
        )

    def retrain(self, training_data: List[Dict]) -> RetrainingEvent:
        """
        Perform model retraining.

        Args:
            training_data: Full training dataset (historical + new)

        Returns:
            RetrainingEvent with performance comparison
        """
        # Capture performance before
        perf_before = self._compute_recent_performance() or ModelPerformanceMetrics(
            timestamp=datetime.now().isoformat(),
            accuracy=self.current_model_accuracy,
            calibration_error=0.0,
            brier_score=0.0,
            n_predictions=0,
            n_correct=0
        )

        # Perform retraining (placeholder - actual implementation depends on model)
        # In practice, this would call the calibrator's fit method
        new_accuracy = self._simulate_retrain(training_data)

        # Capture performance after (would need validation set in practice)
        perf_after = ModelPerformanceMetrics(
            timestamp=datetime.now().isoformat(),
            accuracy=new_accuracy,
            calibration_error=perf_before.calibration_error * 0.8,  # Assume improvement
            brier_score=perf_before.brier_score * 0.9,
            n_predictions=perf_before.n_predictions,
            n_correct=int(new_accuracy * perf_before.n_predictions)
        )

        # Create event
        event = RetrainingEvent(
            timestamp=datetime.now().isoformat(),
            trigger_reason="scheduled_retrain",
            n_training_examples=len(training_data),
            performance_before=perf_before,
            performance_after=perf_after,
            improvement=new_accuracy - perf_before.accuracy
        )

        # Update state
        self.current_model_version += 1
        self.current_model_accuracy = new_accuracy
        self.last_retrain_time = datetime.now()
        self.observations_since_retrain = []
        self.retraining_events.append(event)
        self.performance_history.append(perf_after)

        # Persist
        self._save_state()

        return event

    def _simulate_retrain(self, training_data: List[Dict]) -> float:
        """Simulate retraining (placeholder for actual ML)."""
        # In practice, this would:
        # 1. Split data into train/val
        # 2. Fit model on train
        # 3. Evaluate on val
        # 4. Return validation accuracy

        # Simulate improvement with more data
        base_accuracy = 0.7
        data_bonus = min(0.2, len(training_data) / 1000 * 0.2)
        return base_accuracy + data_bonus

    def _save_state(self):
        """Persist retraining state."""
        state = {
            'model_version': self.current_model_version,
            'model_accuracy': self.current_model_accuracy,
            'last_retrain': self.last_retrain_time.isoformat() if self.last_retrain_time else None,
            'n_retraining_events': len(self.retraining_events),
        }

        state_file = self.model_dir / "retraining_state.json"
        with open(state_file, 'w') as f:
            json.dump(state, f, indent=2)

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of retraining loop state."""
        return {
            'model_version': self.current_model_version,
            'current_accuracy': self.current_model_accuracy,
            'observations_pending': len(self.observations_since_retrain),
            'total_retraining_events': len(self.retraining_events),
            'last_retrain': self.last_retrain_time.isoformat() if self.last_retrain_time else None,
        }
