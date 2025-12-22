"""
Beam Search Module

Phase 6A: Beam search over action sequences under hard constraints.

Architecture:
- action_bias.py: Action intent classification and governance-driven biasing
- types.py: Dataclasses (BeamNode, BeamSearchResult, PrefixRolloutResult, NoCommitEpisode)
- runner.py: Phase5EpisodeRunner (episode execution with Phase 5 classifier)
- search.py: Main BeamSearch class (search algorithm)

Usage:
    from cell_os.hardware.beam_search import BeamSearch, BeamSearchResult, BeamNode

    searcher = BeamSearch(vm, n_steps=8, beam_width=10)
    result = searcher.search(compound_id="nocodazole")
"""

from .action_bias import (
    ActionIntent,
    classify_action_intent,
    action_intent_cost,
    compute_action_bias,
)
from .types import (
    PrefixRolloutResult,
    BeamNode,
    NoCommitEpisode,
    BeamSearchResult,
)
from .runner import Phase5EpisodeRunner
from .search import BeamSearch

__all__ = [
    # Action bias
    'ActionIntent',
    'classify_action_intent',
    'action_intent_cost',
    'compute_action_bias',
    # Types
    'PrefixRolloutResult',
    'BeamNode',
    'NoCommitEpisode',
    'BeamSearchResult',
    # Main classes
    'Phase5EpisodeRunner',
    'BeamSearch',
]
