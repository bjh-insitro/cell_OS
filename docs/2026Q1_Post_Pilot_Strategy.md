# Post n=1 Pilot: Strategic Decision Framework

## Stressor-Next vs Cell-Line-Next

If you only get one more move after an n=1 pilot, pick **another stressor in the same cell line (A549)** before picking another cell line.

Not because cell lines aren't the point. Because you're still proving the rails. And the fastest way to test whether you've built a real coordinate system is to change the input while keeping everything else fixed.

---

## Why Stressor-Next Beats Cell-Line-Next (right after n=1)

**A new stressor answers the hard strategic question:**

> Are we measuring biology on shared rails, or are we measuring "menadione plus microscope"?

If you switch cell line next, you confound everything at once:

- new baseline morphology
- new growth kinetics and density behavior
- new staining behavior and segmentation failure modes
- new stress tolerance
- often new transduction dynamics

If you switch stressor next, you keep:

- same chassis
- same handling
- same imaging pipeline
- same segmentation/feature space
- same library and decoding logic

So you get a cleaner read on whether the tensor idea is real: **do different stressors light up separable, stable manifolds in the same coordinate system?**

---

## The Most Informative "One More" for Tensor Building

**Do a second stressor in A549**, with the same two endpoints (POSH + Perturb-seq), ideally one that is mechanistically distinct and operationally reliable.

If you started with oxidative (menadione), the best complements are:

| Stressor | Mechanism | Notes |
|----------|-----------|-------|
| **Tunicamycin** | ER stress | Slow, robust |
| **Thapsigargin** | ER stress | Fast, can be harsher |
| **Bafilomycin A1** | Lysosomal/autophagy flux | Strong morphology signal, but dosing window matters |
| **Antimycin A** | Mitochondrial ETC | Can collapse viability quickly depending on dose |
| **Rotenone** | Mitochondrial ETC | Can collapse viability quickly depending on dose |

Pick the one that is most "boringly reliable" in your hands. Early tensor work rewards boring.

---

## What Switching Stressor Gives You, Concretely

- Validates that your feature space can represent **multiple axes** without retraining
- Lets you test whether stressors produce **distinct, interpretable separations** (not just "damage")
- Gives you the first evidence that the tensor will have **shape** rather than being a single stress-response axis
- Helps you decide whether Perturb-seq is adding incremental value or just cost

---

## When to Choose a New Cell Line Instead

If the n=1 pilot fails due to any of these:

- A549-specific quirks dominate (density, morphology instability)
- guide assignment / transduction / survival is weird in A549 under stress
- segmentation is too brittle even with good QC
- the whole menadione operating point is too close to collapse for pooled work

Then switching cell line (to **U2OS**) can be a deliberate "stability rescue" move. U2OS is the imaging workhorse: big nuclei, flat cells, forgiving segmentation. It's the line you use to decide if your pipeline is broken or your biology is hard.

---

## The Crisp Strategic Answer

| Objective | Next Step |
|-----------|-----------|
| **Most informative for tensor building** | Second stressor in A549 |
| **Most informative for debugging execution** | U2OS with the same stressor |

---

## Cost Consideration

If POSH throughput is painful (cost and calendar), the single best stressor choice for "maximum new information per dollar" depends on what you already ran. Optimize for boringly reliable over mechanistically interesting at this stage.
