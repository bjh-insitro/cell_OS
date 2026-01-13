# Acquisition Profiles

Acquisition profiles define the "personality" of the autonomous loop, controlling how it trades off stress, viability, uncertainty, and diversity when selecting imaging doses and perturbations.

## Available Profiles

### `balanced` (Default)
**Philosophy:** Moderate tradeoffs across all objectives.

**Use when:**
- Starting a new campaign without prior knowledge
- You want reasonable defaults that work in most cases
- Balancing exploration and exploitation

**Parameters:**
- **Viability window:** 0.7 - 0.9 (moderate tolerance)
- **Diversity weight:** 0.5 (equal exploration/exploitation)
- **Max uncertainty:** 0.3 (moderate risk tolerance)
- **Min stress:** 0.3 (some stress required)

**Typical output:** Moderate phenotypic diversity with good cell health.

---

### `ambitious_postdoc`
**Philosophy:** "Push the boundaries to find signal."

**Use when:**
- Exploring new stress conditions or compounds
- Looking for strong phenotypic responses
- EC50 mapping and dose-response characterization
- Early-stage assay development

**Parameters:**
- **Viability window:** 0.5 - 0.85 (wide tolerance, accepts damage)
- **Diversity weight:** 0.7 (favors exploration)
- **Max uncertainty:** 0.5 (high risk tolerance)
- **Min stress:** 0.5 (requires strong stress signal)

**Typical output:** High phenotypic diversity, some wells may have low viability. Maximizes information gain at the cost of cell health.

**Warning:** May produce noisy data in production screens. Best for discovery phases.

---

### `cautious_operator`
**Philosophy:** "Reproducibility and clean data first."

**Use when:**
- Running production screens with known conditions
- Comparing across batches or time points
- Need high reproducibility and low variance
- Working with precious or difficult-to-culture cells

**Parameters:**
- **Viability window:** 0.85 - 1.0 (tight tolerance, minimal damage)
- **Diversity weight:** 0.2 (favors exploitation of known hits)
- **Max uncertainty:** 0.2 (low risk tolerance)
- **Min stress:** None (stress is optional)

**Typical output:** Clean, reproducible data with high cell viability. Lower phenotypic diversity, focuses on known responders.

**Trade-off:** May miss subtle or novel phenotypes. Optimized for quality over discovery.

---

### `wise_pi`
**Philosophy:** "Strategic exploration with controlled risk."

**Use when:**
- Multi-cycle optimization campaigns
- You have some prior knowledge but want to explore further
- Balancing discovery with reproducibility
- Adaptive research workflows

**Parameters:**
- **Viability window:** 0.75 - 0.9 (moderate-tight tolerance)
- **Diversity weight:** 0.6 (slight exploration bias)
- **Max uncertainty:** 0.3 (moderate risk tolerance)
- **Min stress:** 0.4 (moderate stress required)

**Typical output:** Good phenotypic diversity while maintaining cell health. Balanced approach for iterative campaigns.

**Best for:** Experienced users who understand their system and want controlled exploration.

---

## Usage

### Command Line (POSH Demo)
```bash
# Default (balanced)
python scripts/run_posh_campaign_demo.py

# Ambitious exploration
python scripts/run_posh_campaign_demo.py --profile ambitious_postdoc

# Cautious production
python scripts/run_posh_campaign_demo.py --profile cautious_operator

# Strategic optimization
python scripts/run_posh_campaign_demo.py --profile wise_pi
```

### Python API

#### Imaging Dose Selection
```python
from cell_os.imaging.goal import ImagingWindowGoal
from cell_os.acquisition_config import get_profile

# Use profile to set imaging constraints
profile = get_profile("ambitious_postdoc")
goal = ImagingWindowGoal(profile=profile)

# Or manually override specific parameters
goal = ImagingWindowGoal(
    viability_min=0.5,  # Custom
    viability_max=0.85,
    profile=profile,  # Use profile for other defaults
)
```

#### Perturbation Selection
```python
from cell_os.perturbation_goal import PerturbationGoal

# Use profile for diversity weighting
goal = PerturbationGoal(
    max_perturbations=200,
    profile_name="wise_pi",  # 0.6 diversity weight
)

# Access profile properties
print(f"Diversity weight: {goal.profile.diversity_weight}")
```

---

## Profile Comparison

| Profile | Viability Range | Diversity Weight | Risk Tolerance | Best For |
|---------|----------------|------------------|----------------|----------|
| **balanced** | 0.7 - 0.9 | 0.5 | Moderate | General use, starting point |
| **ambitious_postdoc** | 0.5 - 0.85 | 0.7 | High | Discovery, EC50 mapping |
| **cautious_operator** | 0.85 - 1.0 | 0.2 | Low | Production, reproducibility |
| **wise_pi** | 0.75 - 0.9 | 0.6 | Moderate | Iterative optimization |

---

## Interpreting Results

### High Diversity Weight (0.6-0.7)
- More genes selected for novelty vs. known phenotypes
- Broader exploration of morphological space
- May include genes with weaker but distinct phenotypes

### Low Diversity Weight (0.2-0.3)
- Focuses on genes with strong phenotypic scores
- Exploits known hits and pathways
- More reproducible but less exploratory

### Wide Viability Window (0.5-0.85)
- Accepts more cellular damage
- Captures stress responses at higher doses
- May see apoptotic/necrotic phenotypes

### Tight Viability Window (0.85-1.0)
- Minimal cellular damage
- Cleaner morphological features
- May miss stress-induced phenotypes

---

## Extending Profiles

To add a custom profile, edit `src/cell_os/acquisition_config.py`:

```python
PROFILES["my_custom_profile"] = AcquisitionProfile(
    name="my_custom_profile",
    viability_min=0.6,
    viability_max=0.95,
    max_viability_std=0.3,
    min_stress=0.4,
    diversity_weight=0.55,
    max_allowed_uncertainty=0.35,
)
```

Then use it:
```bash
python scripts/run_posh_campaign_demo.py --profile my_custom_profile
```

---

## Future Enhancements

Planned features for acquisition profiles:

- **Adaptive profiles:** Automatically adjust risk tolerance based on cycle number
- **Cost-aware profiles:** Factor in budget constraints
- **Pathway-targeted profiles:** Bias toward specific biological pathways
- **Multi-objective optimization:** Pareto-optimal tradeoffs between objectives
