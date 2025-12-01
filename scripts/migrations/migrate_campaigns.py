"""
Migrate autonomous campaigns from JSON files to database.

This script:
1. Scans results/autonomous_campaigns/ for campaign folders
2. Loads campaign_report.json and checkpoint files
3. Creates campaigns.db
4. Migrates all campaign data
5. Validates the migration
"""

import json
from pathlib import Path
from typing import List, Optional
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cell_os.database.repositories.campaign import (
    CampaignRepository,
    Campaign,
    CampaignIteration
)


def find_campaign_folders(base_dir: str = "results/autonomous_campaigns") -> List[Path]:
    """Find all campaign folders."""
    base_path = Path(base_dir)
    if not base_path.exists():
        return []
    
    return [p for p in base_path.iterdir() if p.is_dir()]


def load_campaign_report(campaign_dir: Path) -> Optional[dict]:
    """Load campaign_report.json from a campaign folder."""
    report_path = campaign_dir / "campaign_report.json"
    if not report_path.exists():
        return None
    
    with open(report_path) as f:
        return json.load(f)


def load_checkpoints(campaign_dir: Path) -> List[dict]:
    """Load all checkpoint files from a campaign folder."""
    checkpoints = []
    for checkpoint_file in sorted(campaign_dir.glob("checkpoint_iter_*.json")):
        with open(checkpoint_file) as f:
            checkpoints.append(json.load(f))
    return checkpoints


def migrate_campaign(db: CampaignRepository, campaign_dir: Path, report: dict):
    """Migrate a single campaign."""
    campaign_id = report["campaign_id"]
    
    print(f"\n📊 Migrating campaign: {campaign_id}")
    print(f"   Path: {campaign_dir}")
    
    # Create campaign
    campaign = Campaign(
        campaign_id=campaign_id,
        campaign_type="autonomous",
        goal="optimization",
        status="completed",
        config=report.get("config"),
        results_summary=report.get("results")
    )
    
    db.create_campaign(campaign)
    print(f"   ✅ Created campaign record")
    
    # Load and migrate checkpoints (iterations)
    checkpoints = load_checkpoints(campaign_dir)
    print(f"   Found {len(checkpoints)} iterations")
    
    for checkpoint in checkpoints:
        iteration = CampaignIteration(
            campaign_id=campaign_id,
            iteration_number=checkpoint["iteration"],
            timestamp=checkpoint["timestamp"],
            proposals=None,  # Not stored in checkpoint
            results=checkpoint.get("results", []),
            model_state=None,  # Not stored in checkpoint
            metrics={
                "total_experiments": checkpoint.get("total_experiments"),
                "queue_stats": checkpoint.get("queue_stats")
            }
        )
        
        db.add_iteration(iteration)
    
    print(f"   ✅ Migrated {len(checkpoints)} iterations")
    
    return len(checkpoints)


def main():
    """Main migration function."""
    print("="*60)
    print("🚀 CAMPAIGN METADATA MIGRATION")
    print("="*60)
    print("\nMigrating autonomous campaigns from JSON to database...")
    
    # Find campaign folders
    print("\n📂 Scanning for campaigns...")
    campaign_folders = find_campaign_folders()
    
    if not campaign_folders:
        print("⚠️  No campaign folders found in results/autonomous_campaigns/")
        print("   Run an autonomous campaign first:")
        print("   python scripts/demos/run_loop_v2.py --max-iterations 5")
        return 0
    
    print(f"✅ Found {len(campaign_folders)} campaign folders")
    
    # Create database
    print("\n💾 Creating database...")
    db_path = "data/campaigns.db"
    
    # Backup existing database if it exists
    if Path(db_path).exists():
        backup_path = f"{db_path}.backup"
        Path(db_path).rename(backup_path)
        print(f"⚠️  Backed up existing database to {backup_path}")
    
    db = CampaignRepository(db_path)
    print(f"✅ Created {db_path}")
    
    # Migrate each campaign
    total_campaigns = 0
    total_iterations = 0
    
    for campaign_dir in campaign_folders:
        report = load_campaign_report(campaign_dir)
        
        if not report:
            print(f"\n⚠️  Skipping {campaign_dir.name} (no campaign_report.json)")
            continue
        
        iteration_count = migrate_campaign(db, campaign_dir, report)
        total_campaigns += 1
        total_iterations += iteration_count
    
    # Print summary
    print("\n" + "="*60)
    print("📊 MIGRATION SUMMARY")
    print("="*60)
    
    print(f"\n✅ Migrated {total_campaigns} campaigns")
    print(f"✅ Migrated {total_iterations} total iterations")
    
    # Show campaign stats
    print("\n📋 Campaigns:")
    for campaign_id in db.get_all_campaigns():
        stats = db.get_campaign_stats(campaign_id)
        campaign = db.get_campaign(campaign_id)
        print(f"  {campaign_id}")
        print(f"    Iterations: {stats.get('iteration_count', 0)}")
        print(f"    Status: {campaign.status if campaign else 'unknown'}")
    
    print("\n" + "="*60)
    print("✅ Migration completed successfully!")
    print(f"💾 Database created at: {db_path}")
    print("="*60)
    
    return 0


if __name__ == "__main__":
    exit(main())
