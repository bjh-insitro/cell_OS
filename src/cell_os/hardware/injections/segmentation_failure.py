"""
Injection: Segmentation Failure (Adversarial Measurement Layer)

PROBLEM: Segmentation doesn't just add noise - it changes what gets counted.
This is the measurement system lying about sufficient statistics.

NOT a noise source. This is a **measurement distortion layer** that:
- Changes cell counts (merges, splits, drops)
- Distorts features (size, texture, intensity)
- Introduces QC gating (fails ugly wells, creating survivorship bias)

State Variables:
- segmentation_quality (q): Per-well quality score [0, 1]
  Determined by: density, debris, focus, saturation
- merge_count: Cells incorrectly merged (undercounts true N)
- split_count: Cells incorrectly split (overcounts true N)
- dropped_count: Cells dropped by QC filters
- feature_distortion: Per-feature systematic bias

Distortions Applied:
1. Count bias:
   - High density → merges dominate → undercount + inflate size
   - Low density + noise → splits dominate → overcount + deflate size
   - Debris → drops (QC filter)
2. Feature bias:
   - Low q → attenuated texture features
   - Low q → inflated intensity variance (noise amplification)
3. QC gating:
   - q < threshold → partial failure (NaNs, reduced confidence)
   - Creates survivorship bias (agent only sees "clean" data)

Exploits Blocked:
- "Cell count is ground truth": Segmentation miscounts
- "Features are unbiased summaries": Distortion is systematic
- "Bad wells fail noisily": QC gating hides failures
- "More data always helps": Survivorship bias from filtering

Real-World Motivation:
- CellProfiler, Cellpose, StarDist: all fail at high density (merges)
- Over-segmentation at low density with debris
- Nuclear fragmentation (apoptosis) → splits or drops
- Saturation → feature extraction artifacts
- "Clean" datasets come from aggressive QC filtering

Defeat Conditions:
- **Orthogonal assays**: Confluence (not segmentation) to validate count
- **Manual QC**: Human review of flagged wells
- **Count cross-validation**: Cell titer assays (ATP, LDH) to verify count
- **CANNOT FULLY DEFEAT**: Segmentation will always fail at edges
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional
import numpy as np
from .base import InjectionState, Injection, InjectionContext


# Segmentation quality model
QC_FAIL_THRESHOLD = 0.3  # Below this, well fails QC
DENSITY_PENALTY_HIGH = 0.85  # At 80% confluence
DENSITY_PENALTY_LOW = 0.95  # At 20% confluence
DEBRIS_PENALTY = 0.7  # With high debris
FOCUS_PENALTY = 0.6  # At ±5µm defocus
SATURATION_PENALTY = 0.75  # At 1.5× stain scale


@dataclass
class SegmentationFailureState(InjectionState):
    """
    Per-well segmentation quality and distortion tracking.

    This is NOT biological state - it's measurement system state.
    """
    # Quality score
    segmentation_quality: float = 1.0  # [0, 1], 1 = perfect

    # Count distortions
    merge_count: int = 0  # Cells merged (reduce observed count)
    split_count: int = 0  # Cells split (increase observed count)
    dropped_count: int = 0  # Cells dropped by QC

    # Feature distortions (multiplicative biases)
    texture_attenuation: float = 1.0  # <1 = features look smoother
    intensity_noise_inflation: float = 1.0  # >1 = noisier measurements
    size_bias: float = 1.0  # >1 = cells look bigger (merges)

    # QC flags
    qc_passed: bool = True
    qc_warnings: list = field(default_factory=list)

    def check_invariants(self) -> None:
        """Segmentation quality must be [0,1]."""
        assert 0 <= self.segmentation_quality <= 1.0, \
            f"Segmentation quality out of bounds: {self.segmentation_quality}"
        assert self.merge_count >= 0
        assert self.split_count >= 0
        assert self.dropped_count >= 0


class SegmentationFailureInjection(Injection):
    """
    Adversarial measurement layer: segmentation changes sufficient statistics.

    This is the most dangerous injection because it's INVISIBLE to the agent
    unless they validate counts with orthogonal assays.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}

        # Severity knobs
        self.enable_count_distortion = self.config.get('enable_count_distortion', True)
        self.enable_feature_distortion = self.config.get('enable_feature_distortion', True)
        self.enable_qc_gating = self.config.get('enable_qc_gating', True)
        self.qc_threshold = self.config.get('qc_threshold', QC_FAIL_THRESHOLD)

    def initialize_state(self, ctx: InjectionContext, rng: np.random.Generator) -> SegmentationFailureState:
        """Start with perfect segmentation quality (degrades over experiment)."""
        return SegmentationFailureState()

    def compute_segmentation_quality(
        self,
        confluence: float,
        debris_level: float,
        focus_offset_um: float,
        stain_scale: float,
        rng: np.random.Generator
    ) -> float:
        """
        Compute segmentation quality score q ∈ [0, 1].

        Lower q = worse segmentation = more distortion.

        Args:
            confluence: Cell density [0, 1]
            debris_level: Debris amount [0, 1] (from death, backaction)
            focus_offset_um: Defocus amount
            stain_scale: Stain intensity scale
            rng: Random generator

        Returns:
            q ∈ [0, 1]
        """
        q = 1.0

        # Density effects (U-shaped: bad at low and high)
        if confluence > 0.7:
            # High density → merges
            density_factor = DENSITY_PENALTY_HIGH - (confluence - 0.7) * 0.5
            q *= density_factor
        elif confluence < 0.3:
            # Low density + noise → splits (but less severe than merges)
            density_factor = DENSITY_PENALTY_LOW + (0.3 - confluence) * 0.2
            q *= density_factor

        # Debris effects
        if debris_level > 0.1:
            q *= DEBRIS_PENALTY + (1 - DEBRIS_PENALTY) * (1 - debris_level)

        # Focus effects (nonlinear: gentle then sharp drop)
        defocus_severity = abs(focus_offset_um) / 5.0  # Normalized to ±5µm
        if defocus_severity > 0.5:
            focus_factor = FOCUS_PENALTY + (1 - FOCUS_PENALTY) * (1 - defocus_severity)
            q *= focus_factor

        # Saturation effects (high stain scale → saturation artifacts)
        if stain_scale > 1.2:
            saturation_factor = SATURATION_PENALTY + (1 - SATURATION_PENALTY) * (1.2 / stain_scale)
            q *= saturation_factor

        # Add small random jitter (segmentation algorithm variance)
        q *= rng.uniform(0.95, 1.05)

        # Clamp
        q = np.clip(q, 0.0, 1.0)

        return q

    def distort_cell_count(
        self,
        true_count: int,
        segmentation_quality: float,
        confluence: float,
        rng: np.random.Generator
    ) -> tuple[int, int, int]:
        """
        Apply merge/split/drop distortions to true cell count.

        Returns:
            (observed_count, merge_count, split_count)
        """
        if not self.enable_count_distortion:
            return true_count, 0, 0

        q = segmentation_quality

        # Merge rate (undercounts): increases at high density, low q
        if confluence > 0.6:
            merge_rate = (1 - q) * 0.3 * (confluence - 0.6) / 0.4
        else:
            merge_rate = 0.0

        # Split rate (overcounts): increases at low density, low q
        if confluence < 0.4:
            split_rate = (1 - q) * 0.15 * (0.4 - confluence) / 0.4
        else:
            split_rate = 0.0

        # Drop rate (debris filter): increases with low q
        drop_rate = (1 - q) * 0.1 if q < 0.6 else 0.0

        # Apply distortions (order matters: drop, then merge, then split)
        # 1. Drop cells (removed entirely)
        dropped = rng.binomial(true_count, drop_rate)
        remaining = true_count - dropped

        # 2. Merge cells (reduce count)
        # Each merge event combines 2 cells → 1
        merge_events = int(rng.binomial(remaining, merge_rate))
        remaining -= merge_events  # Lost cells from merges

        # 3. Split cells (increase count)
        # Each split event creates 1 extra cell
        split_events = int(rng.binomial(remaining, split_rate))
        remaining += split_events

        observed_count = max(0, remaining)

        return observed_count, merge_events, split_events

    def distort_features(
        self,
        features: Dict[str, float],
        segmentation_quality: float,
        size_bias: float,
        rng: np.random.Generator
    ) -> Dict[str, float]:
        """
        Apply feature distortions based on segmentation quality.

        Low q → texture attenuation, noise inflation.
        Merges → inflated size.
        """
        if not self.enable_feature_distortion:
            return features

        q = segmentation_quality
        distorted = features.copy()

        # Texture attenuation (smoothing from poor segmentation)
        texture_factor = 0.7 + 0.3 * q
        for key in distorted:
            if 'texture' in key.lower() or 'granularity' in key.lower():
                distorted[key] *= texture_factor

        # Intensity noise inflation
        noise_inflation = 1.0 + (1 - q) * 0.3
        for key in distorted:
            if 'intensity' in key.lower():
                # Add multiplicative noise
                distorted[key] *= rng.normal(1.0, 0.05 * noise_inflation)

        # Size bias (merges inflate size, splits deflate)
        for key in distorted:
            if 'area' in key.lower() or 'size' in key.lower():
                distorted[key] *= size_bias

        return distorted

    def apply_qc_gating(
        self,
        segmentation_quality: float,
        confluence: float,
        debris_level: float
    ) -> tuple[bool, list]:
        """
        Decide if well passes QC. Failed wells → partial data or NaNs.

        Returns:
            (qc_passed, warnings)
        """
        if not self.enable_qc_gating:
            return True, []

        warnings = []

        # Hard fail: segmentation quality too low
        if segmentation_quality < self.qc_threshold:
            warnings.append(f"Low segmentation quality: {segmentation_quality:.2f}")

        # Soft warnings (don't fail, but flag)
        if confluence > 0.85:
            warnings.append(f"High confluence: {confluence:.2f} (merges likely)")

        if confluence < 0.15:
            warnings.append(f"Low confluence: {confluence:.2f} (sparse)")

        if debris_level > 0.3:
            warnings.append(f"High debris: {debris_level:.2f}")

        qc_passed = segmentation_quality >= self.qc_threshold

        return qc_passed, warnings

    def hook_cell_painting_assay(
        self,
        ctx: InjectionContext,
        state: SegmentationFailureState,
        true_count: int,
        true_morphology: Dict[str, float],
        confluence: float,
        debris_level: float,
        focus_offset_um: float,
        stain_scale: float,
        rng: np.random.Generator
    ) -> tuple[int, Dict[str, float], Dict[str, Any]]:
        """
        Distort cell painting measurements through segmentation failure.

        This is the core hook: measurement system lying about biology.

        Returns:
            (observed_count, distorted_morphology, qc_metadata)
        """
        # Compute segmentation quality
        q = self.compute_segmentation_quality(
            confluence=confluence,
            debris_level=debris_level,
            focus_offset_um=focus_offset_um,
            stain_scale=stain_scale,
            rng=rng
        )
        state.segmentation_quality = q

        # Distort count
        observed_count, merges, splits = self.distort_cell_count(
            true_count=true_count,
            segmentation_quality=q,
            confluence=confluence,
            rng=rng
        )
        state.merge_count = merges
        state.split_count = splits

        # Compute size bias (merges inflate size)
        if merges > 0:
            # Each merge event increases average size
            state.size_bias = 1.0 + (merges / true_count) * 0.5
        elif splits > 0:
            # Each split event decreases average size
            state.size_bias = 1.0 - (splits / true_count) * 0.3
        else:
            state.size_bias = 1.0

        # Distort features
        distorted_morphology = self.distort_features(
            features=true_morphology,
            segmentation_quality=q,
            size_bias=state.size_bias,
            rng=rng
        )

        # QC gating
        qc_passed, warnings = self.apply_qc_gating(
            segmentation_quality=q,
            confluence=confluence,
            debris_level=debris_level
        )
        state.qc_passed = qc_passed
        state.qc_warnings = warnings

        # Package QC metadata
        qc_metadata = {
            'segmentation_quality': q,
            'qc_passed': qc_passed,
            'qc_warnings': warnings,
            'true_count': true_count,
            'observed_count': observed_count,
            'merge_count': merges,
            'split_count': splits,
            'size_bias': state.size_bias
        }

        # If QC failed, return degraded data
        if not qc_passed:
            # Option 1: Return NaNs (harsh)
            # Option 2: Return data with low confidence flag (realistic)
            qc_metadata['data_quality'] = 'poor'
        else:
            qc_metadata['data_quality'] = 'good'

        return observed_count, distorted_morphology, qc_metadata

    def get_state_summary(self, state: SegmentationFailureState) -> Dict[str, Any]:
        """Summary for logging/debugging."""
        return {
            'segmentation_quality': state.segmentation_quality,
            'qc_passed': state.qc_passed,
            'merge_count': state.merge_count,
            'split_count': state.split_count,
            'size_bias': state.size_bias,
            'warnings': state.qc_warnings
        }

    # Required abstract method implementations (minimal stubs for now)
    def create_state(self, vessel_id: str, context: InjectionContext) -> SegmentationFailureState:
        """Create initial state."""
        return SegmentationFailureState()

    def apply_time_step(self, state: SegmentationFailureState, dt: float, context: InjectionContext) -> None:
        """No time evolution for segmentation state."""
        pass

    def on_event(self, state: SegmentationFailureState, context: InjectionContext) -> None:
        """No event-driven updates."""
        pass

    def get_biology_modifiers(self, state: SegmentationFailureState, context: InjectionContext) -> Dict[str, Any]:
        """Segmentation doesn't modify biology."""
        return {}

    def get_measurement_modifiers(self, state: SegmentationFailureState, context: InjectionContext) -> Dict[str, Any]:
        """Return segmentation quality as modifier."""
        return {'segmentation_quality': state.segmentation_quality}

    def pipeline_transform(self, observation: Dict[str, Any], state: SegmentationFailureState,
                          context: InjectionContext) -> Dict[str, Any]:
        """Transform observations through segmentation distortion."""
        # Would apply count/feature distortions here
        return observation
