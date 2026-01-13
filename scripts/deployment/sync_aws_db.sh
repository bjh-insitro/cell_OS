#!/bin/bash

# Sync database from AWS S3 to local machine
# Usage: ./scripts/sync_aws_db.sh

set -e  # Exit on error

# Configuration
S3_BUCKET="insitro-user"
S3_KEY="brig/cell_thalamus_results.db"
LOCAL_DB_PATH="/Users/bjh/cell_OS/data/cell_thalamus.db"

echo "📡 Downloading database from S3..."
echo "Source: s3://$S3_BUCKET/$S3_KEY"
echo "Destination: $LOCAL_DB_PATH"

# Check if AWS CLI is available
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI not found. Please install it:"
    echo "   brew install awscli"
    exit 1
fi

# Download from S3 using bedrock profile
aws s3 cp "s3://$S3_BUCKET/$S3_KEY" "$LOCAL_DB_PATH" --profile bedrock

# Check if download was successful
if [ -f "$LOCAL_DB_PATH" ]; then
    FILE_SIZE=$(ls -lh "$LOCAL_DB_PATH" | awk '{print $5}')
    echo "✅ Database synced successfully! Size: $FILE_SIZE"
    echo ""
    echo "Next steps:"
    echo "  1. Make sure your backend is running: npm run api"
    echo "  2. View in frontend: http://localhost:5173/cell-thalamus"
else
    echo "❌ Download failed!"
    exit 1
fi
