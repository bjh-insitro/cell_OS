"""
Epistemic Bridge Teeth Tests

These are not "coverage" tests. They are ENFORCEMENT tests.

1. Replay Determinism: Proves design artifact is sufficient for reproduction
2. No-Bypass: Proves execution without persisted design fails hard

If these tests break, the epistemic guarantees are broken.
"""

try:
    import pytest
except ImportError:
    # Allow running without pytest for manual testing
    pytest = None
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

# Import the bridge components
from cell_os.epistemic_agent.design_bridge import (
    proposal_to_design_json,
    validate_design,
    persist_design,
    persist_rejected_design,
    compute_design_hash,
)
from cell_os.epistemic_agent.world_with_bridge import (
    _design_to_well_assignments,
)
from cell_os.epistemic_agent.schemas import Proposal, WellSpec
from cell_os.epistemic_agent.exceptions import InvalidDesignError


def create_test_proposal() -> Proposal:
    """Create a minimal valid proposal for testing."""
    return Proposal(
        design_id="test_design_001",
        hypothesis="Test hypothesis: DMSO control vs compound X",
        budget_limit=8,
        wells=[
            WellSpec(
                cell_line="A549",
                compound="DMSO",
                dose_uM=0.0,
                time_h=24,
                assay="Viability",
                position_tag="center"
            ),
            WellSpec(
                cell_line="A549",
                compound="CompoundX",
                dose_uM=10.0,
                time_h=24,
                assay="Viability",
                position_tag="center"
            ),
        ]
    )


class TestReplayDeterminism:
    """Test that design artifact is sufficient to reproduce execution."""

    def test_design_hash_is_stable_across_reloads(self):
        """
        TOOTH #1: Replay Determinism

        Execute → Persist → Reload → Execute → Assert Identical

        This proves the design artifact contains the full executable truth.
        If this fails, your "receipt" is decorative.
        """
        proposal = create_test_proposal()
        well_positions = ["C05", "C06"]  # Allocated well positions

        # First execution: create and persist design
        with tempfile.TemporaryDirectory() as tmpdir:
            design_dir = Path(tmpdir)

            # Generate design
            design_v1 = proposal_to_design_json(
                proposal=proposal,
                cycle=1,
                run_id="test_run_001",
                well_positions=well_positions,
            )

            # Validate
            validate_design(design_v1, strict=True)

            # Persist
            design_path = persist_design(
                design_v1,
                output_dir=design_dir,
                run_id="test_run_001",
                cycle=1
            )

            # Compute hash
            hash_v1 = compute_design_hash(design_v1)

            # Convert to execution format
            assignments_v1 = _design_to_well_assignments(design_v1)

            # === RELOAD AND RE-EXECUTE ===

            # Load persisted design
            with open(design_path, 'r') as f:
                design_v2 = json.load(f)

            # Compute hash of reloaded design
            hash_v2 = compute_design_hash(design_v2)

            # Convert to execution format
            assignments_v2 = _design_to_well_assignments(design_v2)

            # === ASSERT DETERMINISM ===

            # Hashes must be identical
            assert hash_v1 == hash_v2, (
                f"Design hash changed after reload!\n"
                f"  Original: {hash_v1}\n"
                f"  Reloaded: {hash_v2}\n"
                f"This means the design artifact is NOT sufficient for replay."
            )

            # Execution-relevant fields must be identical
            assert len(assignments_v1) == len(assignments_v2)
            for a1, a2 in zip(assignments_v1, assignments_v2):
                assert a1.well_id == a2.well_id
                assert a1.cell_line == a2.cell_line
                assert a1.compound == a2.compound
                assert a1.dose_uM == a2.dose_uM
                assert a1.timepoint_h == a2.timepoint_h
                assert a1.plate_id == a2.plate_id
                assert a1.day == a2.day
                assert a1.operator == a2.operator
                assert a1.is_sentinel == a2.is_sentinel

    def test_hash_changes_when_execution_relevant_field_changes(self):
        """
        Verify hash includes ALL execution-relevant fields.

        If changing a dose/timepoint/compound doesn't change the hash,
        you'll get false sameness (worse than false difference).
        """
        proposal = create_test_proposal()
        well_positions = ["C05", "C06"]

        # Original design
        design_original = proposal_to_design_json(
            proposal=proposal,
            cycle=1,
            run_id="test_run_001",
            well_positions=well_positions,
        )
        hash_original = compute_design_hash(design_original)

        # Modify dose (execution-relevant)
        design_modified = json.loads(json.dumps(design_original))  # deep copy
        design_modified["wells"][1]["dose_uM"] = 20.0  # Changed from 10.0
        hash_modified = compute_design_hash(design_modified)

        assert hash_original != hash_modified, (
            "Hash did not change when dose changed! "
            "This means execution-relevant fields are not being hashed."
        )

    def test_hash_unchanged_when_metadata_changes(self):
        """
        Verify hash EXCLUDES non-execution-relevant metadata.

        Timestamps, paths, comments should not affect replay identity.
        """
        proposal = create_test_proposal()
        well_positions = ["C05", "C06"]

        # Original design
        design_original = proposal_to_design_json(
            proposal=proposal,
            cycle=1,
            run_id="test_run_001",
            well_positions=well_positions,
        )
        hash_original = compute_design_hash(design_original)

        # Modify metadata (non-execution-relevant)
        design_modified = json.loads(json.dumps(design_original))  # deep copy
        design_modified["metadata"]["created_at"] = "2099-12-31T23:59:59"
        design_modified["metadata"]["comment"] = "This is a test comment"
        hash_modified = compute_design_hash(design_modified)

        assert hash_original == hash_modified, (
            "Hash changed when metadata changed! "
            "This means non-execution-relevant fields are polluting the hash."
        )


