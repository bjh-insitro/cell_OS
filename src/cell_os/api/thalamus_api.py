"""
Cell Thalamus FastAPI Backend

REST API for Cell Thalamus dashboard - provides endpoints for:
- Running simulations (Demo/Quick/Full modes)
- Retrieving experimental results
- Performing variance analysis
- Getting sentinel SPC data
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any
import logging
from pathlib import Path
import os

logger = logging.getLogger(__name__)

# ============================================================================
# Application Setup
# ============================================================================

# Initialize FastAPI app
app = FastAPI(title="Cell Thalamus API", version="1.0.0")

# CORS middleware for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# Global State
# ============================================================================

# In-memory storage for running simulations
running_simulations: Dict[str, Dict[str, Any]] = {}

# Database path - use absolute path to work from any directory
DB_PATH = str(Path(__file__).parent.parent.parent.parent / "data" / "cell_thalamus.db")

# Lambda configuration
USE_LAMBDA = os.getenv('USE_LAMBDA', 'false').lower() == 'true'
LAMBDA_FUNCTION_NAME = os.getenv('LAMBDA_FUNCTION_NAME', 'cell-thalamus-simulator')
AWS_REGION = os.getenv('AWS_REGION', 'us-west-2')
AWS_PROFILE = os.getenv('AWS_PROFILE', 'bedrock')

# Initialize Lambda client if using Lambda
lambda_client = None
if USE_LAMBDA:
    try:
        import boto3  # Only import if using Lambda
        session = boto3.Session(profile_name=AWS_PROFILE)
        lambda_client = session.client('lambda', region_name=AWS_REGION)
        logger.info(f"✓ Lambda client initialized (function: {LAMBDA_FUNCTION_NAME}, region: {AWS_REGION})")
    except ImportError:
        logger.warning("boto3 not installed. Install with: pip install boto3. Falling back to local execution.")
        USE_LAMBDA = False
    except Exception as e:
        logger.warning(f"Failed to initialize Lambda client: {e}. Falling back to local execution.")
        USE_LAMBDA = False

# ============================================================================
# Root Endpoint
# ============================================================================

@app.get("/")
async def root():
    """API health check"""
    return {"status": "ok", "service": "Cell Thalamus API"}

# ============================================================================
# Register Route Modules
# ============================================================================

from .routes import simulations, designs, results, analysis, catalog, watcher, plates, epistemic

# Initialize global state in route modules that need it
simulations.init_globals(running_simulations, DB_PATH, USE_LAMBDA, lambda_client, LAMBDA_FUNCTION_NAME)
designs.init_globals(running_simulations, DB_PATH)
results.init_globals(DB_PATH)
analysis.init_globals(DB_PATH)
plates.init_globals(DB_PATH)

# Register all routers
app.include_router(simulations.router, tags=["Simulations"])
app.include_router(designs.router, tags=["Designs"])
app.include_router(results.router, tags=["Results"])
app.include_router(analysis.router, tags=["Analysis"])
app.include_router(catalog.router, tags=["Catalog"])
app.include_router(watcher.router, tags=["Watcher"])
app.include_router(plates.router, tags=["Plates"])
app.include_router(epistemic.router, tags=["Epistemic Agent"])

logger.info("✓ Cell Thalamus API routes registered")

# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
