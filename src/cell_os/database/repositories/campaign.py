"""
Campaign repository for database operations.
"""
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass, asdict
from ..base import BaseRepository


@dataclass
class Campaign:
    """Campaign metadata."""
    campaign_id: str
    campaign_type: str
    goal: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    status: str = "running"
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
    experiment_type: str = "unknown"
    cell_line_id: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    status: str = "pending"
    metadata: Optional[Dict[str, Any]] = None


class CampaignRepository(BaseRepository):
    """Repository for campaign and experiment tracking."""
    
    def __init__(self, db_path: str = "data/campaigns.db"):
        super().__init__(db_path)
    
    def _init_schema(self):
        """Initialize database schema."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            # Campaigns table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS campaigns (
                    campaign_id TEXT PRIMARY KEY,
                    campaign_type TEXT NOT NULL,
                    goal TEXT,
                    start_date TEXT,
                    end_date TEXT,
                    status TEXT DEFAULT 'running',
                    config TEXT,
                    results_summary TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Iterations table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS campaign_iterations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    campaign_id TEXT NOT NULL,
                    iteration_number INTEGER NOT NULL,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
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
                    experiment_type TEXT DEFAULT 'unknown',
                    cell_line_id TEXT,
                    start_date TEXT,
                    end_date TEXT,
                    status TEXT DEFAULT 'pending',
                    metadata TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (campaign_id) REFERENCES campaigns(campaign_id)
                )
            """)
            
            # Campaign-Experiment link table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS campaign_experiments (
                    campaign_id TEXT NOT NULL,
                    experiment_id TEXT NOT NULL,
                    iteration_number INTEGER,
                    linked_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (campaign_id, experiment_id),
                    FOREIGN KEY (campaign_id) REFERENCES campaigns(campaign_id),
                    FOREIGN KEY (experiment_id) REFERENCES experiments(experiment_id)
                )
            """)
            
            conn.commit()
        finally:
            conn.close()
    
    def create_campaign(self, campaign: Campaign):
        """Create a new campaign."""
        data = asdict(campaign)
        # Convert dicts to JSON strings
        if data.get('config'):
            data['config'] = json.dumps(data['config'])
        if data.get('results_summary'):
            data['results_summary'] = json.dumps(data['results_summary'])
        if not data.get('created_at'):
            data['created_at'] = datetime.now().isoformat()
        
        self._insert('campaigns', data)
    
    def get_campaign(self, campaign_id: str) -> Optional[Campaign]:
        """Get campaign by ID."""
        row = self._fetch_one(
            "SELECT * FROM campaigns WHERE campaign_id = ?",
            (campaign_id,)
        )
        if not row:
            return None
        
        # Parse JSON fields
        if row.get('config'):
            row['config'] = json.loads(row['config'])
        if row.get('results_summary'):
            row['results_summary'] = json.loads(row['results_summary'])
        
        return Campaign(**row)
    
    def update_campaign_status(self, campaign_id: str, status: str, results_summary: Optional[Dict] = None):
        """Update campaign status and results."""
        data = {'status': status}
        if results_summary:
            data['results_summary'] = json.dumps(results_summary)
        if status == 'completed':
            data['end_date'] = datetime.now().isoformat()
        
        self._update('campaigns', data, "campaign_id = ?", (campaign_id,))
    
    def add_iteration(self, iteration: CampaignIteration):
        """Add an iteration to a campaign."""
        data = asdict(iteration)
        # Convert lists/dicts to JSON
        for field in ['proposals', 'results', 'model_state', 'metrics']:
            if data.get(field):
                data[field] = json.dumps(data[field])
        if not data.get('timestamp'):
            data['timestamp'] = datetime.now().isoformat()
        
        self._insert('campaign_iterations', data)
    
    def get_iterations(self, campaign_id: str) -> List[CampaignIteration]:
        """Get all iterations for a campaign."""
        rows = self._fetch_all(
            "SELECT * FROM campaign_iterations WHERE campaign_id = ? ORDER BY iteration_number",
            (campaign_id,)
        )
        
        iterations = []
        for row in rows:
            # Remove database-specific fields
            row = {k: v for k, v in row.items() if k != 'id'}
            # Parse JSON fields
            for field in ['proposals', 'results', 'model_state', 'metrics']:
                if row.get(field):
                    row[field] = json.loads(row[field])
            iterations.append(CampaignIteration(**row))
        
        return iterations
    
    def create_experiment(self, experiment: Experiment):
        """Create a new experiment."""
        data = asdict(experiment)
        if data.get('metadata'):
            data['metadata'] = json.dumps(data['metadata'])
        
        self._insert('experiments', data)
    
    def link_experiment_to_campaign(self, campaign_id: str, experiment_id: str, iteration_number: Optional[int] = None):
        """Link an experiment to a campaign."""
        data = {
            'campaign_id': campaign_id,
            'experiment_id': experiment_id,
            'iteration_number': iteration_number
        }
        self._insert('campaign_experiments', data)
    
    def get_campaign_experiments(self, campaign_id: str) -> List[str]:
        """Get all experiment IDs for a campaign."""
        rows = self._fetch_all(
            "SELECT experiment_id FROM campaign_experiments WHERE campaign_id = ?",
            (campaign_id,)
        )
        return [row['experiment_id'] for row in rows]
    
    def find_campaigns(self, **filters) -> List[Campaign]:
        """Find campaigns matching filters."""
        where_clauses = []
        params = []
        
        for key, value in filters.items():
            if key in ['campaign_type', 'status']:
                where_clauses.append(f"{key} = ?")
                params.append(value)
        
        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
        rows = self._fetch_all(f"SELECT * FROM campaigns WHERE {where_sql}", tuple(params))
        
        campaigns = []
        for row in rows:
            if row.get('config'):
                row['config'] = json.loads(row['config'])
            if row.get('results_summary'):
                row['results_summary'] = json.loads(row['results_summary'])
            campaigns.append(Campaign(**row))
        
        return campaigns
    
    def get_campaign_stats(self, campaign_id: str) -> Dict[str, Any]:
        """Get statistics for a campaign."""
        stats = {}
        
        # Count iterations
        result = self._fetch_one(
            "SELECT COUNT(*) as count FROM campaign_iterations WHERE campaign_id = ?",
            (campaign_id,)
        )
        stats['iteration_count'] = result['count'] if result else 0
        
        # Count experiments
        result = self._fetch_one(
            "SELECT COUNT(*) as count FROM campaign_experiments WHERE campaign_id = ?",
            (campaign_id,)
        )
        stats['experiment_count'] = result['count'] if result else 0
        
        return stats
    
    def get_all_campaigns(self) -> List[str]:
        """Get list of all campaign IDs."""
        rows = self._fetch_all("SELECT campaign_id FROM campaigns")
        return [row['campaign_id'] for row in rows]
