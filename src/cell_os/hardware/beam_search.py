"""
Phase 6A: Beam search over action sequences.

DEPRECATED: This file is now a compatibility shim.
Import from beam_search submodule instead:

    from cell_os.hardware.beam_search import BeamSearch, BeamSearchResult

The module has been refactored into:
- beam_search/action_bias.py: Action intent and biasing
- beam_search/types.py: Dataclasses
- beam_search/runner.py: Phase5EpisodeRunner
- beam_search/search.py: Main BeamSearch class
"""

# Re-export everything from submodule for backward compatibility
from .beam_search import (
    ActionIntent,
    classify_action_intent,
    action_intent_cost,
    compute_action_bias,
    PrefixRolloutResult,
    BeamNode,
    NoCommitEpisode,
    BeamSearchResult,
    Phase5EpisodeRunner,
    BeamSearch,
)

__all__ = [
    'ActionIntent',
    'classify_action_intent',
    'action_intent_cost',
    'compute_action_bias',
    'PrefixRolloutResult',
    'BeamNode',
    'NoCommitEpisode',
    'BeamSearchResult',
    'Phase5EpisodeRunner',
    'BeamSearch',
]
