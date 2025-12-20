# AWS Lambda Setup for Cell Thalamus

**⚠️ IMPORTANT - PERMISSION STATUS (as of Dec 16, 2025):**

Lambda deployment requires IAM permissions that are not yet granted:
1. ❌ **Local Mac → S3 write**: Blocked from `aws s3 cp` with bedrock profile
2. ✅ **JupyterHub → S3 write**: Working! (boto3 has credentials in that environment)
3. ❌ **IAM role** `cell-thalamus-lambda-role`: Doesn't exist yet
4. ❌ **Lambda function creation**: Unknown (role needed first)

**Current status:** ✅ **JupyterHub manual execution is working and uploads to S3 automatically!**

**Recommended approach:** See `docs/JUPYTERHUB_QUICKSTART.md` - run standalone script on JupyterHub, results auto-upload to S3, download with `./scripts/sync_aws_db.sh` on Mac.

---

This guide explains how to set up automatic execution of Cell Thalamus simulations on AWS Lambda (once permissions are granted).

## Architecture

```
Frontend (Mac)
    ↓ Click "Run Experiment"
Backend (localhost:8000)
    ↓ Invoke Lambda via boto3
AWS Lambda (cloud)
    ↓ Run standalone_cell_thalamus.py
    ↓ Upload results to S3
S3 (s3://insitro-user/brig/)
    ↓ Auto-sync via S3 watcher
Mac (data/cell_thalamus.db)
    ↓ Frontend displays results
```

## Prerequisites

1. **AWS CLI installed and configured**
   ```bash
   aws --version
   aws sso login --profile bedrock
   ```

2. **IAM Role for Lambda**
   You need to create an IAM role with:
   - Trust relationship: Lambda service
   - Permissions:
     - `AWSLambdaBasicExecutionRole` (CloudWatch Logs)
     - S3 write access to `s3://insitro-user/brig/*`

   **Create the role:**
   ```bash
   # Get your AWS account ID
   AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text --profile bedrock)
   echo "Your AWS Account ID: $AWS_ACCOUNT_ID"

   # Create trust policy
   cat > /tmp/lambda-trust-policy.json <<EOF
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Principal": {
           "Service": "lambda.amazonaws.com"
         },
         "Action": "sts:AssumeRole"
       }
     ]
   }
   EOF

   # Create role
   aws iam create-role \
       --role-name cell-thalamus-lambda-role \
       --assume-role-policy-document file:///tmp/lambda-trust-policy.json \
       --profile bedrock

   # Attach policies
   aws iam attach-role-policy \
       --role-name cell-thalamus-lambda-role \
       --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole \
       --profile bedrock

   # Create S3 access policy
   cat > /tmp/s3-policy.json <<EOF
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": [
           "s3:PutObject",
           "s3:PutObjectAcl"
         ],
         "Resource": "arn:aws:s3:::insitro-user/brig/*"
       }
     ]
   }
   EOF

   aws iam put-role-policy \
       --role-name cell-thalamus-lambda-role \
       --policy-name S3WriteAccess \
       --policy-document file:///tmp/s3-policy.json \
       --profile bedrock

   # Get role ARN (you'll need this)
   aws iam get-role \
       --role-name cell-thalamus-lambda-role \
       --query 'Role.Arn' \
       --output text \
       --profile bedrock
   ```

## Deployment Steps

### 1. Update Lambda Deployment Script

Edit `scripts/deploy_lambda.sh` and update:
```bash
LAMBDA_ROLE_ARN="arn:aws:iam::YOUR_ACCOUNT_ID:role/cell-thalamus-lambda-role"
```

Replace `YOUR_ACCOUNT_ID` with your AWS account ID from above.

### 2. Deploy Lambda Function

```bash
cd /Users/bjh/cell_OS
./scripts/deploy_lambda.sh
```

This will:
- Package the Lambda function with dependencies (numpy, tqdm, boto3)
- Create or update the Lambda function
- Configure 15-minute timeout and 3GB memory

### 3. Test Lambda Manually

Test that Lambda works:
```bash
aws lambda invoke \
    --function-name cell-thalamus-simulator \
    --payload '{"candidates":[{"compound":"CCCP","cell_line":"A549","timepoint_h":12.0,"wells":12,"priority":"Primary"}]}' \
    --profile bedrock \
    response.json

cat response.json
```

Check S3 for results:
```bash
aws s3 ls s3://insitro-user/brig/ --profile bedrock
```

### 4. Enable Lambda in Backend

Set environment variable to use Lambda:
```bash
export USE_LAMBDA=true
export LAMBDA_FUNCTION_NAME=cell-thalamus-simulator
export AWS_REGION=us-west-2
export AWS_PROFILE=bedrock
```

Or add to your `.env` file:
```
USE_LAMBDA=true
LAMBDA_FUNCTION_NAME=cell-thalamus-simulator
AWS_REGION=us-west-2
AWS_PROFILE=bedrock
```

### 5. Start Backend with Lambda Enabled

```bash
cd src/cell_os/api
USE_LAMBDA=true uvicorn thalamus_api:app --reload
```

You should see:
```
✓ Lambda client initialized (function: cell-thalamus-simulator, region: us-west-2)
```

### 6. Ensure S3 Watcher is Running

```bash
# Check status
./scripts/watch_s3_db.sh status

# Start if not running
./scripts/watch_s3_db.sh start
```

## Usage

1. **Open Frontend**: http://localhost:5173/autonomous-loop-tutorial
2. **Navigate to Execution Stage**
3. **Click "Run Real Experiment (192 wells)"**

**What happens:**
- Frontend sends portfolio to backend
- Backend invokes Lambda (you'll see `🚀 Invoking Lambda` in logs)
- Lambda runs simulation in cloud (15 min max)
- Lambda uploads DB to S3
- S3 watcher detects change and downloads
- Frontend shows results automatically

## Monitoring

**Backend logs:**
```bash
tail -f api.log  # or wherever uvicorn logs
```

**Lambda logs:**
```bash
aws logs tail /aws/lambda/cell-thalamus-simulator --follow --profile bedrock
```

**S3 sync logs:**
```bash
tail -f /tmp/cell_thalamus_s3_watcher.log
```

## Troubleshooting

### Lambda not invoking
- Check `USE_LAMBDA=true` is set
- Check AWS credentials: `aws sts get-caller-identity --profile bedrock`
- Check backend logs for errors

### Lambda timeout
- Lambda has 15-minute limit
- For larger experiments, increase timeout or use AWS Batch instead
- Check CloudWatch logs for errors

### Results not appearing
- Check S3 watcher is running: `./scripts/watch_s3_db.sh status`
- Manually check S3: `aws s3 ls s3://insitro-user/brig/ --profile bedrock`
- Force download: `./scripts/sync_aws_db.sh`

### Local Fallback

To run locally (without Lambda):
```bash
export USE_LAMBDA=false
# or just don't set USE_LAMBDA
```

## Cost Estimation

**Lambda pricing** (us-west-2):
- Compute: $0.0000166667 per GB-second
- 3GB memory × 900 seconds (15 min) = 2700 GB-seconds
- Cost per run: ~$0.045 (4.5 cents)

**S3 pricing:**
- Storage: $0.023 per GB/month
- 50 MB database = ~$0.001/month
- PUT requests: negligible

**Total:** ~5 cents per experiment run

## Next Steps

For even more scalability:
- **AWS Batch**: For longer-running experiments (>15 minutes)
- **ECS Fargate**: For persistent workers
- **Step Functions**: For complex multi-stage workflows

Current Lambda setup is ideal for experiments under 15 minutes.
