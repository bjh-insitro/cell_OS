"""
Lambda Service

AWS Lambda invocation for simulation offloading.
"""

import logging
import json
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


def invoke_lambda_simulation(
    design_id: str,
    candidates: List,
    lambda_client,
    lambda_function_name: str,
    running_simulations: Dict[str, Dict[str, Any]]
):
    """Invoke AWS Lambda to run simulation"""
    try:
        # Prepare payload
        payload = {
            'design_id': design_id,
            'candidates': [c.dict() if hasattr(c, 'dict') else c for c in candidates]
        }

        logger.info(f"Invoking Lambda with {len(candidates)} candidates...")

        # Invoke Lambda asynchronously
        response = lambda_client.invoke(
            FunctionName=lambda_function_name,
            InvocationType='Event',  # Async invocation
            Payload=json.dumps(payload)
        )

        status_code = response['StatusCode']
        if status_code == 202:
            running_simulations[design_id]["status"] = "running_lambda"
            running_simulations[design_id]["lambda_invoked"] = True
            logger.info(f"✓ Lambda invoked successfully (status: {status_code})")
            logger.info(f"⏳ Simulation running on Lambda. Results will appear in S3 and auto-sync to local.")
        else:
            raise Exception(f"Lambda invocation failed with status: {status_code}")

    except Exception as e:
        logger.error(f"Lambda invocation failed: {e}")
        running_simulations[design_id]["status"] = "failed"
        running_simulations[design_id]["error"] = f"Lambda invocation failed: {str(e)}"
        raise
