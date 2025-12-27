"""
Edge Effect Belief Updater

Detects spatial bias by comparing edge vs center wells.
Tracks per-channel effect magnitudes using exponential moving average.
"""

from typing import List
import numpy as np

from .base import BaseBeliefUpdater
from ..ledger import cond_key


class EdgeBeliefUpdater(BaseBeliefUpdater):
    """
    Updates edge effect beliefs by comparing matched edge/center pairs.

    Tracks:
    - Per-channel effect magnitudes (exponential moving average)
    - Test count
    - Confidence gate (2+ tests with consistent effects >5%)
    """

    def update(self, conditions: List) -> None:
        """
        Update edge effect beliefs from matched edge/center pairs.

        Args:
            conditions: List of ConditionSummary objects
        """
        edge_conditions, center_conditions = self._group_by_position(conditions)
        matched_pairs = set(edge_conditions.keys()) & set(center_conditions.keys())

        if not matched_pairs:
            return

        # Compute per-channel effects
        new_effects_by_channel, supporting = self._compute_effects(
            edge_conditions, center_conditions, matched_pairs
        )

        # Update tracked fields
        self._update_effect_fields(new_effects_by_channel, matched_pairs, supporting)

        # Evaluate confidence gate
        self._update_confidence_gate(supporting)

    def _group_by_position(self, conditions: List):
        """Group conditions by position (edge vs center)."""
        edge_conditions = {}
        center_conditions = {}

        for cond in conditions:
            key = (cond.cell_line, cond.compound, cond.dose_uM, cond.time_h, cond.assay)
            if cond.position_tag == 'edge':
                edge_conditions[key] = cond
            elif cond.position_tag == 'center':
                center_conditions[key] = cond

        return edge_conditions, center_conditions

    def _compute_effects(self, edge_conditions, center_conditions, matched_pairs):
        """Compute per-channel effect sizes for matched pairs."""
        new_effects_by_channel = dict(self.beliefs.edge_effect_strength_by_channel)
        supporting = []

        for key in matched_pairs:
            edge = edge_conditions[key]
            center = center_conditions[key]

            supporting.append(cond_key(edge))
            supporting.append(cond_key(center))

            if edge.feature_means and center.feature_means:
                for channel in edge.feature_means:
                    if channel in center.feature_means:
                        edge_val = edge.feature_means[channel]
                        center_val = center.feature_means[channel]

                        # Phase 4: Skip SNR-masked channels (None values)
                        if edge_val is None or center_val is None:
                            continue

                        if center_val > 0:
                            effect = (edge_val - center_val) / center_val

                            # Accumulate effects (exponential moving average)
                            if channel not in new_effects_by_channel:
                                new_effects_by_channel[channel] = effect
                            else:
                                alpha = 0.7  # weight new observation more
                                old = new_effects_by_channel[channel]
                                new_effects_by_channel[channel] = alpha * effect + (1 - alpha) * old

        return new_effects_by_channel, supporting

    def _update_effect_fields(self, new_effects_by_channel, matched_pairs, supporting):
        """Update edge effect tracking fields."""
        self.beliefs._set(
            "edge_tests_run",
            self.beliefs.edge_tests_run + 1,
            evidence={"n_tests": self.beliefs.edge_tests_run + 1, "n_pairs": len(matched_pairs)},
            supporting_conditions=supporting,
            note=f"Edge test #{self.beliefs.edge_tests_run + 1}"
        )

        self.beliefs._set(
            "edge_effect_strength_by_channel",
            new_effects_by_channel,
            evidence={
                "n_channels": len(new_effects_by_channel),
                "effects_sample": {k: float(v) for k, v in list(new_effects_by_channel.items())[:3]}
            },
            supporting_conditions=supporting,
            note=f"Updated edge effects for {len(new_effects_by_channel)} channels"
        )

    def _update_confidence_gate(self, supporting):
        """Determine if edge effects are confident (2+ tests, consistent >5%)."""
        if self.beliefs.edge_tests_run >= 2 and self.beliefs.edge_effect_strength_by_channel:
            strong_effects = [abs(e) > 0.05 for e in self.beliefs.edge_effect_strength_by_channel.values()]
            n_strong = sum(strong_effects)
            new_confident = n_strong > 0

            # Compute summary evidence
            effect_magnitudes = [abs(e) for e in self.beliefs.edge_effect_strength_by_channel.values()]
            mean_effect = float(np.mean(effect_magnitudes)) if effect_magnitudes else 0.0

            self.beliefs._set(
                "edge_effect_confident",
                new_confident,
                evidence={
                    "n_tests": self.beliefs.edge_tests_run,
                    "n_channels": len(self.beliefs.edge_effect_strength_by_channel),
                    "n_strong_effects": n_strong,
                    "mean_abs_effect": mean_effect,
                    "threshold": 0.05,
                    "effects_by_channel": {k: float(v) for k, v in list(self.beliefs.edge_effect_strength_by_channel.items())[:5]},
                },
                supporting_conditions=supporting,
                note=f"Edge bias detected in {n_strong}/{len(self.beliefs.edge_effect_strength_by_channel)} channels" if new_confident else "Edge effect not yet confident",
            )
