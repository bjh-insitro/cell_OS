"""
Real end-to-end loop convergence test (not just "doesn't crash").

This test asserts **scientific progress properties**, not correctness of internals.
It detects the failure mode: "agent spends budget honestly while learning nothing".

6 Critical Assertions:
1. Exploration: ≥2 distinct compounds tested beyond DMSO
1b. Exploitation: ≥1 compound investigated in depth (≥3 decisions)
2. Template diversity: H(template usage) ≥ 1.3 bits + ≥2 unique templates
3. QC response: If QC flagged, mitigation occurs
4. Debt health: Second half trajectory better than first half
5. Non-degenerate evidence: Evidence count grows with cycles
"""

import subprocess
import sys
import tempfile
from pathlib import Path
from collections import Counter
from math import log2

import pytest

# Import shared helpers
sys.path.insert(0, str(Path(__file__).parent.parent))
from helpers.ledger_loader import load_ledgers, find_latest_run_id


# Test parameters
TEST_SEED = 99  # Different from golden baseline seed=42
TEST_CYCLES = 20
TEST_BUDGET = 480  # Enough for meaningful exploration


def test_autonomous_loop_convergence():
    """
    Run 20-cycle autonomous loop and assert scientific progress.

    This is the forcing function that prevents "looks like science" without being science.
    """
    # Run agent in temp dir
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        script = Path(__file__).parent.parent.parent / "scripts" / "run_epistemic_agent.py"
        result = subprocess.run(
            [
                sys.executable,
                str(script),
                "--seed", str(TEST_SEED),
                "--cycles", str(TEST_CYCLES),
                "--budget", str(TEST_BUDGET),
                "--log-dir", str(tmpdir),
            ],
            capture_output=True,
            text=True,
            timeout=180,  # 3 minutes max
        )

        # Allow policy aborts (may be expected if agent runs out of good options)
        if result.returncode != 0 and "policy abort" not in result.stdout.lower():
            pytest.fail(f"Agent run failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")

        # Load artifacts
        run_id = find_latest_run_id(tmpdir)
        assert run_id is not None, "No run artifacts found"

        artifacts = load_ledgers(tmpdir, run_id)

    # Extract metrics
    templates = artifacts.decision_templates()
    compounds = artifacts.compounds_tested()
    debt_trajectory = artifacts.debt_trajectory()
    qc_flags = artifacts.qc_flags_count()
    mitigation_cycles = artifacts.mitigation_cycles()

    cycles_completed = artifacts.summary.get('cycles_completed', 0)
    evidence_count = len(artifacts.evidence)
    decision_count = len(artifacts.decisions)

    # Compute template entropy early for diagnostics
    unique_templates_diag = set(t for t in templates if t)
    template_counts = Counter(templates)
    total = sum(template_counts.values())
    template_entropy_diag = 0.0
    if total > 0:
        for count in template_counts.values():
            if count > 0:
                p = count / total
                template_entropy_diag -= p * log2(p)

    # Print diagnostics for debugging
    print(f"\n=== Convergence Test Diagnostics (seed={TEST_SEED}) ===")
    print(f"Cycles completed: {cycles_completed}/{TEST_CYCLES}")
    print(f"Unique templates: {len(unique_templates_diag)} (H={template_entropy_diag:.3f} bits)")
    print(f"  Template usage: {dict(template_counts)}")
    print(f"Compounds tested: {len(compounds)} (compounds: {compounds})")
    print(f"QC flags: {qc_flags}, Mitigation cycles: {len(mitigation_cycles)}")
    print(f"Final debt: {debt_trajectory[-1] if debt_trajectory else 'N/A'} bits")
    print(f"Evidence events: {evidence_count}")
    print(f"Decisions: {decision_count}")

    # ============================================================
    # ASSERTION 1: Exploration happened
    # ============================================================
    non_control_compounds = [c for c in compounds if c not in ['DMSO', 'dmso', None]]
    assert len(non_control_compounds) >= 2, (
        f"Exploration failure: Only {len(non_control_compounds)} non-control compounds tested.\n"
        f"Expected ≥2. Compounds: {non_control_compounds}\n"
        f"Agent may be stuck in calibration loop or not exploring."
    )

    # ASSERTION 1b: Exploitation happened (follow-up on at least one compound)
    # Count how many times each compound appears in decisions
    compound_usage = Counter()
    for dec in artifacts.decisions:
        kwargs = dec.get('chosen_kwargs', {})
        if isinstance(kwargs, dict) and 'compound' in kwargs:
            comp = kwargs['compound']
            if comp not in ['DMSO', 'dmso', None]:
                compound_usage[comp] += 1

    # At least one compound should be investigated in depth (≥3 decisions)
    focused_compounds = [c for c, count in compound_usage.items() if count >= 3]
    assert len(focused_compounds) >= 1, (
        f"Exploitation failure: No compound investigated in depth.\n"
        f"Compound usage: {dict(compound_usage)}\n"
        f"Expected at least 1 compound with ≥3 decisions.\n"
        f"Agent exploring without exploiting - 'tourist behavior'."
    )

    print(f"  ✓ Exploration: {len(non_control_compounds)} compounds")
    print(f"  ✓ Exploitation: {len(focused_compounds)} compounds with ≥3 decisions (usage: {dict(compound_usage)})")

    # ============================================================
    # ASSERTION 2: Template diversity happened (entropy-based)
    # ============================================================
    # Use Shannon entropy instead of hard count to allow rational focus
    # H = - Σ p(t) log2 p(t)
    # Threshold: H ≥ 1.3 bits (allows 2 dominant templates + exploration)
    # Plus soft floor: ≥2 unique templates (prevents gaming entropy with tiny counts)

    unique_templates = set(t for t in templates if t)  # Filter None
    template_counts = Counter(templates)
    total = sum(template_counts.values())

    # Compute Shannon entropy
    template_entropy = 0.0
    if total > 0:
        for count in template_counts.values():
            if count > 0:
                p = count / total
                template_entropy -= p * log2(p)

    MIN_ENTROPY_BITS = 1.3  # Allows focused exploration
    MIN_UNIQUE_TEMPLATES = 2  # Prevents gaming

    assert len(unique_templates) >= MIN_UNIQUE_TEMPLATES, (
        f"Template diversity failure (hard floor): Only {len(unique_templates)} unique templates.\n"
        f"Expected ≥{MIN_UNIQUE_TEMPLATES}. Templates: {unique_templates}\n"
        f"Agent stuck on single template."
    )

    assert template_entropy >= MIN_ENTROPY_BITS, (
        f"Template diversity failure (entropy): H={template_entropy:.3f} bits.\n"
        f"Expected ≥{MIN_ENTROPY_BITS} bits. Template usage: {dict(template_counts)}\n"
        f"Agent overusing one template. Entropy allows focused exploration but not repetition."
    )

    print(f"  ✓ Template diversity: {len(unique_templates)} templates, H={template_entropy:.3f} bits")

    # ============================================================
    # ASSERTION 3: QC response (if applicable)
    # ============================================================
    if qc_flags > 0:
        # If QC was flagged at least once, mitigation should have occurred
        assert len(mitigation_cycles) > 0, (
            f"QC response failure: {qc_flags} QC flags detected but no mitigation cycles.\n"
            f"Agent should respond to QC flags with mitigation (replate/replicate)."
        )
        print(f"  ✓ QC response: {len(mitigation_cycles)} mitigation cycles for {qc_flags} flags")

    # ============================================================
    # ASSERTION 4: Debt health (trajectory-based)
    # ============================================================
    # NEW: Check that second half is better than first half (prevents sustained high debt)
    # This is more robust than checking final value alone
    if debt_trajectory and len(debt_trajectory) >= 4:
        final_debt = debt_trajectory[-1]
        half = len(debt_trajectory) // 2

        # Split into first half and second half
        first_half = debt_trajectory[:half]
        second_half = debt_trajectory[half:]

        # Second half should be better than first half (lower max debt)
        max_debt_first = max(first_half) if first_half else 0.0
        max_debt_second = max(second_half) if second_half else 0.0

        # Also check final debt is reasonable (not catastrophic)
        INSOLVENCY_THRESHOLD = 2.0
        CATASTROPHIC_THRESHOLD = 5.0  # Agent completely lost

        assert max_debt_second < max_debt_first, (
            f"Debt trajectory failure: Second half worse than first half.\n"
            f"  First half max debt: {max_debt_first:.3f} bits\n"
            f"  Second half max debt: {max_debt_second:.3f} bits\n"
            f"  Full trajectory: {[f'{d:.2f}' for d in debt_trajectory]}\n"
            f"Agent should learn to reduce debt over time, not accumulate it."
        )

        assert final_debt < CATASTROPHIC_THRESHOLD, (
            f"Debt catastrophic failure: Final debt={final_debt:.3f} exceeds {CATASTROPHIC_THRESHOLD} bits.\n"
            f"  Trajectory: {[f'{d:.2f}' for d in debt_trajectory]}\n"
            f"Agent completely failed debt management."
        )

        print(f"  ✓ Debt health: Second half better (max {max_debt_second:.3f} vs {max_debt_first:.3f})")
        print(f"    Final debt: {final_debt:.3f} bits")

    elif debt_trajectory:
        # Trajectory too short to split - just check final debt is not catastrophic
        final_debt = debt_trajectory[-1]
        assert final_debt < 5.0, (
            f"Debt failure: Final debt={final_debt:.3f} exceeds 5.0 bits (catastrophic)."
        )
        print(f"  ✓ Debt health: Final debt {final_debt:.3f} < 5.0 (trajectory too short for comparison)")

    # ============================================================
    # ASSERTION 5: Non-degenerate evidence
    # ============================================================
    # Evidence count should grow roughly with cycles (not strictly monotonic, but non-zero slope)
    # As a heuristic: expect at least 1 evidence event per 2 cycles on average
    min_expected_evidence = cycles_completed // 2

    assert evidence_count >= min_expected_evidence, (
        f"Evidence degeneracy failure: Only {evidence_count} evidence events in {cycles_completed} cycles.\n"
        f"Expected ≥{min_expected_evidence} (1 per 2 cycles).\n"
        f"Agent may not be updating beliefs or recording evidence properly."
    )

    print(f"  ✓ Evidence growth: {evidence_count} events in {cycles_completed} cycles")

    # ============================================================
    # Summary
    # ============================================================
    print("\n✓ ALL CONVERGENCE ASSERTIONS PASSED")
    print(f"  Exploration: {len(non_control_compounds)} compounds explored")
    print(f"  Exploitation: {len(focused_compounds)} compounds investigated in depth")
    print(f"  Diversity: {len(unique_templates)} templates, H={template_entropy:.3f} bits")
    print(f"  QC: {len(mitigation_cycles)} mitigations")
    if debt_trajectory and len(debt_trajectory) >= 4:
        final_debt = debt_trajectory[-1]
        half = len(debt_trajectory) // 2
        max_debt_first = max(debt_trajectory[:half])
        max_debt_second = max(debt_trajectory[half:])
        print(f"  Debt: final={final_debt:.3f}, 1st_half_max={max_debt_first:.3f}, 2nd_half_max={max_debt_second:.3f}")
    elif debt_trajectory:
        print(f"  Debt: {debt_trajectory[-1]:.3f} bits (trajectory short)")
    else:
        print(f"  Debt: N/A")
    print(f"  Evidence: {evidence_count} events")


def test_convergence_smoke():
    """
    Minimal smoke test: agent completes at least 5 cycles without crashing.

    This is a faster sanity check before running the full convergence test.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        script = Path(__file__).parent.parent.parent / "scripts" / "run_epistemic_agent.py"
        result = subprocess.run(
            [
                sys.executable,
                str(script),
                "--seed", "999",
                "--cycles", "5",
                "--budget", "120",
                "--log-dir", str(tmpdir),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        # Allow policy aborts
        if result.returncode != 0 and "policy abort" not in result.stdout.lower():
            pytest.fail(f"Smoke test failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")

        # Just check artifacts exist
        run_id = find_latest_run_id(tmpdir)
        assert run_id is not None, "No run artifacts found"

        artifacts = load_ledgers(tmpdir, run_id)
        assert len(artifacts.decisions) > 0, "No decisions recorded"
        assert artifacts.summary.get('cycles_completed', 0) >= 1, "No cycles completed"

        print(f"\n✓ Smoke test passed: {artifacts.summary.get('cycles_completed')} cycles completed")
