import pytest

from cell_os.llm_scientist import LLMScientist, ScientificInsight, CandidateHypothesis


def test_llm_scientist_basic_structure():
    scientist = LLMScientist(model_name="mock")
    log = "## Cycle 1\nViability decreased with dose."

    insight = scientist.analyze_mission_log(log)

    # Types
    assert isinstance(insight, ScientificInsight)
    assert isinstance(insight.summary, str)
    assert isinstance(insight.hypotheses, list)
    assert isinstance(insight.meta_confidence, float)

    # Content sanity checks
    assert "Cycle" in insight.summary
    assert len(insight.hypotheses) >= 1

    for h in insight.hypotheses:
        assert isinstance(h, CandidateHypothesis)
        assert isinstance(h.text, str) and h.text
        assert isinstance(h.rationale, str) and h.rationale
        assert 0.0 <= h.likelihood <= 1.0

    assert 0.0 <= insight.meta_confidence <= 1.0
