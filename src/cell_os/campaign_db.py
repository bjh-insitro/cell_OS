"""
Campaign Metadata Database

Manages autonomous and manual campaigns with full tracking of iterations,
experiments, and results. Replaces scattered JSON files with unified database.
"""

import sqlite3
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class Campaign:
    """Campaign metadata."""
    campaign_id: str
    campaign_type: str  # autonomous, manual, mcb, wcb, facility
    goal: Optional[str] = None  # optimization, validation, production
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    status: str = "running"  # running, completed, failed, cancelled
    config: Optional[Dict[str, Any]] = None
    results_summary: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None


@dataclass
class CampaignIteration:
    """Single iteration in an autonomous campaign."""
    campaign_id: str
    iteration_number: int
    timestamp: Optional[str] = None
    proposals: Optional[List[Dict]] = None
    results: Optional[List[Dict]] = None
    model_state: Optional[Dict] = None
    metrics: Optional[Dict] = None


@dataclass
class Experiment:
    """Individual experiment record."""
    experiment_id: str
    campaign_id: Optional[str] = None
    experiment_type: str = "unknown"  # viability, reporter, imaging, mcb, wcb
    cell_line_id: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    status: str = "pending"  # pending, running, completed, failed
    metadata: Optional[Dict[str, Any]] = None


