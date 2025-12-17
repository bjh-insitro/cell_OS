#!/bin/bash
set -e

# Deploy Cell Thalamus Lambda Function
# This script packages and deploys the Lambda function to AWS

LAMBDA_FUNCTION_NAME="cell-thalamus-simulator"
AWS_REGION="us-west-2"
AWS_PROFILE="bedrock"
LAMBDA_ROLE_ARN="arn:aws:iam::298579124006:role/cell-thalamus-lambda-role"  # Will be created by AWS admin

echo "======================================"
echo "Cell Thalamus Lambda Deployment"
echo "======================================"

# Check AWS CLI
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI not found. Install it first."
    exit 1
fi

# Create package directory
PACKAGE_DIR="$(pwd)/lambda_package"
rm -rf "$PACKAGE_DIR"
mkdir -p "$PACKAGE_DIR"

echo "📦 Packaging Lambda function..."

# Copy Lambda handler
cp lambda/cell_thalamus_lambda.py "$PACKAGE_DIR/"

# Copy standalone script
cp standalone_cell_thalamus.py "$PACKAGE_DIR/"

# Install dependencies to package directory
echo "📥 Installing dependencies..."
pip install --target "$PACKAGE_DIR" numpy tqdm boto3 --upgrade --quiet

# Create ZIP
cd "$PACKAGE_DIR"
ZIP_FILE="../cell_thalamus_lambda.zip"
rm -f "$ZIP_FILE"
zip -r "$ZIP_FILE" . -q
cd ..

echo "✅ Package created: $(du -h cell_thalamus_lambda.zip | cut -f1)"

# Check if Lambda function exists
echo "🔍 Checking if Lambda function exists..."
if aws lambda get-function --function-name "$LAMBDA_FUNCTION_NAME" --profile "$AWS_PROFILE" &> /dev/null; then
    echo "📤 Updating existing Lambda function..."
    aws lambda update-function-code \
        --function-name "$LAMBDA_FUNCTION_NAME" \
        --zip-file fileb://cell_thalamus_lambda.zip \
        --profile "$AWS_PROFILE" \
        --region "$AWS_REGION"

    echo "⚙️  Updating Lambda configuration..."
    aws lambda update-function-configuration \
        --function-name "$LAMBDA_FUNCTION_NAME" \
        --timeout 900 \
        --memory-size 3008 \
        --profile "$AWS_PROFILE" \
        --region "$AWS_REGION"
else
    echo "🆕 Creating new Lambda function..."
    aws lambda create-function \
        --function-name "$LAMBDA_FUNCTION_NAME" \
        --runtime python3.11 \
        --role "$LAMBDA_ROLE_ARN" \
        --handler cell_thalamus_lambda.lambda_handler \
        --zip-file fileb://cell_thalamus_lambda.zip \
        --timeout 900 \
        --memory-size 3008 \
        --profile "$AWS_PROFILE" \
        --region "$AWS_REGION" \
        --environment Variables={S3_BUCKET=insitro-user,S3_KEY=brig/cell_thalamus_results.db}
fi

echo ""
echo "✅ Lambda deployment complete!"
echo ""
echo "📋 Function details:"
echo "   Name: $LAMBDA_FUNCTION_NAME"
echo "   Region: $AWS_REGION"
echo "   Timeout: 15 minutes"
echo "   Memory: 3 GB"
echo ""
echo "🧪 Test invocation:"
echo '   aws lambda invoke --function-name cell-thalamus-simulator \'
echo '       --payload '"'"'{"candidates":[{"compound":"CCCP","cell_line":"A549","timepoint_h":12.0,"wells":12,"priority":"Primary"}]}'"'"' \'
echo '       --profile bedrock response.json'
echo ""
echo "⚠️  NOTE: You need to update LAMBDA_ROLE_ARN in this script with your AWS account ID!"
echo "   Create an IAM role with Lambda execution + S3 write permissions first."
