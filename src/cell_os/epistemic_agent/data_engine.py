"""
Data Engine per Feala's Closed-Loop Manifesto.

"Building data engines, rather than static datasets, that grow in
complexity over time."

This module implements persistent learning across experimental runs:
1. Accumulates observations into a growing knowledge base
2. Tracks which compound/condition combinations have been tested
3. Enables transfer learning from past experiments
4. Provides compound-specific priors based on historical data

Design principle: Each experiment should make future experiments smarter.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Set
from pathlib import Path
from datetime import datetime
import json
import sqlite3
from contextlib import contextmanager


@dataclass
class ObservationRecord:
    """Single observation stored in the data engine."""
    run_id: str
    cycle: int
    timestamp: str

    # Experimental conditions
    cell_line: str
    compound: str
    dose_um: float
    time_h: float

    # Observations
    viability: float
    morphology_mean: float
    morphology_std: float

    # Mechanism inference
    predicted_mechanism: Optional[str] = None
    mechanism_confidence: float = 0.0
    true_mechanism: Optional[str] = None  # If known

    # Metadata
    n_wells: int = 1
    position_tag: str = "any"


@dataclass
class CompoundKnowledge:
    """Accumulated knowledge about a specific compound."""
    compound_id: str

    # Observation counts
    total_observations: int = 0
    unique_doses_tested: int = 0
    unique_timepoints_tested: int = 0

    # Aggregated statistics
    mean_viability: float = 1.0
    mean_effect_size: float = 0.0

    # Mechanism predictions
    mechanism_calls: Dict[str, int] = field(default_factory=dict)
    most_likely_mechanism: Optional[str] = None
    mechanism_confidence: float = 0.0

    # Dose-response info
    estimated_ic50: Optional[float] = None
    therapeutic_window_exists: bool = False

    def update_from_observation(self, obs: ObservationRecord):
        """Update knowledge from new observation."""
        self.total_observations += 1

        # Running average for viability
        alpha = 1.0 / self.total_observations
        self.mean_viability = (1 - alpha) * self.mean_viability + alpha * obs.viability

        # Track mechanism calls
        if obs.predicted_mechanism:
            self.mechanism_calls[obs.predicted_mechanism] = \
                self.mechanism_calls.get(obs.predicted_mechanism, 0) + 1

            # Update most likely mechanism
            if self.mechanism_calls:
                self.most_likely_mechanism = max(
                    self.mechanism_calls,
                    key=self.mechanism_calls.get
                )
                total = sum(self.mechanism_calls.values())
                self.mechanism_confidence = self.mechanism_calls[self.most_likely_mechanism] / total


class DataEngine:
    """
    Persistent data engine for cross-run learning.

    Uses SQLite for persistence, enabling knowledge accumulation
    across multiple experimental campaigns.
    """

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize data engine with optional database path."""
        if db_path is None:
            db_path = Path("results/data_engine.db")

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # In-memory caches
        self._compound_knowledge: Dict[str, CompoundKnowledge] = {}
        self._tested_conditions: Set[str] = set()

        # Initialize database
        self._init_db()
        self._load_cache()

    def _init_db(self):
        """Initialize database schema."""
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS observations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT,
                    cycle INTEGER,
                    timestamp TEXT,
                    cell_line TEXT,
                    compound TEXT,
                    dose_um REAL,
                    time_h REAL,
                    viability REAL,
                    morphology_mean REAL,
                    morphology_std REAL,
                    predicted_mechanism TEXT,
                    mechanism_confidence REAL,
                    true_mechanism TEXT,
                    n_wells INTEGER,
                    position_tag TEXT
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_compound
                ON observations(compound)
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS compound_knowledge (
                    compound_id TEXT PRIMARY KEY,
                    total_observations INTEGER,
                    mean_viability REAL,
                    most_likely_mechanism TEXT,
                    mechanism_confidence REAL,
                    mechanism_calls_json TEXT,
                    updated_at TEXT
                )
            """)

    @contextmanager
    def _get_conn(self):
        """Get database connection."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _load_cache(self):
        """Load compound knowledge into memory cache."""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT compound_id, total_observations, mean_viability, "
                "most_likely_mechanism, mechanism_confidence, mechanism_calls_json "
                "FROM compound_knowledge"
            )
            for row in cursor:
                ck = CompoundKnowledge(
                    compound_id=row[0],
                    total_observations=row[1],
                    mean_viability=row[2],
                    most_likely_mechanism=row[3],
                    mechanism_confidence=row[4],
                    mechanism_calls=json.loads(row[5]) if row[5] else {}
                )
                self._compound_knowledge[ck.compound_id] = ck

    def record_observation(self, obs: ObservationRecord):
        """Record a new observation to the data engine."""
        # Store in database
        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO observations
                (run_id, cycle, timestamp, cell_line, compound, dose_um, time_h,
                 viability, morphology_mean, morphology_std, predicted_mechanism,
                 mechanism_confidence, true_mechanism, n_wells, position_tag)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                obs.run_id, obs.cycle, obs.timestamp, obs.cell_line,
                obs.compound, obs.dose_um, obs.time_h, obs.viability,
                obs.morphology_mean, obs.morphology_std, obs.predicted_mechanism,
                obs.mechanism_confidence, obs.true_mechanism, obs.n_wells,
                obs.position_tag
            ))

        # Update compound knowledge
        if obs.compound not in self._compound_knowledge:
            self._compound_knowledge[obs.compound] = CompoundKnowledge(
                compound_id=obs.compound
            )

        self._compound_knowledge[obs.compound].update_from_observation(obs)
        self._save_compound_knowledge(obs.compound)

        # Track tested condition
        condition_key = f"{obs.cell_line}_{obs.compound}_{obs.dose_um}_{obs.time_h}"
        self._tested_conditions.add(condition_key)

    def _save_compound_knowledge(self, compound_id: str):
        """Persist compound knowledge to database."""
        ck = self._compound_knowledge.get(compound_id)
        if not ck:
            return

        with self._get_conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO compound_knowledge
                (compound_id, total_observations, mean_viability,
                 most_likely_mechanism, mechanism_confidence,
                 mechanism_calls_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                ck.compound_id, ck.total_observations, ck.mean_viability,
                ck.most_likely_mechanism, ck.mechanism_confidence,
                json.dumps(ck.mechanism_calls),
                datetime.now().isoformat()
            ))

    def get_compound_prior(self, compound: str) -> Optional[Dict[str, float]]:
        """
        Get mechanism prior for a compound based on historical data.

        Returns dict of mechanism -> probability, or None if no data.
        """
        ck = self._compound_knowledge.get(compound)
        if not ck or not ck.mechanism_calls:
            return None

        total = sum(ck.mechanism_calls.values())
        return {m: c / total for m, c in ck.mechanism_calls.items()}

    def get_exploration_score(self, compound: str) -> float:
        """
        Score how much we know about a compound (0=nothing, 1=well-characterized).

        Used to prioritize under-explored compounds.
        """
        ck = self._compound_knowledge.get(compound)
        if not ck:
            return 0.0

        # Score based on observation count and confidence
        obs_score = min(1.0, ck.total_observations / 100)  # Cap at 100 obs
        conf_score = ck.mechanism_confidence

        return 0.5 * obs_score + 0.5 * conf_score

    def suggest_next_compound(
        self,
        available_compounds: List[str],
        strategy: str = "uncertainty"
    ) -> str:
        """
        Suggest which compound to test next.

        Strategies:
        - "uncertainty": Test least-explored compound
        - "confirmation": Test compound with uncertain mechanism call
        - "random": Random selection
        """
        if not available_compounds:
            raise ValueError("No compounds available")

        if strategy == "uncertainty":
            # Pick compound with lowest exploration score
            scores = {c: self.get_exploration_score(c) for c in available_compounds}
            return min(scores, key=scores.get)

        elif strategy == "confirmation":
            # Pick compound with mechanism call but low confidence
            candidates = []
            for c in available_compounds:
                ck = self._compound_knowledge.get(c)
                if ck and ck.most_likely_mechanism and ck.mechanism_confidence < 0.8:
                    candidates.append((c, ck.mechanism_confidence))

            if candidates:
                return min(candidates, key=lambda x: x[1])[0]
            return available_compounds[0]

        else:  # random
            import random
            return random.choice(available_compounds)

    def get_stats(self) -> Dict[str, Any]:
        """Get summary statistics from the data engine."""
        with self._get_conn() as conn:
            total_obs = conn.execute(
                "SELECT COUNT(*) FROM observations"
            ).fetchone()[0]

            unique_compounds = conn.execute(
                "SELECT COUNT(DISTINCT compound) FROM observations"
            ).fetchone()[0]

            unique_runs = conn.execute(
                "SELECT COUNT(DISTINCT run_id) FROM observations"
            ).fetchone()[0]

        return {
            'total_observations': total_obs,
            'unique_compounds': unique_compounds,
            'unique_runs': unique_runs,
            'compounds_with_mechanism': sum(
                1 for ck in self._compound_knowledge.values()
                if ck.most_likely_mechanism
            ),
        }
