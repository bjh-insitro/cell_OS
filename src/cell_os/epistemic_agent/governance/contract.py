# src/cell_os/epistemic_agent/governance/contract.py

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional, Set


class GovernanceAction(str, Enum):
    COMMIT = "COMMIT"
    NO_COMMIT = "NO_COMMIT"
    NO_DETECTION = "NO_DETECTION"


class Blocker(str, Enum):
    """
    Machine-readable reasons for NO_COMMIT.

    Used by action biasing to decide what to do about the block.
    """
    LOW_POSTERIOR_TOP = "LOW_POSTERIOR_TOP"  # Need more mechanism discrimination
    HIGH_NUISANCE = "HIGH_NUISANCE"  # Need to reduce confounding
    BAD_INPUT = "BAD_INPUT"  # Garbage inputs rejected


@dataclass(frozen=True)
class GovernanceInputs:
    """
    Minimal, model-agnostic inputs to the governance gate.

    Interpretations:
      - posterior: mechanism -> probability mass (should sum ~ 1.0, but we don't force it here)
      - nuisance_prob: probability that the signal is explained by nuisance/context/pipeline (0..1)
      - evidence_strength: scalar "there is a signal" proxy (0..1)
          - used to prevent cowardice: if evidence_strength is high, NO_DETECTION is disallowed
    """
    posterior: Dict[str, float]
    nuisance_prob: float
    evidence_strength: float


@dataclass(frozen=True)
class GovernanceThresholds:
    """
    Contract knobs. Keep these stable and explicit.

    - commit_posterior_min: minimum posterior mass of top mechanism to allow commit
    - nuisance_max_for_commit: maximum nuisance probability allowed to commit
    - evidence_min_for_detection: if evidence_strength >= this, NO_DETECTION is forbidden
    """
    commit_posterior_min: float = 0.80
    nuisance_max_for_commit: float = 0.35
    evidence_min_for_detection: float = 0.70


@dataclass(frozen=True)
class GovernanceDecision:
    action: GovernanceAction
    mechanism: Optional[str]
    reason: str
    blockers: Set[Blocker]  # Machine-readable reasons for NO_COMMIT (empty if COMMIT/NO_DETECTION)


def _top_mechanism(posterior: Dict[str, float]) -> tuple[Optional[str], float]:
    if not posterior:
        return None, 0.0
    mech = max(posterior, key=lambda k: posterior[k])
    return mech, float(posterior[mech])


def decide_governance(
    x: GovernanceInputs,
    t: GovernanceThresholds = GovernanceThresholds(),
) -> GovernanceDecision:
    """
    Pure governance contract.

    Priority order:
      1) If evidence is strong, you may NOT claim NO_DETECTION.
      2) You may COMMIT only if top posterior is strong AND nuisance is low.
      3) Otherwise NO_COMMIT, unless low evidence allows NO_DETECTION.

    This is intentionally boring. Boring is good. Boring is enforceable.
    """
    # Input validation: reject garbage before it becomes a decision
    if not (0.0 <= x.nuisance_prob <= 1.0):
        return GovernanceDecision(
            action=GovernanceAction.NO_COMMIT,
            mechanism=None,
            reason=f"bad_input: nuisance_prob={x.nuisance_prob} out of range [0,1]",
            blockers={Blocker.BAD_INPUT},
        )

    if not (0.0 <= x.evidence_strength <= 1.0):
        return GovernanceDecision(
            action=GovernanceAction.NO_COMMIT,
            mechanism=None,
            reason=f"bad_input: evidence_strength={x.evidence_strength} out of range [0,1]",
            blockers={Blocker.BAD_INPUT},
        )

    top_mech, top_p = _top_mechanism(x.posterior)

    # 1) Anti-cowardice: if evidence is strong, NO_DETECTION is not allowed.
    strong_evidence = x.evidence_strength >= t.evidence_min_for_detection

    # 2) Commit rule: requires both strong posterior and low nuisance.
    commit_allowed = (
        top_mech is not None
        and top_p >= t.commit_posterior_min
        and x.nuisance_prob <= t.nuisance_max_for_commit
    )

    if commit_allowed:
        return GovernanceDecision(
            action=GovernanceAction.COMMIT,
            mechanism=top_mech,
            reason=f"commit: top_p={top_p:.3f} nuisance={x.nuisance_prob:.3f}",
            blockers=set(),  # No blockers when committing
        )

    # If we cannot commit, identify blockers
    blockers = set()
    if top_p < t.commit_posterior_min:
        blockers.add(Blocker.LOW_POSTERIOR_TOP)
    if x.nuisance_prob > t.nuisance_max_for_commit:
        blockers.add(Blocker.HIGH_NUISANCE)

    # If we cannot commit:
    if strong_evidence:
        return GovernanceDecision(
            action=GovernanceAction.NO_COMMIT,
            mechanism=None,
            reason=(
                "no_commit: evidence strong but commit conditions not met "
                f"(top_p={top_p:.3f}, nuisance={x.nuisance_prob:.3f})"
            ),
            blockers=blockers,
        )

    # Low evidence: NO_DETECTION is allowed.
    return GovernanceDecision(
        action=GovernanceAction.NO_DETECTION,
        mechanism=None,
        reason=f"no_detection: evidence={x.evidence_strength:.3f} below threshold",
        blockers=set(),  # No blockers for NO_DETECTION (low evidence is not a failure)
    )
