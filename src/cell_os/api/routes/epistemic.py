"""
Epistemic Agent Routes

Endpoints for Phase 1 epistemic agent campaigns.
"""

import logging
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()

# Store running epistemic campaigns
running_epistemic_campaigns: Dict[str, Dict[str, Any]] = {}


class EpistemicCampaignRequest(BaseModel):
    """Request to start an epistemic agent campaign."""
    budget: int = 200
    n_iterations: int = 20
    cell_lines: Optional[List[str]] = None
    compounds: Optional[List[str]] = None


def _run_epistemic_campaign_task(campaign_id: str, budget: int, n_iterations: int):
    """Background task to run epistemic agent campaign."""
    try:
        from cell_os.cell_thalamus.epistemic_agent import EpistemicAgent

        # Update status
        running_epistemic_campaigns[campaign_id]["status"] = "running"

        # Initialize agent
        agent = EpistemicAgent(budget=budget)

        # Run campaign with progress updates
        iteration_stats = []

        for iteration in range(n_iterations):
            logger.info(f"Campaign {campaign_id}: Iteration {iteration + 1}/{n_iterations}")

            # Update progress
            running_epistemic_campaigns[campaign_id]["current_iteration"] = iteration + 1
            running_epistemic_campaigns[campaign_id]["progress"] = (iteration + 1) / n_iterations

            # Execute one iteration
            query = agent.acquisition_function()
            result = agent.execute_query(query)

            # Compute current metrics
            if len(agent.results) >= 4:
                from cell_os.cell_thalamus.epistemic_agent import InformationMetrics
                sep_ratio = InformationMetrics.compute_separation_ratio(
                    agent.results, agent.stress_class_map
                )
            else:
                sep_ratio = 0.0

            iteration_stats.append({
                'iteration': iteration + 1,
                'query': str(query),
                'separation_ratio': sep_ratio,
                'budget_remaining': agent.budget_remaining
            })

            # Update campaign status
            running_epistemic_campaigns[campaign_id]["latest_separation_ratio"] = sep_ratio
            running_epistemic_campaigns[campaign_id]["budget_remaining"] = agent.budget_remaining

        # Generate final summary
        summary = agent._generate_summary(iteration_stats)

        # Mark as completed
        running_epistemic_campaigns[campaign_id]["status"] = "completed"
        running_epistemic_campaigns[campaign_id]["summary"] = summary
        running_epistemic_campaigns[campaign_id]["completed_at"] = datetime.now().isoformat()

        logger.info(f"Campaign {campaign_id} completed")
        logger.info(f"  Final separation ratio: {summary['final_separation_ratio']:.3f}")

    except Exception as e:
        logger.error(f"Error in epistemic campaign {campaign_id}: {e}")
        running_epistemic_campaigns[campaign_id]["status"] = "failed"
        running_epistemic_campaigns[campaign_id]["error"] = str(e)


@router.post("/api/thalamus/epistemic/start")
async def start_epistemic_campaign(request: EpistemicCampaignRequest, background_tasks: BackgroundTasks):
    """
    Start a Phase 1 epistemic agent campaign.

    The agent will autonomously explore dose/timepoint space to discover
    which conditions maximize mechanistic information content.
    """
    try:
        from cell_os.cell_thalamus.epistemic_agent import EpistemicAgent

        campaign_id = str(uuid.uuid4())

        logger.info(f"Starting epistemic campaign {campaign_id}")
        logger.info(f"  Budget: {request.budget} wells")
        logger.info(f"  Iterations: {request.n_iterations}")

        # Initialize campaign tracking
        running_epistemic_campaigns[campaign_id] = {
            "status": "initializing",
            "budget": request.budget,
            "n_iterations": request.n_iterations,
            "started_at": datetime.now().isoformat(),
            "progress": 0,
            "current_iteration": 0
        }

        # Start campaign in background
        background_tasks.add_task(
            _run_epistemic_campaign_task,
            campaign_id,
            request.budget,
            request.n_iterations
        )

        return {
            "campaign_id": campaign_id,
            "status": "started",
            "budget": request.budget,
            "n_iterations": request.n_iterations
        }

    except Exception as e:
        logger.error(f"Error starting epistemic campaign: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/thalamus/epistemic/status/{campaign_id}")
async def get_epistemic_campaign_status(campaign_id: str):
    """Get status of a running epistemic campaign."""
    if campaign_id not in running_epistemic_campaigns:
        raise HTTPException(status_code=404, detail="Campaign not found")

    return running_epistemic_campaigns[campaign_id]


@router.get("/api/thalamus/epistemic/campaigns")
async def list_epistemic_campaigns():
    """List all epistemic campaigns (running and completed)."""
    return {
        "campaigns": [
            {
                "campaign_id": cid,
                "status": data["status"],
                "started_at": data.get("started_at"),
                "progress": data.get("progress", 0),
                "current_iteration": data.get("current_iteration", 0),
                "n_iterations": data.get("n_iterations", 0)
            }
            for cid, data in running_epistemic_campaigns.items()
        ]
    }