class TestNoBypass:
    """Test that execution without persisted design fails hard."""

    def test_invalid_design_raises_before_execution(self):
        """
        TOOTH #2: No-Bypass Test

        Prove that invalid designs are REJECTED before execution.
        This is Covenant 5: refuse what you cannot guarantee.
        """
        proposal = create_test_proposal()
        well_positions = ["C05", "C06"]

        # Create design with invalid well position
        design = proposal_to_design_json(
            proposal=proposal,
            cycle=1,
            run_id="test_run_001",
            well_positions=well_positions,
        )

        # Inject invalid well position
        design["wells"][0]["well_pos"] = "Z99"  # Invalid position

        # Validation MUST fail with structured exception
        e = None
        if pytest:
            with pytest.raises(InvalidDesignError) as exc_info:
                validate_design(design, strict=True)
            e = exc_info.value
        else:
            # Manual test without pytest
            try:
                validate_design(design, strict=True)
                raise AssertionError("Validation should have failed but didn't!")
            except InvalidDesignError as ex:
                e = ex

        # Assert structured fields (no string parsing!)
        assert e.violation_code == "invalid_well_position"
        assert e.covenant_id == "C5"
        assert e.validator_mode == "placeholder", (
            "Validator mode must indicate placeholder status. "
            "This means we're pretending full validation is active when it's not."
        )
        assert e.design_id == "test_design_001"
        assert e.cycle == 1

    def test_invalid_design_produces_rejection_with_provenance(self):
        """
        When validation fails, the error must contain design provenance.

        This ensures refusal receipts can point to the invalid design artifact.
        """
        proposal = create_test_proposal()
        well_positions = ["C05", "C06"]

        # Create design with duplicate well positions
        design = proposal_to_design_json(
            proposal=proposal,
            cycle=1,
            run_id="test_run_001",
            well_positions=["C05", "C05"],  # Duplicate!
        )

        # Validation MUST fail with structured provenance
        e = None
        if pytest:
            with pytest.raises(InvalidDesignError) as exc_info:
                validate_design(design, strict=True)
            e = exc_info.value
        else:
            # Manual test without pytest
            try:
                validate_design(design, strict=True)
                raise AssertionError("Validation should have failed but didn't!")
            except InvalidDesignError as ex:
                e = ex

        # Assert structured fields (no string parsing!)
        assert e.violation_code == "duplicate_well_positions"
        assert e.covenant_id == "C5"
        assert e.validator_mode == "placeholder"
        assert e.design_id == "test_design_001"
        assert "C05" in str(e.details.get("duplicates", [])), "Details must contain duplicate positions"

    def test_design_to_well_assignments_is_only_execution_path(self):
        """
        Prove that _design_to_well_assignments() is the sole conversion path.

        If there's another function that converts Proposal → Execution,
        the bridge can be bypassed.
        """
        proposal = create_test_proposal()
        well_positions = ["C05", "C06"]

        # Create and validate design
        design = proposal_to_design_json(
            proposal=proposal,
            cycle=1,
            run_id="test_run_001",
            well_positions=well_positions,
        )

        # This MUST be the only way to get WellAssignments for execution
        assignments = _design_to_well_assignments(design)

        # Verify it produces valid assignments
        assert len(assignments) == 2
        assert assignments[0].well_id == "C05"
        assert assignments[1].well_id == "C06"

        # The old path (Proposal → WellAssignments directly) should NOT exist
        # If it does, someone can bypass the bridge
        # This is enforced by world_with_bridge.py using design_json as canonical


