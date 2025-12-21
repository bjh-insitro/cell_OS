"""
Confidence Calibrator: Reality Layer

Maps belief state → P(correct).

NOT part of the inference layer. This is the outer epistemic contract that learns:
"Given that the posterior says X with confidence Y and nuisance is Z,
 how often is the prediction actually correct?"

This allows:
- 80% posterior + 53% nuisance → 52% calibrated confidence
- 60% posterior + 10% nuisance → 70% calibrated confidence

The inversion is not a bug. It's epistemic maturity.
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple, Literal
import numpy as np
import pickle
from pathlib import Path
from sklearn.linear_model import LogisticRegression
from sklearn.isotonic import IsotonicRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import brier_score_loss, log_loss

from .mechanism_posterior_v2 import MechanismPosterior, Mechanism


@dataclass
class BeliefState:
    """
    Complete belief state at decision point.

    Features used for calibration mapping.
    """
    top_probability: float
    margin: float  # top - second
    entropy: float

    # v1 feature (bookkeeping ratio: inflation_share_nonhetero)
    nuisance_fraction: float

    # v2 feature (observation-aware: P(NUISANCE | x))
    nuisance_probability: Optional[float] = None

    # Optional context features
    timepoint_h: Optional[float] = None
    dose_relative: Optional[float] = None
    viability: Optional[float] = None

    def to_feature_vector(
        self,
        include_context: bool = False,
        schema_version: Literal["v1", "v2"] = "v1",
    ) -> np.ndarray:
        """
        Convert to feature vector for calibration.

        v1: uses nuisance_fraction (bookkeeping ratio)
        v2: uses nuisance_probability (observation-aware)
        """
        if schema_version == "v1":
            nuisance_feat = self.nuisance_fraction
        elif schema_version == "v2":
            if self.nuisance_probability is None:
                raise ValueError("nuisance_probability is required for schema_version='v2'")
            nuisance_feat = self.nuisance_probability
        else:
            raise ValueError(f"Unknown schema_version: {schema_version}")

        features = [
            self.top_probability,
            self.margin,
            self.entropy,
            nuisance_feat,
        ]

        if include_context and self.timepoint_h is not None:
            features.extend([
                self.timepoint_h / 24.0,  # Normalize to typical experiment
                self.dose_relative if self.dose_relative is not None else 1.0,
                self.viability if self.viability is not None else 1.0,
            ])

        return np.array(features, dtype=float)


@dataclass
class CalibrationDatapoint:
    """Single observation for calibration training."""
    belief_state: BeliefState
    predicted_mechanism: Mechanism
    true_mechanism: Mechanism

    @property
    def correct(self) -> bool:
        return self.predicted_mechanism == self.true_mechanism

    @property
    def nuisance_bin(self) -> str:
        """Stratification bin by nuisance level."""
        # Prefer v2 nuisance_probability when available
        nf = (
            self.belief_state.nuisance_probability
            if self.belief_state.nuisance_probability is not None
            else self.belief_state.nuisance_fraction
        )

        if nf < 0.3:
            return "low_nuisance"
        elif nf < 0.5:
            return "medium_nuisance"
        else:
            return "high_nuisance"


class ConfidenceCalibrator:
    """
    Learns P(correct | belief_state).

    Frozen after training. Treat like labware.
    """

    def __init__(self, method: str = 'platt', include_context: bool = False, schema_version: str = "v1"):
        """
        Args:
            method: 'platt' (logistic regression) or 'isotonic'
            include_context: Include timepoint, dose, viability as features
            schema_version: 'v1' (nuisance_fraction) or 'v2' (nuisance_probability)
        """
        self.method = method
        self.include_context = include_context
        self.schema_version = schema_version
        self.calibrator = None
        self.training_stats = {}
        self.frozen = False

    def collect_training_data(
        self,
        posteriors: List[MechanismPosterior],
        ground_truths: List[Mechanism],
        belief_states: List[BeliefState]
    ) -> List[CalibrationDatapoint]:
        """
        Convert posterior + ground truth pairs to calibration datapoints.

        Args:
            posteriors: List of mechanism posteriors
            ground_truths: True mechanisms
            belief_states: Complete belief states (with nuisance, timepoint, etc)

        Returns:
            List of CalibrationDatapoint objects
        """
        assert len(posteriors) == len(ground_truths) == len(belief_states)

        datapoints = []
        for post, truth, belief in zip(posteriors, ground_truths, belief_states):
            datapoints.append(CalibrationDatapoint(
                belief_state=belief,
                predicted_mechanism=post.top_mechanism,
                true_mechanism=truth
            ))

        return datapoints

    def stratified_split(
        self,
        datapoints: List[CalibrationDatapoint],
        test_fraction: float = 0.2
    ) -> Tuple[List[CalibrationDatapoint], List[CalibrationDatapoint]]:
        """
        Stratified split by nuisance level.

        Ensures train/test both have low/medium/high nuisance cases.
        """
        # Group by nuisance bin
        bins = {'low_nuisance': [], 'medium_nuisance': [], 'high_nuisance': []}
        for dp in datapoints:
            bins[dp.nuisance_bin].append(dp)

        train = []
        test = []

        for bin_name, bin_data in bins.items():
            n_test = int(len(bin_data) * test_fraction)
            rng = np.random.default_rng(42)
            indices = rng.permutation(len(bin_data))

            test_indices = indices[:n_test]
            train_indices = indices[n_test:]

            test.extend([bin_data[i] for i in test_indices])
            train.extend([bin_data[i] for i in train_indices])

        return train, test

    def train(
        self,
        datapoints: List[CalibrationDatapoint],
        verbose: bool = True
    ):
        """
        Train calibrator on collected data.

        IMPORTANT: Stratify deliberately to avoid IID-only training.
        """
        if self.frozen:
            raise RuntimeError("Calibrator is frozen. Create new instance to retrain.")

        if verbose:
            print("="*80)
            print("CALIBRATOR TRAINING")
            print("="*80)
            print(f"Method: {self.method}")
            print(f"Include context: {self.include_context}")
            print(f"Total datapoints: {len(datapoints)}")

        # Check nuisance stratification
        bins = {'low_nuisance': 0, 'medium_nuisance': 0, 'high_nuisance': 0}
        for dp in datapoints:
            bins[dp.nuisance_bin] += 1

        if verbose:
            print(f"\nNuisance stratification:")
            for bin_name, count in bins.items():
                pct = 100 * count / len(datapoints)
                print(f"  {bin_name}: {count} ({pct:.1f}%)")

        # Extract features and labels
        X = np.array([dp.belief_state.to_feature_vector(self.include_context)
                      for dp in datapoints])
        y = np.array([1.0 if dp.correct else 0.0 for dp in datapoints])

        if verbose:
            print(f"\nAccuracy (before calibration): {y.mean():.3f}")
            print(f"Feature matrix shape: {X.shape}")

        # Train calibrator
        if self.method == 'platt':
            self.calibrator = LogisticRegression(max_iter=1000)
            self.calibrator.fit(X, y)

            if verbose and hasattr(self.calibrator, 'coef_'):
                print(f"\nLogistic regression coefficients:")
                feature_names = ['top_prob', 'margin', 'entropy', 'nuisance_frac']
                if self.include_context:
                    feature_names.extend(['timepoint', 'dose', 'viability'])
                for name, coef in zip(feature_names, self.calibrator.coef_[0]):
                    print(f"  {name}: {coef:+.3f}")

        elif self.method == 'isotonic':
            # Isotonic regression on top_probability only
            self.calibrator = IsotonicRegression(out_of_bounds='clip')
            self.calibrator.fit(X[:, 0], y)  # Use only top_prob

        else:
            raise ValueError(f"Unknown method: {self.method}")

        # Compute training stats
        y_pred = self.predict_confidence_batch(
            [dp.belief_state for dp in datapoints]
        )

        brier = brier_score_loss(y, y_pred)
        logloss = log_loss(y, y_pred)

        self.training_stats = {
            'n_samples': len(datapoints),
            'accuracy': float(y.mean()),
            'brier_score': float(brier),
            'log_loss': float(logloss),
            'nuisance_bins': bins
        }

        if verbose:
            print(f"\nTraining metrics:")
            print(f"  Brier score: {brier:.4f}")
            print(f"  Log loss: {logloss:.4f}")

        return self.training_stats

    def evaluate_stratified(
        self,
        datapoints: List[CalibrationDatapoint],
        verbose: bool = True
    ) -> Dict[str, Dict[str, float]]:
        """
        Evaluate calibration metrics stratified by nuisance level.

        Critical: Check that high-nuisance bins are conservative.
        """
        if self.calibrator is None:
            raise RuntimeError("Calibrator not trained")

        # Group by nuisance bin
        bins = {'low_nuisance': [], 'medium_nuisance': [], 'high_nuisance': []}
        for dp in datapoints:
            bins[dp.nuisance_bin].append(dp)

        results = {}

        for bin_name, bin_data in bins.items():
            if len(bin_data) == 0:
                continue

            X = np.array([dp.belief_state.to_feature_vector(self.include_context)
                          for dp in bin_data])
            y_true = np.array([1.0 if dp.correct else 0.0 for dp in bin_data])
            y_pred = self.predict_confidence_batch(
                [dp.belief_state for dp in bin_data]
            )

            # Compute metrics
            accuracy = y_true.mean()
            mean_confidence = y_pred.mean()
            brier = brier_score_loss(y_true, y_pred)

            # Expected Calibration Error (ECE) - simplified
            # Bin by predicted confidence, compare mean pred to mean accuracy
            n_bins = 5
            ece = 0.0
            for i in range(n_bins):
                bin_lower = i / n_bins
                bin_upper = (i + 1) / n_bins
                mask = (y_pred >= bin_lower) & (y_pred < bin_upper)

                if mask.sum() > 0:
                    bin_acc = y_true[mask].mean()
                    bin_conf = y_pred[mask].mean()
                    bin_weight = mask.sum() / len(y_pred)
                    ece += bin_weight * abs(bin_conf - bin_acc)

            results[bin_name] = {
                'n_samples': len(bin_data),
                'accuracy': float(accuracy),
                'mean_confidence': float(mean_confidence),
                'brier_score': float(brier),
                'ece': float(ece),
                'overconfident': mean_confidence > accuracy + 0.05
            }

        if verbose:
            print("\n" + "="*80)
            print("STRATIFIED CALIBRATION METRICS")
            print("="*80)
            for bin_name, metrics in results.items():
                print(f"\n{bin_name.upper()}:")
                print(f"  Samples: {metrics['n_samples']}")
                print(f"  Accuracy: {metrics['accuracy']:.3f}")
                print(f"  Mean confidence: {metrics['mean_confidence']:.3f}")
                print(f"  Brier score: {metrics['brier_score']:.4f}")
                print(f"  ECE: {metrics['ece']:.4f}")

                if metrics['overconfident']:
                    print(f"  ⚠ OVERCONFIDENT (conf > acc + 0.05)")

        return results

    def predict_confidence(self, belief_state: BeliefState) -> float:
        """
        Predict P(correct | belief_state).

        This is the calibrated confidence, NOT the posterior probability.
        """
        if self.calibrator is None:
            raise RuntimeError("Calibrator not trained")

        X = belief_state.to_feature_vector(
            include_context=self.include_context,
            schema_version=getattr(self, "schema_version", "v1"),
        ).reshape(1, -1)

        if self.method == 'platt':
            # Logistic regression returns probabilities
            conf = self.calibrator.predict_proba(X)[0, 1]
        elif self.method == 'isotonic':
            # Isotonic returns calibrated probabilities
            conf = self.calibrator.predict(X[0, 0:1])[0]
        else:
            raise ValueError(f"Unknown method: {self.method}")

        return float(np.clip(conf, 0.0, 1.0))

    def predict_confidence_batch(self, belief_states: List[BeliefState]) -> np.ndarray:
        """Batch version of predict_confidence."""
        return np.array([self.predict_confidence(bs) for bs in belief_states])

    def freeze(self):
        """Freeze calibrator. No more training allowed."""
        self.frozen = True

    def save(self, path: str):
        """Save calibrator to disk."""
        data = {
            'method': self.method,
            'include_context': self.include_context,
            'schema_version': self.schema_version,
            'calibrator': self.calibrator,
            'training_stats': self.training_stats,
            'frozen': self.frozen
        }
        with open(path, 'wb') as f:
            pickle.dump(data, f)
        print(f"Calibrator saved to {path}")

    @classmethod
    def load(cls, path: str) -> 'ConfidenceCalibrator':
        """Load calibrator from disk."""
        with open(path, 'rb') as f:
            data = pickle.load(f)

        calibrator = cls(
            method=data['method'],
            include_context=data['include_context'],
            schema_version=data.get('schema_version', 'v1')  # Default to v1 for old models
        )
        calibrator.calibrator = data['calibrator']
        calibrator.training_stats = data['training_stats']
        calibrator.frozen = data['frozen']

        # Suppress verbose loading message (called frequently during beam search)
        # print(f"Calibrator loaded from {path}")
        return calibrator


def reliability_diagram(
    datapoints: List[CalibrationDatapoint],
    calibrator: ConfidenceCalibrator,
    n_bins: int = 10
) -> Dict[str, np.ndarray]:
    """
    Compute reliability diagram data.

    Returns:
        bin_centers: Predicted confidence bin centers
        bin_accuracies: Actual accuracy per bin
        bin_counts: Number of samples per bin
    """
    y_true = np.array([1.0 if dp.correct else 0.0 for dp in datapoints])
    y_pred = calibrator.predict_confidence_batch([dp.belief_state for dp in datapoints])

    bin_edges = np.linspace(0, 1, n_bins + 1)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
    bin_accuracies = []
    bin_counts = []

    for i in range(n_bins):
        mask = (y_pred >= bin_edges[i]) & (y_pred < bin_edges[i + 1])

        if mask.sum() > 0:
            bin_accuracies.append(y_true[mask].mean())
            bin_counts.append(mask.sum())
        else:
            bin_accuracies.append(0.0)
            bin_counts.append(0)

    return {
        'bin_centers': bin_centers,
        'bin_accuracies': np.array(bin_accuracies),
        'bin_counts': np.array(bin_counts)
    }
