"""
Boundary Model - Decision Boundaries with Batch Normalization

Decision boundary in embedding space with explicit batch normalization.
Handles additive drift via batch-relative embeddings.
"""

import numpy as np
from typing import List, Dict, Literal
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import cross_val_score
import logging

from .types import WellRecord, BatchFrame

logger = logging.getLogger(__name__)


class BoundaryModel:
    """
    Decision boundary in embedding space with explicit batch normalization.

    Handles additive drift via batch-relative embeddings.
    """

    def __init__(
        self,
        name: str,
        classes: List[str],
        model_type: Literal["logistic", "svm"] = "logistic"
    ):
        self.name = name
        self.classes = classes
        self.model_type = model_type
        self.model = None
        self.scaler = StandardScaler()
        self.is_fitted = False

    def _batch_normalize(
        self,
        wells: List[WellRecord],
        batch_frames: Dict[str, BatchFrame]
    ) -> np.ndarray:
        """
        Apply batch normalization: z' = z - vehicle_mu(batch).

        This annihilates additive drift.
        """
        normalized_embeddings = []

        for well in wells:
            if well.batch_id not in batch_frames:
                logger.warning(f"No batch frame for {well.batch_id}, using raw embedding")
                normalized_embeddings.append(well.embedding)
                continue

            batch_frame = batch_frames[well.batch_id]
            z_normalized = well.embedding - batch_frame.vehicle_mu
            normalized_embeddings.append(z_normalized)

        return np.array(normalized_embeddings)

    def fit(
        self,
        wells: List[WellRecord],
        labels: np.ndarray,
        batch_frames: Dict[str, BatchFrame]
    ) -> None:
        """
        Fit boundary model on batch-normalized embeddings.

        Args:
            wells: Training wells with embeddings
            labels: Ground truth labels (indices into self.classes)
            batch_frames: Per-batch normalization frames
        """
        # Batch normalize
        X = self._batch_normalize(wells, batch_frames)

        # Scale (after batch norm, for numerical stability)
        X_scaled = self.scaler.fit_transform(X)

        # Fit model
        if self.model_type == "logistic":
            self.model = LogisticRegression(
                multi_class='multinomial' if len(self.classes) > 2 else 'auto',
                max_iter=1000,
                random_state=42
            )
        else:
            raise NotImplementedError(f"Model type {self.model_type} not implemented")

        self.model.fit(X_scaled, labels)
        self.is_fitted = True

        # Log cross-validation accuracy
        cv_scores = cross_val_score(self.model, X_scaled, labels, cv=min(5, len(X)))
        logger.info(f"{self.name} model fitted. CV accuracy: {cv_scores.mean():.3f} ± {cv_scores.std():.3f}")

    def predict_proba(
        self,
        wells: List[WellRecord],
        batch_frames: Dict[str, BatchFrame]
    ) -> np.ndarray:
        """
        Predict class probabilities.

        Returns: shape (n_wells, n_classes)
        """
        if not self.is_fitted:
            raise ValueError("Model not fitted")

        X = self._batch_normalize(wells, batch_frames)
        X_scaled = self.scaler.transform(X)

        return self.model.predict_proba(X_scaled)

    def uncertainty(
        self,
        wells: List[WellRecord],
        batch_frames: Dict[str, BatchFrame]
    ) -> np.ndarray:
        """
        Compute per-well uncertainty as predictive entropy.

        Returns: shape (n_wells,)
        """
        proba = self.predict_proba(wells, batch_frames)

        # Shannon entropy: H = -sum(p * log(p))
        entropy = -np.sum(proba * np.log(proba + 1e-10), axis=1)

        return entropy
