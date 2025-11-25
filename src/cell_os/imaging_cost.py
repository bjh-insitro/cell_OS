# -*- coding: utf-8 -*-
"""Cost calculator for imaging experiments.

Integrates with the economic engine to calculate costs for proposed imaging doses.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional

from cell_os.imaging_acquisition import ExperimentPlan


@dataclass
class ImagingCost:
    """Cost breakdown for an imaging experiment.
    
    Attributes
    ----------
    experiment_plan : ExperimentPlan
        The proposed experiment.
    reagent_cost_usd : float
        Cost of reagents (media, stressor, dyes).
    consumable_cost_usd : float
        Cost of plates, tips, etc.
    instrument_cost_usd : float
        Amortized cost of microscope time.
    total_cost_usd : float
        Total cost for this experiment.
    """
    experiment_plan: ExperimentPlan
    reagent_cost_usd: float
    consumable_cost_usd: float
    instrument_cost_usd: float
    total_cost_usd: float


def calculate_imaging_cost(
    plan: ExperimentPlan,
    wells_per_dose: int = 3,
    fields_per_well: int = 9,
    imaging_time_per_field_min: float = 0.5,
    microscope_cost_per_hour: float = 50.0,
) -> ImagingCost:
    """Calculate cost for a single imaging experiment.
    
    Parameters
    ----------
    plan : ExperimentPlan
        The proposed experiment.
    wells_per_dose : int
        Number of replicate wells per dose.
    fields_per_well : int
        Number of fields to image per well.
    imaging_time_per_field_min : float
        Time to acquire one field (minutes).
    microscope_cost_per_hour : float
        Amortized cost of microscope usage ($/hour).
    
    Returns
    -------
    ImagingCost
        Cost breakdown for this experiment.
    """
    # Reagent costs (simplified - could integrate with Inventory)
    # Assume: media, stressor, CellROX, Hoechst
    media_cost_per_well = 0.50  # $0.50 per well for media
    stressor_cost_per_well = 0.10  # $0.10 per well for TBHP
    dye_cost_per_well = 0.20  # $0.20 per well for CellROX + Hoechst
    
    reagent_cost = wells_per_dose * (media_cost_per_well + stressor_cost_per_well + dye_cost_per_well)
    
    # Consumable costs
    plate_cost = 15.0  # $15 per 96-well plate (assume 1 plate per experiment)
    tip_cost = 2.0  # $2 for tips
    
    consumable_cost = plate_cost + tip_cost
    
    # Instrument costs
    total_fields = wells_per_dose * fields_per_well
    imaging_time_hours = (total_fields * imaging_time_per_field_min) / 60.0
    instrument_cost = imaging_time_hours * microscope_cost_per_hour
    
    total_cost = reagent_cost + consumable_cost + instrument_cost
    
    return ImagingCost(
        experiment_plan=plan,
        reagent_cost_usd=reagent_cost,
        consumable_cost_usd=consumable_cost,
        instrument_cost_usd=instrument_cost,
        total_cost_usd=total_cost,
    )


def calculate_batch_cost(
    plans: List[ExperimentPlan],
    wells_per_dose: int = 3,
    fields_per_well: int = 9,
) -> float:
    """Calculate total cost for a batch of experiments.
    
    Parameters
    ----------
    plans : List[ExperimentPlan]
        List of proposed experiments.
    wells_per_dose : int
        Number of replicate wells per dose.
    fields_per_well : int
        Number of fields to image per well.
    
    Returns
    -------
    total_cost_usd : float
        Total cost for the batch.
    """
    total = 0.0
    for plan in plans:
        cost = calculate_imaging_cost(plan, wells_per_dose, fields_per_well)
        total += cost.total_cost_usd
    return total


def get_cost_per_information_bit(
    plan: ExperimentPlan,
    uncertainty_reduction: float,
    wells_per_dose: int = 3,
) -> float:
    """Calculate cost per bit of information gained.
    
    Parameters
    ----------
    plan : ExperimentPlan
        The proposed experiment.
    uncertainty_reduction : float
        Expected reduction in posterior uncertainty (bits).
    wells_per_dose : int
        Number of replicate wells.
    
    Returns
    -------
    cost_per_bit : float
        Cost per bit of information ($/bit).
    """
    cost = calculate_imaging_cost(plan, wells_per_dose)
    if uncertainty_reduction <= 0:
        return float('inf')
    return cost.total_cost_usd / uncertainty_reduction
