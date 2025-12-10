"""
Unit tests for JobStatus value object
"""
import pytest
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).resolve().parents[5]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from backend.domain.value_objects.job_status import JobState, JobStatus


class TestJobStatusCreation:
    """Test JobStatus object creation."""
    
    def test_create_queued(self):
        """Test creating queued status."""
        status = JobStatus.queued()
        assert status.state == JobState.QUEUED
        assert status.progress == 0.0
        assert status.error_message is None
    
    def test_create_running(self):
        """Test creating running status."""
        status = JobStatus.running(0.5)
        assert status.state == JobState.RUNNING
        assert status.progress == 0.5
    
    def test_create_completed(self):
        """Test creating completed status."""
        status = JobStatus.completed()
        assert status.state == JobState.COMPLETED
        assert status.progress == 1.0
    
    def test_create_partial(self):
        """Test creating partial status."""
        status = JobStatus.partial(0.7)
        assert status.state == JobState.PARTIAL
        assert status.progress == 0.7
    
    def test_create_error(self):
        """Test creating error status."""
        status = JobStatus.error("Something went wrong")
        assert status.state == JobState.ERROR
        assert status.error_message == "Something went wrong"
    
    def test_create_cancelled(self):
        """Test creating cancelled status."""
        status = JobStatus.cancelled()
        assert status.state == JobState.CANCELLED
        assert status.progress == 0.0


class TestJobStatusFromString:
    """Test JobStatus.from_string() factory method."""
    
    def test_from_string_valid(self):
        """Test creating from valid string."""
        status = JobStatus.from_string("running", 0.5)
        assert status.state == JobState.RUNNING
        assert status.progress == 0.5
    
    def test_from_string_invalid(self):
        """Test creating from invalid string creates error status."""
        status = JobStatus.from_string("invalid_state")
        assert status.state == JobState.ERROR
        assert "Invalid state" in status.error_message


class TestJobStatusProgressClamping:
    """Test that progress is clamped to [0, 1]."""
    
    def test_progress_clamped_high(self):
        """Test progress > 1.0 is clamped."""
        status = JobStatus(JobState.RUNNING, progress=1.5)
        assert status.progress == 1.0
    
    def test_progress_clamped_low(self):
        """Test progress < 0.0 is clamped."""
        status = JobStatus(JobState.RUNNING, progress=-0.5)
        assert status.progress == 0.0


class TestJobStatusTransitions:
    """Test state transition validation."""
    
    def test_can_transition_queued_to_running(self):
        """Test queued can transition to running."""
        status = JobStatus.queued()
        assert status.can_transition_to(JobState.RUNNING)
    
    def test_can_transition_queued_to_cancelled(self):
        """Test queued can transition to cancelled."""
        status = JobStatus.queued()
        assert status.can_transition_to(JobState.CANCELLED)
    
    def test_cannot_transition_queued_to_completed(self):
        """Test queued cannot directly transition to completed."""
        status = JobStatus.queued()
        assert not status.can_transition_to(JobState.COMPLETED)
    
    def test_can_transition_running_to_completed(self):
        """Test running can transition to completed."""
        status = JobStatus.running()
        assert status.can_transition_to(JobState.COMPLETED)
    
    def test_can_transition_running_to_error(self):
        """Test running can transition to error."""
        status = JobStatus.running()
        assert status.can_transition_to(JobState.ERROR)
    
    def test_cannot_transition_completed_to_running(self):
        """Test completed is terminal (cannot transition to running)."""
        status = JobStatus.completed()
        assert not status.can_transition_to(JobState.RUNNING)
    
    def test_can_transition_error_to_running(self):
        """Test error can transition to running (retry)."""
        status = JobStatus.error("Failed")
        assert status.can_transition_to(JobState.RUNNING)
    
    def test_can_transition_partial_to_running(self):
        """Test partial can transition to running (resume)."""
        status = JobStatus.partial()
        assert status.can_transition_to(JobState.RUNNING)


class TestJobStatusTransitionTo:
    """Test transition_to() method."""
    
    def test_transition_to_valid(self):
        """Test valid state transition."""
        status = JobStatus.queued()
        running = status.transition_to(JobState.RUNNING, progress=0.1)
        assert running.state == JobState.RUNNING
        assert running.progress == 0.1
    
    def test_transition_to_invalid(self):
        """Test invalid state transition raises error."""
        status = JobStatus.completed()
        with pytest.raises(ValueError, match="Invalid state transition"):
            status.transition_to(JobState.RUNNING)
    
    def test_transition_preserves_progress(self):
        """Test transition preserves progress if not specified."""
        status = JobStatus.running(0.5)
        partial = status.transition_to(JobState.PARTIAL)
        assert partial.progress == 0.5


class TestJobStatusHelpers:
    """Test helper methods."""
    
    def test_is_terminal_completed(self):
        """Test is_terminal for completed status."""
        assert JobStatus.completed().is_terminal()
    
    def test_is_terminal_cancelled(self):
        """Test is_terminal for cancelled status."""
        assert JobStatus.cancelled().is_terminal()
    
    def test_is_terminal_running(self):
        """Test is_terminal false for running status."""
        assert not JobStatus.running().is_terminal()
    
    def test_is_active_queued(self):
        """Test is_active for queued status."""
        assert JobStatus.queued().is_active()
    
    def test_is_active_running(self):
        """Test is_active for running status."""
        assert JobStatus.running().is_active()
    
    def test_is_active_completed(self):
        """Test is_active false for completed status."""
        assert not JobStatus.completed().is_active()
    
    def test_is_successful(self):
        """Test is_successful for completed status."""
        assert JobStatus.completed().is_successful()
        assert not JobStatus.error("Failed").is_successful()
    
    def test_is_failed(self):
        """Test is_failed for error status."""
        assert JobStatus.error("Failed").is_failed()
        assert not JobStatus.completed().is_failed()
    
    def test_is_partial(self):
        """Test is_partial for partial status."""
        assert JobStatus.partial().is_partial()
        assert not JobStatus.completed().is_partial()
    
    def test_percentage(self):
        """Test percentage helper."""
        assert JobStatus.running(0.75).percentage() == 75.0
        assert JobStatus.completed().percentage() == 100.0


class TestJobStatusStringRepresentation:
    """Test string representation."""
    
    def test_str_without_error(self):
        """Test string representation without error."""
        status = JobStatus.running(0.5)
        assert str(status) == "running (50%)"
    
    def test_str_with_error(self):
        """Test string representation with error message."""
        status = JobStatus.error("Connection failed")
        assert "error" in str(status)
        assert "Connection failed" in str(status)


class TestJobStatusImmutability:
    """Test that JobStatus is immutable."""
    
    def test_cannot_modify_state(self):
        """Test that state cannot be changed after creation."""
        status = JobStatus.queued()
        with pytest.raises(AttributeError):
            status.state = JobState.RUNNING  # type: ignore
    
    def test_cannot_modify_progress(self):
        """Test that progress cannot be changed after creation."""
        status = JobStatus.running(0.5)
        with pytest.raises(AttributeError):
            status.progress = 0.7  # type: ignore
