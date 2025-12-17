"""
Predictive Modeling for Mechanism Discovery

Tests if morphology signatures encode generalizable biological mechanisms through:
1. Stress axis classification from morphology
2. Compound generalization (leave-compounds-out CV)
3. Within-class transfer (train on tBHQ, test on H2O2)
4. Dose interpolation
5. Cell-line transfer
"""

import numpy as np
import pandas as pd
import logging
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, confusion_matrix, classification_report
from sklearn.model_selection import cross_val_score
import sqlite3

logger = logging.getLogger(__name__)


@dataclass
class ExperimentData:
    """Container for experimental data."""
    X: np.ndarray  # Features (N x 5): ER, mito, nucleus, actin, RNA
    y: np.ndarray  # Labels: stress axis
    metadata: pd.DataFrame  # Full metadata for each sample

    def __len__(self):
        return len(self.X)


class MorphologyClassifier:
    """
    Trains classifiers to predict stress axis from Cell Painting morphology.

    Tests if morphology signatures encode generalizable mechanism.
    """

    def __init__(self, db_path: str = "data/cell_thalamus.db"):
        self.db_path = db_path
        self.scaler = StandardScaler()
        self.model = None

        # Compound-to-stress-axis mapping
        self.stress_class_map = {
            'tBHQ': 'oxidative',
            'H2O2': 'oxidative',
            'tunicamycin': 'er_stress',
            'thapsigargin': 'er_stress',
            'CCCP': 'mitochondrial',
            'oligomycin': 'mitochondrial',
            'etoposide': 'dna_damage',
            'MG132': 'proteasome',
            'nocodazole': 'microtubule',
            'paclitaxel': 'microtubule',
            'DMSO': 'vehicle'
        }

    def load_data(self,
                  compounds: Optional[List[str]] = None,
                  cell_lines: Optional[List[str]] = None,
                  dose_range: Optional[Tuple[float, float]] = None,
                  timepoint: Optional[float] = None) -> ExperimentData:
        """
        Load experimental data from database.

        Args:
            compounds: List of compounds to include (None = all)
            cell_lines: List of cell lines to include (None = all)
            dose_range: (min, max) dose in µM (None = all)
            timepoint: Specific timepoint to filter (None = all)

        Returns:
            ExperimentData with features, labels, and metadata
        """
        conn = sqlite3.connect(self.db_path)

        # Build query
        query = """
        SELECT
            compound,
            dose_uM,
            timepoint_h,
            cell_line,
            morph_er,
            morph_mito,
            morph_nucleus,
            morph_actin,
            morph_rna
        FROM thalamus_results
        WHERE compound != 'DMSO'
        """

        conditions = []
        if compounds:
            compound_list = "', '".join(compounds)
            conditions.append(f"compound IN ('{compound_list}')")
        if cell_lines:
            cell_line_list = "', '".join(cell_lines)
            conditions.append(f"cell_line IN ('{cell_line_list}')")
        if dose_range:
            conditions.append(f"dose_uM >= {dose_range[0]} AND dose_uM <= {dose_range[1]}")
        if timepoint:
            conditions.append(f"timepoint_h = {timepoint}")

        if conditions:
            query += " AND " + " AND ".join(conditions)

        # Load data
        df = pd.read_sql_query(query, conn)
        conn.close()

        # Add stress axis labels
        df['stress_axis'] = df['compound'].map(self.stress_class_map)

        # Extract features and labels
        feature_cols = ['morph_er', 'morph_mito', 'morph_nucleus', 'morph_actin', 'morph_rna']
        X = df[feature_cols].values
        y = df['stress_axis'].values

        logger.info(f"Loaded {len(df)} samples")
        logger.info(f"  Compounds: {df['compound'].nunique()}")
        logger.info(f"  Cell lines: {df['cell_line'].nunique()}")
        logger.info(f"  Stress classes: {df['stress_axis'].nunique()}")

        return ExperimentData(X=X, y=y, metadata=df)

    def train(self, X_train: np.ndarray, y_train: np.ndarray,
              model_type: str = 'rf') -> Dict[str, Any]:
        """
        Train classifier.

        Args:
            X_train: Training features (N x 5)
            y_train: Training labels (stress axis)
            model_type: 'rf' (Random Forest) or 'gb' (Gradient Boosting)

        Returns:
            Training metrics
        """
        # Normalize features
        X_train_scaled = self.scaler.fit_transform(X_train)

        # Train model
        if model_type == 'rf':
            self.model = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                min_samples_split=20,
                random_state=42
            )
        elif model_type == 'gb':
            self.model = GradientBoostingClassifier(
                n_estimators=100,
                max_depth=5,
                learning_rate=0.1,
                random_state=42
            )
        else:
            raise ValueError(f"Unknown model type: {model_type}")

        self.model.fit(X_train_scaled, y_train)

        # Training accuracy
        y_pred_train = self.model.predict(X_train_scaled)
        train_acc = accuracy_score(y_train, y_pred_train)

        logger.info(f"Trained {model_type} model")
        logger.info(f"  Training accuracy: {train_acc:.3f}")

        return {
            'model_type': model_type,
            'train_accuracy': train_acc,
            'n_classes': len(np.unique(y_train))
        }

    def evaluate(self, X_test: np.ndarray, y_test: np.ndarray) -> Dict[str, Any]:
        """
        Evaluate model on test set.

        Args:
            X_test: Test features
            y_test: Test labels

        Returns:
            Evaluation metrics
        """
        if self.model is None:
            raise ValueError("Model not trained yet")

        # Normalize and predict
        X_test_scaled = self.scaler.transform(X_test)
        y_pred = self.model.predict(X_test_scaled)

        # Metrics
        acc = accuracy_score(y_test, y_pred)
        cm = confusion_matrix(y_test, y_pred)
        report = classification_report(y_test, y_pred, output_dict=True)

        logger.info(f"Test accuracy: {acc:.3f}")

        return {
            'accuracy': acc,
            'confusion_matrix': cm,
            'classification_report': report,
            'predictions': y_pred
        }