class CampaignDatabase:
    """
    Database for campaign and experiment tracking.
    
    Features:
    - Campaign metadata and configuration
    - Iteration tracking for autonomous campaigns
    - Experiment records linked to campaigns
    - Results aggregation
    - Progress monitoring
    """
    
    def __init__(self, db_path: str = "data/campaigns.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Campaigns table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS campaigns (
                campaign_id TEXT PRIMARY KEY,
                campaign_type TEXT NOT NULL,
                goal TEXT,
                start_date TIMESTAMP,
                end_date TIMESTAMP,
                status TEXT DEFAULT 'running',
                config TEXT,
                results_summary TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Campaign iterations (for autonomous campaigns)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS campaign_iterations (
                iteration_id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id TEXT NOT NULL,
                iteration_number INTEGER NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                proposals TEXT,
                results TEXT,
                model_state TEXT,
                metrics TEXT,
                FOREIGN KEY (campaign_id) REFERENCES campaigns(campaign_id),
                UNIQUE(campaign_id, iteration_number)
            )
        """)
        
        # Experiments table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS experiments (
                experiment_id TEXT PRIMARY KEY,
                campaign_id TEXT,
                experiment_type TEXT NOT NULL,
                cell_line_id TEXT,
                start_date TIMESTAMP,
                end_date TIMESTAMP,
                status TEXT DEFAULT 'pending',
                metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (campaign_id) REFERENCES campaigns(campaign_id)
            )
        """)
        
        # Campaign-experiment link table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS campaign_experiments (
                campaign_id TEXT NOT NULL,
                experiment_id TEXT NOT NULL,
                iteration_number INTEGER,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (campaign_id, experiment_id),
                FOREIGN KEY (campaign_id) REFERENCES campaigns(campaign_id),
                FOREIGN KEY (experiment_id) REFERENCES experiments(experiment_id)
            )
        """)
        
        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_campaign_type ON campaigns(campaign_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_campaign_status ON campaigns(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_iteration_campaign ON campaign_iterations(campaign_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_experiment_campaign ON experiments(campaign_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_experiment_type ON experiments(experiment_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_experiment_status ON experiments(status)")
        
        conn.commit()
        conn.close()
    
    def create_campaign(self, campaign: Campaign) -> str:
        """Create a new campaign."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if campaign.created_at is None:
            campaign.created_at = datetime.now().isoformat()
        if campaign.start_date is None:
            campaign.start_date = datetime.now().isoformat()
        
        cursor.execute("""
            INSERT INTO campaigns (
                campaign_id, campaign_type, goal, start_date, end_date,
                status, config, results_summary, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            campaign.campaign_id,
            campaign.campaign_type,
            campaign.goal,
            campaign.start_date,
            campaign.end_date,
            campaign.status,
            json.dumps(campaign.config) if campaign.config else None,
            json.dumps(campaign.results_summary) if campaign.results_summary else None,
            campaign.created_at
        ))
        
        conn.commit()
        conn.close()
        
        return campaign.campaign_id
    
    def get_campaign(self, campaign_id: str) -> Optional[Campaign]:
        """Get campaign by ID."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM campaigns WHERE campaign_id = ?", (campaign_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return Campaign(
                campaign_id=row[0],
                campaign_type=row[1],
                goal=row[2],
                start_date=row[3],
                end_date=row[4],
                status=row[5],
                config=json.loads(row[6]) if row[6] else None,
                results_summary=json.loads(row[7]) if row[7] else None,
                created_at=row[8]
            )
        return None
    
    def update_campaign_status(
        self,
        campaign_id: str,
        status: str,
        results_summary: Optional[Dict] = None
    ):
        """Update campaign status and results."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if status in ["completed", "failed", "cancelled"]:
            end_date = datetime.now().isoformat()
            cursor.execute("""
                UPDATE campaigns
                SET status = ?, end_date = ?, results_summary = ?
                WHERE campaign_id = ?
            """, (status, end_date, json.dumps(results_summary) if results_summary else None, campaign_id))
        else:
            cursor.execute("""
                UPDATE campaigns
                SET status = ?
                WHERE campaign_id = ?
            """, (status, campaign_id))
        
        conn.commit()
        conn.close()
    
    def add_iteration(self, iteration: CampaignIteration) -> int:
        """Add an iteration to a campaign."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if iteration.timestamp is None:
            iteration.timestamp = datetime.now().isoformat()
        
        cursor.execute("""
            INSERT INTO campaign_iterations (
                campaign_id, iteration_number, timestamp,
                proposals, results, model_state, metrics
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            iteration.campaign_id,
            iteration.iteration_number,
            iteration.timestamp,
            json.dumps(iteration.proposals) if iteration.proposals else None,
            json.dumps(iteration.results) if iteration.results else None,
            json.dumps(iteration.model_state) if iteration.model_state else None,
            json.dumps(iteration.metrics) if iteration.metrics else None
        ))
        
        iteration_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return iteration_id
    
    def get_iterations(self, campaign_id: str) -> List[CampaignIteration]:
        """Get all iterations for a campaign."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM campaign_iterations
            WHERE campaign_id = ?
            ORDER BY iteration_number
        """, (campaign_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            CampaignIteration(
                campaign_id=row[1],
                iteration_number=row[2],
                timestamp=row[3],
                proposals=json.loads(row[4]) if row[4] else None,
                results=json.loads(row[5]) if row[5] else None,
                model_state=json.loads(row[6]) if row[6] else None,
                metrics=json.loads(row[7]) if row[7] else None
            )
            for row in rows
        ]
    
    def create_experiment(self, experiment: Experiment) -> str:
        """Create a new experiment."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if experiment.start_date is None:
            experiment.start_date = datetime.now().isoformat()
        
        cursor.execute("""
            INSERT INTO experiments (
                experiment_id, campaign_id, experiment_type, cell_line_id,
                start_date, end_date, status, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            experiment.experiment_id,
            experiment.campaign_id,
            experiment.experiment_type,
            experiment.cell_line_id,
            experiment.start_date,
            experiment.end_date,
            experiment.status,
            json.dumps(experiment.metadata) if experiment.metadata else None
        ))
        
        conn.commit()
        conn.close()
        
        return experiment.experiment_id
    
    def link_experiment_to_campaign(
        self,
        campaign_id: str,
        experiment_id: str,
        iteration_number: Optional[int] = None
    ):
        """Link an experiment to a campaign."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR IGNORE INTO campaign_experiments (
                campaign_id, experiment_id, iteration_number
            ) VALUES (?, ?, ?)
        """, (campaign_id, experiment_id, iteration_number))
        
        conn.commit()
        conn.close()
    
    def get_campaign_experiments(self, campaign_id: str) -> List[str]:
        """Get all experiment IDs for a campaign."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT experiment_id FROM campaign_experiments
            WHERE campaign_id = ?
            ORDER BY added_at
        """, (campaign_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [row[0] for row in rows]
    
    def find_campaigns(self, **filters) -> List[Campaign]:
        """Find campaigns matching filters."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        where_clauses = []
        params = []
        
        if 'campaign_type' in filters:
            where_clauses.append("campaign_type = ?")
            params.append(filters['campaign_type'])
        
        if 'status' in filters:
            where_clauses.append("status = ?")
            params.append(filters['status'])
        
        if 'goal' in filters:
            where_clauses.append("goal = ?")
            params.append(filters['goal'])
        
        query = "SELECT * FROM campaigns"
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        query += " ORDER BY created_at DESC"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        return [
            Campaign(
                campaign_id=row[0],
                campaign_type=row[1],
                goal=row[2],
                start_date=row[3],
                end_date=row[4],
                status=row[5],
                config=json.loads(row[6]) if row[6] else None,
                results_summary=json.loads(row[7]) if row[7] else None,
                created_at=row[8]
            )
            for row in rows
        ]
    
    def get_campaign_stats(self, campaign_id: str) -> Dict[str, Any]:
        """Get statistics for a campaign."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get iteration count
        cursor.execute("""
            SELECT COUNT(*) FROM campaign_iterations
            WHERE campaign_id = ?
        """, (campaign_id,))
        iteration_count = cursor.fetchone()[0]
        
        # Get experiment count
        cursor.execute("""
            SELECT COUNT(*) FROM campaign_experiments
            WHERE campaign_id = ?
        """, (campaign_id,))
        experiment_count = cursor.fetchone()[0]
        
        # Get campaign info
        campaign = self.get_campaign(campaign_id)
        
        conn.close()
        
        stats = {
            "campaign_id": campaign_id,
            "iterations": iteration_count,
            "experiments": experiment_count,
            "status": campaign.status if campaign else "unknown",
            "type": campaign.campaign_type if campaign else "unknown"
        }
        
        if campaign and campaign.start_date and campaign.end_date:
            start = datetime.fromisoformat(campaign.start_date)
            end = datetime.fromisoformat(campaign.end_date)
            duration = (end - start).total_seconds()
            stats["duration_seconds"] = duration
        
        return stats
    
    def get_all_campaigns(self) -> List[str]:
        """Get list of all campaign IDs."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT campaign_id FROM campaigns ORDER BY created_at DESC")
        rows = cursor.fetchall()
        conn.close()
        
        return [row[0] for row in rows]
