"""
Cell Thalamus API Server Entry Point

Run with: python src/cell_os/api/main.py
or: uvicorn cell_os.api.thalamus_api:app --reload
"""

import uvicorn
from cell_os.api.thalamus_api import app

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 Starting Cell Thalamus API Server")
    print("=" * 60)
    print("API Documentation: http://localhost:8000/docs")
    print("API Base URL: http://localhost:8000/api/thalamus")
    print("=" * 60)

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