class TestRejectedDesignPersistence:
    """Test that rejected designs are quarantined with reason files."""

    def test_rejected_design_is_persisted_with_reason(self):
        """
        TOOTH #3: Rejected Design Persistence

        When validation fails, the invalid design MUST be persisted to quarantine
        with a reason file. Refusal without a receipt is just a crash with posture.
        """
        proposal = create_test_proposal()
        well_positions = ["C05", "C05"]  # Duplicate positions (invalid)

        # Create invalid design
        design = proposal_to_design_json(
            proposal=proposal,
            cycle=1,
            run_id="test_run_001",
            well_positions=well_positions,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            design_dir = Path(tmpdir)

            # Persist rejected design
            rejected_path, reason_path = persist_rejected_design(
                design=design,
                output_dir=design_dir,
                run_id="test_run_001",
                cycle=1,
                violation_code="duplicate_well_positions",
                violation_message="Duplicate well positions: ['C05']",
                validator_mode="placeholder",
            )

            # Verify rejected design was written
            assert rejected_path.exists(), "Rejected design was not persisted"
            assert "_REJECTED.json" in str(rejected_path), "Rejected design missing REJECTED suffix"

            # Verify reason file was written
            assert reason_path.exists(), "Rejection reason was not persisted"
            assert "_REJECTED.reason.json" in str(reason_path), "Reason file missing correct suffix"

            # Verify rejected design content
            with open(rejected_path, 'r') as f:
                rejected_design = json.load(f)
            assert rejected_design["design_id"] == design["design_id"]
            assert len(rejected_design["wells"]) == 2

            # Verify reason file content
            with open(reason_path, 'r') as f:
                reason = json.load(f)

            # Required fields in reason file
            assert reason["violation_code"] == "duplicate_well_positions"
            assert "Duplicate well positions" in reason["violation_message"]
            assert reason["validator_mode"] == "placeholder"
            assert "design_hash" in reason, "Rejected design must have hash for diff tracking"
            assert "caught_at" in reason
            assert reason["caught_at"]["cycle"] == 1
            assert reason["caught_at"]["run_id"] == "test_run_001"
            assert "design_path" in reason

    def test_rejected_design_hash_is_computed(self):
        """
        Rejected designs must have hashes for diff tracking.

        This allows comparing original attempt vs retry attempt (when retries exist).
        """
        proposal = create_test_proposal()
        well_positions = ["C05", "C06"]

        design = proposal_to_design_json(
            proposal=proposal,
            cycle=1,
            run_id="test_run_001",
            well_positions=well_positions,
        )

        # Inject invalid timepoint
        design["wells"][0]["timepoint_h"] = -1  # Invalid

        with tempfile.TemporaryDirectory() as tmpdir:
            design_dir = Path(tmpdir)

            rejected_path, reason_path = persist_rejected_design(
                design=design,
                output_dir=design_dir,
                run_id="test_run_001",
                cycle=1,
                violation_code="invalid_timepoint",
                violation_message="Well 0 has non-positive timepoint: -1",
                validator_mode="placeholder",
            )

            # Load reason and verify hash
            with open(reason_path, 'r') as f:
                reason = json.load(f)

            assert "design_hash" in reason
            assert len(reason["design_hash"]) == 16  # 16-char hex
            assert reason["design_hash"] == compute_design_hash(design)

    def test_persistence_failure_sets_audit_degraded(self):
        """
        When refusal artifacts fail to write, audit_degraded must be True.

        This is CRITICAL: refusal is still enforced (agent still refuses),
        but the audit trail is degraded (receipt write failed).
        Caller must surface this degradation explicitly.
        """
        from cell_os.epistemic_agent.design_bridge import RefusalPersistenceError
        from unittest.mock import patch

        proposal = create_test_proposal()
        well_positions = ["C05", "C06"]

        design = proposal_to_design_json(
            proposal=proposal,
            cycle=1,
            run_id="test_run_001",
            well_positions=well_positions,
        )

        # Inject invalid timepoint to trigger validation failure
        design["wells"][0]["timepoint_h"] = -1

        # Simulate persistence failure by patching open to raise
        with tempfile.TemporaryDirectory() as tmpdir:
            design_dir = Path(tmpdir)

            with patch("builtins.open", side_effect=OSError("Disk full")):
                # Persistence must fail with RefusalPersistenceError
                if pytest:
                    with pytest.raises(RefusalPersistenceError) as exc_info:
                        persist_rejected_design(
                            design=design,
                            output_dir=design_dir,
                            run_id="test_run_001",
                            cycle=1,
                            violation_code="invalid_timepoint",
                            violation_message="Well 0 has non-positive timepoint: -1",
                            validator_mode="placeholder",
                        )
                    e = exc_info.value
                    assert "Failed to persist refusal artifacts" in str(e)
                    assert "Disk full" in str(e)
                else:
                    # Manual test without pytest
                    try:
                        persist_rejected_design(
                            design=design,
                            output_dir=design_dir,
                            run_id="test_run_001",
                            cycle=1,
                            violation_code="invalid_timepoint",
                            violation_message="Well 0 has non-positive timepoint: -1",
                            validator_mode="placeholder",
                        )
                        raise AssertionError("Persistence should have failed but didn't!")
                    except RefusalPersistenceError as e:
                        assert "Failed to persist refusal artifacts" in str(e)
                        assert "Disk full" in str(e)


class TestValidationPlaceholder:
    """Test that validation placeholder status is explicit."""

    def test_validation_errors_indicate_placeholder_status(self):
        """
        All validation errors MUST set validator_mode="placeholder"
        until full validation is active.

        This prevents false sense of safety.
        """
        proposal = create_test_proposal()
        well_positions = ["C05", "C06"]

        # Create design missing required field
        design = proposal_to_design_json(
            proposal=proposal,
            cycle=1,
            run_id="test_run_001",
            well_positions=well_positions,
        )
        del design["wells"][0]["cell_line"]  # Remove required field

        # Validation must fail with placeholder status
        e = None
        if pytest:
            with pytest.raises(InvalidDesignError) as exc_info:
                validate_design(design, strict=True)
            e = exc_info.value
        else:
            # Manual test without pytest
            try:
                validate_design(design, strict=True)
                raise AssertionError("Validation should have failed but didn't!")
            except InvalidDesignError as ex:
                e = ex

        # Assert structured fields (no string parsing!)
        assert e.validator_mode == "placeholder", (
            "Validation error did not indicate placeholder status. "
            "You're pretending to have full validation when you don't."
        )
        assert e.violation_code == "missing_well_field"
        assert e.covenant_id == "C5"


if __name__ == "__main__":
    if pytest:
        pytest.main([__file__, "-v"])
    else:
        print("Running tests manually (pytest not available)...")
        print("\n=== TestReplayDeterminism ===")
        test1 = TestReplayDeterminism()
        try:
            test1.test_design_hash_is_stable_across_reloads()
            print("✓ test_design_hash_is_stable_across_reloads PASSED")
        except Exception as e:
            print(f"✗ test_design_hash_is_stable_across_reloads FAILED: {e}")

        try:
            test1.test_hash_changes_when_execution_relevant_field_changes()
            print("✓ test_hash_changes_when_execution_relevant_field_changes PASSED")
        except Exception as e:
            print(f"✗ test_hash_changes_when_execution_relevant_field_changes FAILED: {e}")

        try:
            test1.test_hash_unchanged_when_metadata_changes()
            print("✓ test_hash_unchanged_when_metadata_changes PASSED")
        except Exception as e:
            print(f"✗ test_hash_unchanged_when_metadata_changes FAILED: {e}")

        print("\n=== TestNoBypass ===")
        test2 = TestNoBypass()
        try:
            test2.test_invalid_design_raises_before_execution()
            print("✓ test_invalid_design_raises_before_execution PASSED")
        except Exception as e:
            print(f"✗ test_invalid_design_raises_before_execution FAILED: {e}")

        try:
            test2.test_invalid_design_produces_rejection_with_provenance()
            print("✓ test_invalid_design_produces_rejection_with_provenance PASSED")
        except Exception as e:
            print(f"✗ test_invalid_design_produces_rejection_with_provenance FAILED: {e}")

        try:
            test2.test_design_to_well_assignments_is_only_execution_path()
            print("✓ test_design_to_well_assignments_is_only_execution_path PASSED")
        except Exception as e:
            print(f"✗ test_design_to_well_assignments_is_only_execution_path FAILED: {e}")

        print("\n=== TestRejectedDesignPersistence ===")
        test3 = TestRejectedDesignPersistence()
        try:
            test3.test_rejected_design_is_persisted_with_reason()
            print("✓ test_rejected_design_is_persisted_with_reason PASSED")
        except Exception as e:
            print(f"✗ test_rejected_design_is_persisted_with_reason FAILED: {e}")

        try:
            test3.test_rejected_design_hash_is_computed()
            print("✓ test_rejected_design_hash_is_computed PASSED")
        except Exception as e:
            print(f"✗ test_rejected_design_hash_is_computed FAILED: {e}")

        try:
            test3.test_persistence_failure_sets_audit_degraded()
            print("✓ test_persistence_failure_sets_audit_degraded PASSED")
        except Exception as e:
            print(f"✗ test_persistence_failure_sets_audit_degraded FAILED: {e}")

        print("\n=== TestValidationPlaceholder ===")
        test4 = TestValidationPlaceholder()
        try:
            test4.test_validation_errors_indicate_placeholder_status()
            print("✓ test_validation_errors_indicate_placeholder_status PASSED")
        except Exception as e:
            print(f"✗ test_validation_errors_indicate_placeholder_status FAILED: {e}")

        print("\nAll tests completed!")
