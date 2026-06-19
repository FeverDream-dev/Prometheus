from __future__ import annotations

from prometheus_cli.escalation import FailureTracker, failure_signature


class TestFailureSignature:
    def test_same_error_produces_same_signature(self):
        sig1 = failure_signature("write_file", "ERROR PermissionError: Path escapes workspace: ../secret")
        sig2 = failure_signature("write_file", "ERROR PermissionError: Path escapes workspace: ../secret")
        assert sig1 == sig2

    def test_different_line_numbers_group_together(self):
        sig1 = failure_signature("run_command", "ERROR TimeoutExpired: Command timed out after 30s at line 42")
        sig2 = failure_signature("run_command", "ERROR TimeoutExpired: Command timed out after 30s at line 99")
        assert sig1 == sig2

    def test_different_file_paths_group_together(self):
        sig1 = failure_signature("read_file", "ERROR FileNotFoundError: /repo/src/a.py not found")
        sig2 = failure_signature("read_file", "ERROR FileNotFoundError: /repo/src/b.py not found")
        assert sig1 == sig2

    def test_different_error_types_do_not_group(self):
        sig1 = failure_signature("run_command", "ERROR TimeoutExpired: timed out")
        sig2 = failure_signature("run_command", "ERROR CalledProcessError: exit 1")
        assert sig1 != sig2

    def test_different_tools_do_not_group(self):
        sig1 = failure_signature("write_file", "ERROR PermissionError: denied")
        sig2 = failure_signature("run_command", "ERROR PermissionError: denied")
        assert sig1 != sig2


class TestFailureTracker:
    def test_returns_none_below_threshold(self):
        tracker = FailureTracker(threshold=5)
        for _ in range(4):
            assert tracker.record("write_file", "ERROR PermissionError: denied") is None

    def test_returns_signature_at_threshold(self):
        tracker = FailureTracker(threshold=5)
        result = None
        for _ in range(5):
            result = tracker.record("write_file", "ERROR PermissionError: denied")
        assert result is not None
        assert "write_file" in result

    def test_different_failures_do_not_trigger(self):
        tracker = FailureTracker(threshold=5)
        for _ in range(3):
            assert tracker.record("write_file", "ERROR PermissionError: denied") is None
        for _ in range(3):
            assert tracker.record("run_command", "ERROR TimeoutExpired: timed out") is None
        assert tracker.distinct_signatures() == 2
        assert tracker.total() == 6

    def test_reset_clears_specific_signature(self):
        tracker = FailureTracker(threshold=3)
        for _ in range(3):
            sig = tracker.record("run_command", "ERROR ValueError: bad input")
        assert sig is not None
        tracker.reset(sig)
        assert tracker.count_for("run_command", "ERROR ValueError: bad input") == 0

    def test_threshold_met_after_five_identical_signatures(self):
        tracker = FailureTracker(threshold=5)
        error = "ERROR FileNotFoundError: /repo/src/main.py not found"
        sigs = [tracker.record("read_file", error) for _ in range(5)]
        assert sigs[-1] is not None
        assert all(s is None for s in sigs[:4])
