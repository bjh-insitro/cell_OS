"""
llm_scientist.py

Module for the "LLM Scientist" agent that reflects on mission logs
(and eventually world models) and generates scientific hypotheses.

Currently uses a mock heuristic implementation, but the API is shaped so you
can later plug in a real LLM-backed agent without touching callers.
"""

from dataclasses import dataclass
from typing import List, Optional, Any


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class CandidateHypothesis:
    """
    A single candidate hypothesis produced by the scientist.

    Attributes
    ----------
    text:
        The core hypothesis statement.
    rationale:
        Short explanation of why the agent believes this hypothesis.
    likelihood:
        Agent's subjective probability that this hypothesis explains
        the observations, in [0.0, 1.0].
    """
    text: str
    rationale: str
    likelihood: float


@dataclass
class ScientificInsight:
    """
    Container for the scientist's reflection on a mission log.

    Attributes
    ----------
    summary:
        Concise natural language summary of what happened.
    hypotheses:
        List of candidate hypotheses, preferably ordered from most to
        least likely.
    meta_confidence:
        Confidence that the *overall* analysis is meaningful given the
        available data, in [0.0, 1.0].
    """
    summary: str
    hypotheses: List[CandidateHypothesis]
    meta_confidence: float


# ---------------------------------------------------------------------------
# Scientist agent
# ---------------------------------------------------------------------------

class LLMScientist:
    """
    A simple "LLM Scientist" abstraction.

    For now this is mostly a wrapper around a mock heuristic implementation.
    Later you can:
      - Replace `_mock_analyze` with a call out to a real LLM.
      - Pass in richer structures (world model, metadata, GP surfaces).
      - Extend outputs to include experiment suggestions, anomaly flags, etc.
    """

    def __init__(self, model_name: str = "mock") -> None:
        self.model_name = model_name

    # Public API -------------------------------------------------------------

    def analyze(
        self,
        mission_log: str,
        world_model: Optional[Any] = None,
    ) -> ScientificInsight:
        """
        Analyze a mission log (and optionally a world model) and return a
        structured scientific insight.

        Parameters
        ----------
        mission_log:
            The textual mission log content, for example a markdown log
            produced by your agent after running a cycle.
        world_model:
            Optional structured state of the world, for example a Phase0WorldModel
            instance. Currently unused in the mock implementation but included
            here so you do not have to change call sites later.

        Returns
        -------
        ScientificInsight
            Summary plus a ranked list of candidate hypotheses.
        """
        if self.model_name == "mock":
            return self._mock_analyze(mission_log, world_model)

        # Placeholder for future real models
        raise NotImplementedError(
            f"Model '{self.model_name}' is not implemented yet."
        )

    def analyze_mission_log(self, log_content: str) -> ScientificInsight:
        """
        Backwards compatible wrapper around `analyze`.

        Existing code that calls `analyze_mission_log` can keep doing so.
        Internally we just delegate to `analyze` with no world model.
        """
        return self.analyze(mission_log=log_content, world_model=None)

    # Internal implementations ----------------------------------------------

    def _mock_analyze(
        self,
        mission_log: str,
        world_model: Optional[Any] = None,
    ) -> ScientificInsight:
        """
        Heuristic-based analysis for the mock scientist.

        Very simple pattern matching on the mission log. This is only
        meant as scaffolding and for tests, not as a serious scientist.
        """
        # 1. Simple cycle counting for the summary
        n_cycles = mission_log.count("## Cycle")
        if n_cycles == 0:
            cycle_fragment = "No explicit Cycles were recorded."
        elif n_cycles == 1:
            cycle_fragment = "Completed 1 recorded Cycle of autonomous experimentation."
        else:
            cycle_fragment = f"Completed {n_cycles} recorded Cycles of autonomous experimentation."

        summary = (
            f"{cycle_fragment} "
            "Observed dose dependent viability changes across conditions."
        )

        # 2. Build candidate hypotheses
        hypotheses: List[CandidateHypothesis] = []

        # Cell line specific patterns
        has_hepg2 = "HepG2" in mission_log
        has_u2os = "U2OS" in mission_log

        if has_hepg2 and has_u2os:
            hypotheses.append(
                CandidateHypothesis(
                    text=(
                        "The compound engages a HepG2 biased metabolic or stress response "
                        "pathway, leading to differential toxicity between HepG2 and U2OS."
                    ),
                    rationale=(
                        "Mission log mentions both HepG2 and U2OS with differing viability "
                        "trends across the same dose ladder."
                    ),
                    likelihood=0.6,
                )
            )
        elif has_hepg2:
            hypotheses.append(
                CandidateHypothesis(
                    text="The compound primarily affects liver like cells represented by HepG2.",
                    rationale=(
                        "Mission log focuses on HepG2 responses with no direct comparator cell line."
                    ),
                    likelihood=0.5,
                )
            )
        elif has_u2os:
            hypotheses.append(
                CandidateHypothesis(
                    text="The compound exerts general cytotoxicity in U2OS without clear lineage specificity.",
                    rationale="Only U2OS is mentioned, with viability decreasing at higher doses.",
                    likelihood=0.45,
                )
            )

        # Compound specific hints
        compound_hints_added = False
        if "staurosporine" in mission_log.lower():
            compound_hints_added = True
            hypotheses.append(
                CandidateHypothesis(
                    text="Observed effects are consistent with broad kinase inhibition by staurosporine.",
                    rationale=(
                        "Staurosporine is referenced, and the log suggests sharp viability loss "
                        "at mid to high doses across multiple lines."
                    ),
                    likelihood=0.7,
                )
            )
        if "tunicamycin" in mission_log.lower():
            compound_hints_added = True
            hypotheses.append(
                CandidateHypothesis(
                    text="ER stress and unfolded protein response are likely primary drivers of toxicity.",
                    rationale="Tunicamycin is mentioned and is known to induce ER stress.",
                    likelihood=0.65,
                )
            )

        # Fallback generic hypotheses
        if not hypotheses:
            hypotheses.append(
                CandidateHypothesis(
                    text="The compound exhibits dose dependent cytotoxicity with no clear mechanism resolved yet.",
                    rationale="Viability shifts with dose, but log lacks mechanistic markers or comparators.",
                    likelihood=0.4,
                )
            )

        if not compound_hints_added:
            hypotheses.append(
                CandidateHypothesis(
                    text="Observed effects may reflect nonspecific oxidative or metabolic stress.",
                    rationale=(
                        "No strong compound identity cues found, but the pattern of viability vs dose "
                        "is consistent with generic stress induction."
                    ),
                    likelihood=0.35,
                )
            )

        # 3. Meta confidence
        meta_confidence = 0.5
        if n_cycles >= 2:
            meta_confidence += 0.1
        if has_hepg2 and has_u2os:
            meta_confidence += 0.1
        if compound_hints_added:
            meta_confidence += 0.1

        meta_confidence = max(0.0, min(1.0, meta_confidence))

        return ScientificInsight(
            summary=summary,
            hypotheses=hypotheses,
            meta_confidence=meta_confidence,
        )
