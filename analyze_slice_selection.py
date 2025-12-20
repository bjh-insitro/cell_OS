"""
Analyze why only microtubule appeared in the weak-posterior slice.

Check posterior distributions per mechanism BEFORE filtering.
"""

import pickle
import numpy as np
from collections import defaultdict

# Load the saved results
with open('/tmp/mechanism_conditional_results.pkl', 'rb') as f:
    data = pickle.load(f)

# This won't exist yet - need to save all_records in the test script
# For now, let me just note what to check

print("Need to save all_records (before filtering) to diagnose slice selection")
print("\nChecking per compound:")
print("1. Distribution of posterior_top_prob")
print("2. Distribution of nuisance_frac")
print("3. Fraction with predicted_axis != 'unknown'")
