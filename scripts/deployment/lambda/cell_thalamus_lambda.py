"""
AWS Lambda Handler for Cell Thalamus Simulation
Triggers standalone_cell_thalamus.py with portfolio parameters
"""
import json
import sys
import os
import tempfile
import boto3
from pathlib import Path

# Add parent directory to path to import standalone script
sys.path.insert(0, os.path.dirname(__file__))
from standalone_cell_thalamus import run_parallel_simulation

s3_client = boto3.client('s3')
S3_BUCKET = os.environ.get("CELL_OS_S3_BUCKET", "insitro-user")
S3_KEY = os.environ.get("CELL_OS_S3_KEY", "brig/cell_thalamus_results.db")


def lambda_handler(event, context):
    """
    Lambda handler for Cell Thalamus simulation.

    Expected event structure:
    {
        "candidates": [
            {"compound": "CCCP", "cell_line": "A549", "timepoint_h": 12.0, "wells": 12, "priority": "Primary"},
            ...
        ],
        "design_id": "uuid-string" (optional)
    }
    """
    try:
        print("Lambda invoked with event:", json.dumps(event))

        # Parse input
        candidates = event.get('candidates', [])
        design_id = event.get('design_id', None)

        if not candidates:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'No candidates provided'})
            }

        # Create temporary DB file
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_db:
            db_path = tmp_db.name

        print(f"Running simulation with {len(candidates)} candidates...")
        print(f"Total wells: {sum(c['wells'] for c in candidates) + 32}")

        # Run simulation
        # Note: For Lambda, we need to adapt run_parallel_simulation to accept portfolio params
        # For now, run in 'demo' mode to test Lambda infrastructure
        design_id = run_parallel_simulation(
            mode='demo',
            workers=4,  # Lambda has limited CPU
            db_path=db_path
        )

        print(f"Simulation complete! Design ID: {design_id}")

        # Upload to S3
        print(f"Uploading to s3://{S3_BUCKET}/{S3_KEY}...")
        s3_client.upload_file(db_path, S3_BUCKET, S3_KEY)
        print("Upload complete!")

        # Clean up
        os.unlink(db_path)

        return {
            'statusCode': 200,
            'body': json.dumps({
                'success': True,
                'design_id': design_id,
                'message': 'Simulation complete and uploaded to S3'
            })
        }

    except Exception as e:
        print(f"Error in Lambda handler: {e}")
        import traceback
        traceback.print_exc()

        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'message': 'Simulation failed'
            })
        }
