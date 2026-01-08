"""
Calibrator Retraining Integration.

Connects the DataEngine, ModelRetrainingLoop, and ConfidenceCalibrator
for continuous model improvement per Feala's manifesto.
"""

from typing import List, Optional, Dict, Any, Tuple
from pathlib import Path
from datetime import datetime
import json
import pickle

from .data_engine import DataEngine, ObservationRecord
from .model_retraining import ModelRetrainingLoop, RetrainingTrigger


class CalibratorRetrainingIntegration:
    """
    Integrates data engine with calibrator retraining.

    Flow:
    1. DataEngine accumulates observations
    2. ModelRetrainingLoop monitors performance
    3. When triggered, retrain ConfidenceCalibrator
    4. Save new model version
    """

    def __init__(
        self,
        data_engine: DataEngine,
        model_dir: Optional[Path] = None,
        triggers: Optional[RetrainingTrigger] = None
    ):
        self.data_engine = data_engine
        self.model_dir = Path(model_dir) if model_dir else Path("results/models")
        self.model_dir.mkdir(parents=True, exist_ok=True)

        self.retraining_loop = ModelRetrainingLoop(
            model_dir=self.model_dir,
            triggers=triggers
        )

        self.current_calibrator = None
        self.calibrator_version = 0

    def record_prediction(
        self,
        run_id: str,
        cycle: int,
        cell_line: str,
        compound: str,
        dose_um: float,
        time_h: float,
        viability: float,
        morphology_mean: float,
        morphology_std: float,
        predicted_mechanism: str,
        confidence: float,
        true_mechanism: Optional[str] = None
    ):
        """Record a prediction and its outcome."""
        # Record in data engine
        obs = ObservationRecord(
            run_id=run_id,
            cycle=cycle,
            timestamp=datetime.now().isoformat(),
            cell_line=cell_line,
            compound=compound,
            dose_um=dose_um,
            time_h=time_h,
            viability=viability,
            morphology_mean=morphology_mean,
            morphology_std=morphology_std,
            predicted_mechanism=predicted_mechanism,
            mechanism_confidence=confidence,
            true_mechanism=true_mechanism
        )
        self.data_engine.record_observation(obs)

        # Record in retraining loop for performance tracking
        features = {
            'dose_um': dose_um,
            'time_h': time_h,
            'viability': viability,
            'morphology_mean': morphology_mean
        }
        self.retraining_loop.record_prediction(
            features=features,
            predicted=predicted_mechanism,
            confidence=confidence,
            actual=true_mechanism
        )

    def check_and_retrain(self) -> Optional[Dict[str, Any]]:
        """
        Check if retraining is needed and perform if so.

        Returns retraining event dict if retrained, None otherwise.
        """
        should_retrain, reason = self.retraining_loop.should_retrain()

        if not should_retrain:
            return None

        # Get all training data from data engine
        training_data = self._get_training_data()

        if len(training_data) < 50:
            return None  # Not enough data

        # Perform retraining
        event = self.retraining_loop.retrain(training_data)

        # Update calibrator version
        self.calibrator_version += 1

        return {
            'version': self.calibrator_version,
            'reason': reason,
            'n_training_examples': len(training_data),
            'improvement': event.improvement
        }

    def _get_training_data(self) -> List[Dict]:
        """Extract training data from data engine."""
        # Query all observations with ground truth
        training_data = []

        with self.data_engine._get_conn() as conn:
            cursor = conn.execute("""
                SELECT cell_line, compound, dose_um, time_h, viability,
                       morphology_mean, morphology_std, predicted_mechanism,
                       mechanism_confidence, true_mechanism
                FROM observations
                WHERE true_mechanism IS NOT NULL
            """)

            for row in cursor:
                training_data.append({
                    'cell_line': row[0],
                    'compound': row[1],
                    'dose_um': row[2],
                    'time_h': row[3],
                    'viability': row[4],
                    'morphology_mean': row[5],
                    'morphology_std': row[6],
                    'predicted': row[7],
                    'confidence': row[8],
                    'actual': row[9]
                })

        return training_data

    def get_status(self) -> Dict[str, Any]:
        """Get current status of retraining integration."""
        return {
            'calibrator_version': self.calibrator_version,
            'data_engine_stats': self.data_engine.get_stats(),
            'retraining_status': self.retraining_loop.get_summary()
        }
