# IAM Role Request for Cell Thalamus Lambda

**Requestor:** bjh
**Account ID:** 298579124006
**Purpose:** Enable automated Cell Thalamus simulations on AWS Lambda

## Role Configuration Needed

**Role Name:** `cell-thalamus-lambda-role`

**Trust Relationship:**
```json
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
```

**Required Permissions:**

1. **CloudWatch Logs** (attach managed policy):
   - `arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole`

2. **S3 Write Access** (inline policy):
   ```json
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
   ```

## Why This is Needed

- Lambda function will run Python simulations (15 min max)
- Results (SQLite database, ~50MB) will be written to `s3://insitro-user/brig/cell_thalamus_results.db`
- This automates what I currently do manually on JupyterHub

## Alternative

If creating a new role is blocked, can you add S3 write permissions to existing `lambda_basic_execution` role?

Current permission: `arn:aws:s3:::insitro-papers/*`
Need: `arn:aws:s3:::insitro-user/brig/*`
