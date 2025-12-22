"""
Base interface for belief updaters.

Each updater is responsible for updating a specific aspect of beliefs
based on observations (conditions).
"""

from abc import ABC, abstractmethod
from typing import List, Any


class BaseBeliefUpdater(ABC):
    """
    Abstract base class for belief update strategies.

    Each updater has access to the belief state and can update
    specific fields based on observed conditions.
    """

    def __init__(self, belief_state: 'BeliefState'):
        """
        Initialize updater with reference to belief state.

        Args:
            belief_state: The BeliefState instance to update
        """
        self.beliefs = belief_state

    @abstractmethod
    def update(self, conditions: List, **kwargs) -> Any:
        """
        Update beliefs based on observed conditions.

        Args:
            conditions: List of ConditionSummary objects
            **kwargs: Additional updater-specific parameters

        Returns:
            Updater-specific output (e.g., diagnostics)
        """
        pass