class TransferLearningExperiments:
    """
    Runs transfer learning experiments to test generalization.
    """

    def __init__(self, db_path: str = "data/cell_thalamus.db"):
        self.classifier = MorphologyClassifier(db_path)

    def leave_compounds_out_cv(self,
                               n_folds: int = 5,
                               timepoint: float = 12.0,
                               dose_range: Tuple[float, float] = (10.0, 100.0)) -> Dict[str, Any]:
        """
        Leave-compounds-out cross-validation.

        Tests if model trained on subset of compounds generalizes to held-out compounds
        from the same stress classes.

        Args:
            n_folds: Number of CV folds
            timepoint: Which timepoint to use (12h recommended)
            dose_range: Mid-dose range for best signal

        Returns:
            CV results with per-fold accuracies
        """
        logger.info("="*70)
        logger.info("LEAVE-COMPOUNDS-OUT CROSS-VALIDATION")
        logger.info("="*70)
        logger.info(f"Timepoint: {timepoint}h")
        logger.info(f"Dose range: {dose_range[0]}-{dose_range[1]} µM")

        # Load all data
        data = self.classifier.load_data(
            timepoint=timepoint,
            dose_range=dose_range
        )

        # Get unique compounds per stress class
        from collections import defaultdict
        class_compounds = defaultdict(list)
        for compound, stress_class in self.classifier.stress_class_map.items():
            if compound != 'DMSO':
                class_compounds[stress_class].append(compound)

        # Leave 2 compounds out (one from each of 2 classes)
        fold_results = []

        # Simple approach: leave out 2 compounds total
        all_compounds = [c for c in self.classifier.stress_class_map.keys() if c != 'DMSO']

        for fold in range(min(n_folds, 5)):  # Do 5 folds max
            # Randomly select 2 compounds to hold out
            np.random.seed(42 + fold)
            holdout_compounds = np.random.choice(all_compounds, size=2, replace=False)
            train_compounds = [c for c in all_compounds if c not in holdout_compounds]

            # Split data
            train_mask = data.metadata['compound'].isin(train_compounds)
            test_mask = data.metadata['compound'].isin(holdout_compounds)

            X_train = data.X[train_mask]
            y_train = data.y[train_mask]
            X_test = data.X[test_mask]
            y_test = data.y[test_mask]

            if len(X_test) == 0:
                continue

            # Train and evaluate
            logger.info(f"\nFold {fold + 1}:")
            logger.info(f"  Train compounds: {train_compounds}")
            logger.info(f"  Test compounds: {list(holdout_compounds)}")
            logger.info(f"  Train samples: {len(X_train)}")
            logger.info(f"  Test samples: {len(X_test)}")

            self.classifier.train(X_train, y_train, model_type='rf')
            results = self.classifier.evaluate(X_test, y_test)

            fold_results.append({
                'fold': fold + 1,
                'train_compounds': train_compounds,
                'test_compounds': list(holdout_compounds),
                'accuracy': results['accuracy'],
                'n_train': len(X_train),
                'n_test': len(X_test)
            })

            logger.info(f"  Accuracy: {results['accuracy']:.3f}")

        # Summary
        accuracies = [r['accuracy'] for r in fold_results]
        mean_acc = np.mean(accuracies)
        std_acc = np.std(accuracies)

        logger.info(f"\n{'='*70}")
        logger.info("CROSS-VALIDATION SUMMARY")
        logger.info(f"{'='*70}")
        logger.info(f"Mean accuracy: {mean_acc:.3f} ± {std_acc:.3f}")
        logger.info(f"Folds: {len(fold_results)}")

        if mean_acc > 0.7:
            logger.info("✅ SUCCESS: Model generalizes to unseen compounds!")
        else:
            logger.info("⚠️  WEAK: Model struggles with held-out compounds")

        return {
            'mean_accuracy': mean_acc,
            'std_accuracy': std_acc,
            'fold_results': fold_results
        }

    def within_class_transfer(self) -> Dict[str, Any]:
        """
        Test transfer within stress classes.

        Examples:
        - Train on tBHQ (oxidative), test on H2O2 (oxidative)
        - Train on tunicamycin (ER stress), test on thapsigargin (ER stress)

        Returns:
            Transfer results for each test case
        """
        logger.info("="*70)
        logger.info("WITHIN-CLASS TRANSFER LEARNING")
        logger.info("="*70)

        test_cases = [
            {
                'name': 'Oxidative: tBHQ → H2O2',
                'train_compound': 'tBHQ',
                'test_compound': 'H2O2',
                'stress_class': 'oxidative'
            },
            {
                'name': 'ER Stress: tunicamycin → thapsigargin',
                'train_compound': 'tunicamycin',
                'test_compound': 'thapsigargin',
                'stress_class': 'er_stress'
            },
            {
                'name': 'Mitochondrial: CCCP → oligomycin',
                'train_compound': 'CCCP',
                'test_compound': 'oligomycin',
                'stress_class': 'mitochondrial'
            },
            {
                'name': 'Microtubule: nocodazole → paclitaxel',
                'train_compound': 'nocodazole',
                'test_compound': 'paclitaxel',
                'stress_class': 'microtubule'
            }
        ]

        results = []

        for case in test_cases:
            logger.info(f"\n{case['name']}")
            logger.info("-" * 70)

            # Load train data (single compound)
            train_data = self.classifier.load_data(
                compounds=[case['train_compound']],
                timepoint=12.0,
                dose_range=(10.0, 100.0)
            )

            # Load test data (single compound)
            test_data = self.classifier.load_data(
                compounds=[case['test_compound']],
                timepoint=12.0,
                dose_range=(10.0, 100.0)
            )

            if len(test_data) == 0:
                logger.warning(f"  No test data for {case['test_compound']} in dose range - skipping")
                continue

            # For binary classification: is it the same stress class?
            # Convert labels to binary
            y_train_binary = (train_data.y == case['stress_class']).astype(int)
            y_test_binary = (test_data.y == case['stress_class']).astype(int)

            # Train
            self.classifier.train(train_data.X, y_train_binary, model_type='rf')

            # Evaluate
            eval_results = self.classifier.evaluate(test_data.X, y_test_binary)

            logger.info(f"  Train samples: {len(train_data)}")
            logger.info(f"  Test samples: {len(test_data)}")
            logger.info(f"  Transfer accuracy: {eval_results['accuracy']:.3f}")

            results.append({
                'test_case': case['name'],
                'accuracy': eval_results['accuracy'],
                'n_train': len(train_data),
                'n_test': len(test_data)
            })

        # Summary
        logger.info(f"\n{'='*70}")
        logger.info("WITHIN-CLASS TRANSFER SUMMARY")
        logger.info(f"{'='*70}")
        for r in results:
            status = "✅" if r['accuracy'] > 0.7 else "⚠️"
            logger.info(f"{status} {r['test_case']}: {r['accuracy']:.3f}")

        return {'test_cases': results}

    def cell_line_transfer(self) -> Dict[str, Any]:
        """
        Test if stress signatures transfer across cell lines.

        Train on A549, test on HepG2 (and vice versa).

        Returns:
            Transfer results
        """
        logger.info("="*70)
        logger.info("CELL-LINE TRANSFER LEARNING")
        logger.info("="*70)

        results = []

        for train_cell, test_cell in [('A549', 'HepG2'), ('HepG2', 'A549')]:
            logger.info(f"\nTrain: {train_cell} → Test: {test_cell}")
            logger.info("-" * 70)

            # Load data
            train_data = self.classifier.load_data(
                cell_lines=[train_cell],
                timepoint=12.0,
                dose_range=(10.0, 100.0)
            )

            test_data = self.classifier.load_data(
                cell_lines=[test_cell],
                timepoint=12.0,
                dose_range=(10.0, 100.0)
            )

            # Train and evaluate
            self.classifier.train(train_data.X, train_data.y, model_type='rf')
            eval_results = self.classifier.evaluate(test_data.X, test_data.y)

            logger.info(f"  Transfer accuracy: {eval_results['accuracy']:.3f}")

            results.append({
                'train_cell': train_cell,
                'test_cell': test_cell,
                'accuracy': eval_results['accuracy']
            })

        # Summary
        logger.info(f"\n{'='*70}")
        logger.info("CELL-LINE TRANSFER SUMMARY")
        logger.info(f"{'='*70}")
        mean_acc = np.mean([r['accuracy'] for r in results])
        logger.info(f"Mean transfer accuracy: {mean_acc:.3f}")

        if mean_acc > 0.6:
            logger.info("✅ SUCCESS: Stress signatures transfer across cell lines!")
        else:
            logger.info("⚠️  WEAK: Cell-line-specific responses dominate")

        return {'results': results, 'mean_accuracy': mean_acc}
