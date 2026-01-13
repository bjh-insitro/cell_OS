#!/usr/bin/env python3
"""
Upload cell_thalamus_results.db to S3
Run this in JupyterHub after completing a simulation
"""

import boto3
import os
from pathlib import Path

# Configuration (override via environment variables)
S3_BUCKET = os.environ.get("CELL_OS_S3_BUCKET", "insitro-user")
S3_KEY = os.environ.get("CELL_OS_S3_KEY", "brig/cell_thalamus_results.db")
LOCAL_DB_PATH = "cell_thalamus_results.db"

def upload_to_s3():
    """Upload database file to S3"""

    # Check if file exists
    if not os.path.exists(LOCAL_DB_PATH):
        print(f"❌ Error: {LOCAL_DB_PATH} not found!")
        print(f"Current directory: {os.getcwd()}")
        print(f"Files here: {os.listdir('.')}")
        return False

    # Get file size
    file_size_mb = os.path.getsize(LOCAL_DB_PATH) / (1024 * 1024)

    print(f"📤 Uploading database to S3...")
    print(f"   Source: {LOCAL_DB_PATH} ({file_size_mb:.2f} MB)")
    print(f"   Destination: s3://{S3_BUCKET}/{S3_KEY}")

    try:
        # Upload to S3
        s3 = boto3.client('s3')
        s3.upload_file(LOCAL_DB_PATH, S3_BUCKET, S3_KEY)

        print(f"✅ Upload successful!")
        print(f"   To download locally, run: ./scripts/sync_aws_db.sh")
        return True

    except Exception as e:
        print(f"❌ Upload failed: {e}")
        return False

if __name__ == "__main__":
    upload_to_s3()
