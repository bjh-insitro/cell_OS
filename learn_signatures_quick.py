"""
Quick signature learning test with 20 samples per mechanism.

This validates the approach works before running the full 200-sample dataset.
"""

import sys
sys.path.insert(0, '/Users/bjh/cell_OS')

from learn_mechanism_signatures import (
    learn_all_signatures,
    test_cosplay_detector_with_learned_signatures,
    save_learned_signatures
)
from pathlib import Path

if __name__ == "__main__":
    # Quick test with 20 samples per mechanism
    print("QUICK TEST: Learning signatures with 20 samples per mechanism")
    print("="*80)

    learned_signatures = learn_all_signatures(n_samples_per_mechanism=20)

    # Test cosplay detector
    passed = test_cosplay_detector_with_learned_signatures(learned_signatures)

    # Save for testing
    save_path = "/Users/bjh/cell_OS/data/learned_mechanism_signatures_quick.pkl"
    Path(save_path).parent.mkdir(parents=True, exist_ok=True)
    save_learned_signatures(learned_signatures, save_path)

    print("\n" + "="*80)
    print("QUICK TEST VERDICT:")
    print("="*80)
    if passed:
        print("✓ Learned signatures PASS cosplay detector (quick test)")
        print("  This suggests 3D feature space [actin, mito, ER] is sufficient")
        print("  Proceed with full 200-sample dataset for production signatures")
    else:
        print("✗ Learned signatures FAIL cosplay detector (quick test)")
        print("  This suggests 3D feature space [actin, mito, ER] may be insufficient")
        print("  Consider: add morphology PCA dimensions or more channels")
