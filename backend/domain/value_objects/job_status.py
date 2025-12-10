"""
JobStatus value object

Represents the status of a document processing job.
Enforces valid state transitions.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class JobState(str, Enum):
    """Valid job states."""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class JobStatus:
    """
    Immutable job status with state transition validation.
    
    Tracks current state, progress, and optional error information.
    Validates state transitions to prevent invalid status changes.
    """
    state: JobState
    progress: float = 0.0  # 0.0 to 1.0
    error_message: Optional[str] = None
    
    def __post_init__(self):
        """Validate state and progress."""
        # Ensure state is JobState enum
        if not isinstance(self.state, JobState):
            if isinstance(self.state, str):
                try:
                    object.__setattr__(self, 'state', JobState(self.state))
                except ValueError:
                    object.__setattr__(self, 'state', JobState.ERROR)
            else:
                object.__setattr__(self, 'state', JobState.ERROR)
        
        # Clamp progress to [0, 1]
        progress = self.progress
        if not isinstance(progress, (int, float)):
            progress = 0.0
        elif progress < 0.0:
            progress = 0.0
        elif progress > 1.0:
            progress = 1.0
        object.__setattr__(self, 'progress', float(progress))

    def __eq__(self, other: object) -> bool:
        """Support comparisons with JobStatus, JobState, and string states."""
        if isinstance(other, JobStatus):
            return self.state == other.state
        if isinstance(other, JobState):
            return self.state == other
        if isinstance(other, str):
            return self.state.value == other.lower()
        return NotImplemented

    def __hash__(self) -> int:
        """Hash based on the job state to align with equality semantics."""
        return hash(self.state)
    
    @classmethod
    def queued(cls) -> JobStatus:
        """Create a queued status."""
        return cls(state=JobState.QUEUED, progress=0.0)
    
    @classmethod
    def running(cls, progress: float = 0.0) -> JobStatus:
        """Create a running status with optional progress."""
        return cls(state=JobState.RUNNING, progress=progress)
    
    @classmethod
    def completed(cls) -> JobStatus:
        """Create a completed status."""
        return cls(state=JobState.COMPLETED, progress=1.0)
    
    @classmethod
    def partial(cls, progress: float = 0.5) -> JobStatus:
        """Create a partial completion status."""
        return cls(state=JobState.PARTIAL, progress=progress)
    
    @classmethod
    def error(cls, message: str) -> JobStatus:
        """Create an error status with message."""
        return cls(state=JobState.ERROR, progress=0.0, error_message=message)
    
    @classmethod
    def cancelled(cls) -> JobStatus:
        """Create a cancelled status."""
        return cls(state=JobState.CANCELLED, progress=0.0)
    
    @classmethod
    def from_string(cls, state_str: str, progress: float = 0.0) -> JobStatus:
        """
        Create JobStatus from string state.
        
        Args:
            state_str: State as string
            progress: Optional progress value
            
        Returns:
            JobStatus instance
            
        Examples:
            >>> JobStatus.from_string("running", 0.5)
            JobStatus(state=<JobState.RUNNING: 'running'>, progress=0.5)
        """
        try:
            state = JobState(state_str)
            return cls(state=state, progress=progress)
        except ValueError:
            return cls.error(f"Invalid state: {state_str}")
    
    def can_transition_to(self, new_state: JobState) -> bool:
        """
        Check if transition to new state is valid.
        
        Valid transitions:
        - QUEUED → RUNNING, CANCELLED, ERROR
        - RUNNING → COMPLETED, PARTIAL, ERROR, CANCELLED
        - COMPLETED → (none - terminal state)
        - PARTIAL → RUNNING, COMPLETED, ERROR
        - ERROR → RUNNING (retry)
        - CANCELLED → (none - terminal state)
        
        Args:
            new_state: Proposed new state
            
        Returns:
            True if transition is valid
        """
        valid_transitions = {
            JobState.QUEUED: {JobState.RUNNING, JobState.CANCELLED, JobState.ERROR},
            JobState.RUNNING: {JobState.COMPLETED, JobState.PARTIAL, JobState.ERROR, JobState.CANCELLED},
            JobState.COMPLETED: set(),  # Terminal state
            JobState.PARTIAL: {JobState.RUNNING, JobState.COMPLETED, JobState.ERROR},
            JobState.ERROR: {JobState.RUNNING},  # Allow retry
            JobState.CANCELLED: set(),  # Terminal state
        }
        
        return new_state in valid_transitions.get(self.state, set())
    
    def transition_to(
        self,
        new_state: JobState,
        progress: Optional[float] = None,
        error_message: Optional[str] = None
    ) -> JobStatus:
        """
        Create new JobStatus with transitioned state.
        
        Args:
            new_state: New state to transition to
            progress: Optional new progress value
            error_message: Optional error message
            
        Returns:
            New JobStatus instance
            
        Raises:
            ValueError: If transition is invalid
            
        Examples:
            >>> status = JobStatus.queued()
            >>> running = status.transition_to(JobState.RUNNING, progress=0.1)
            >>> running.state
            <JobState.RUNNING: 'running'>
        """
        if not self.can_transition_to(new_state):
            raise ValueError(
                f"Invalid state transition from {self.state.value} to {new_state.value}"
            )
        
        new_progress = progress if progress is not None else self.progress
        return JobStatus(
            state=new_state,
            progress=new_progress,
            error_message=error_message
        )
    
    def is_terminal(self) -> bool:
        """Check if this is a terminal state (no further transitions allowed)."""
        return self.state in {JobState.COMPLETED, JobState.CANCELLED}
    
    def is_active(self) -> bool:
        """Check if job is currently active (queued or running)."""
        return self.state in {JobState.QUEUED, JobState.RUNNING}
    
    def is_successful(self) -> bool:
        """Check if job completed successfully."""
        return self.state == JobState.COMPLETED
    
    def is_failed(self) -> bool:
        """Check if job failed with error."""
        return self.state == JobState.ERROR
    
    def is_partial(self) -> bool:
        """Check if job partially completed."""
        return self.state == JobState.PARTIAL
    
    def percentage(self) -> float:
        """Get progress as percentage (0-100)."""
        return self.progress * 100.0
    
    def __str__(self) -> str:
        """String representation."""
        if self.error_message:
            return f"{self.state.value} ({self.percentage():.0f}%): {self.error_message}"
        return f"{self.state.value} ({self.percentage():.0f}%)"


# Legacy compatibility constants expected by existing tests
JobStatus.QUEUED = JobState.QUEUED
JobStatus.RUNNING = JobState.RUNNING
JobStatus.PROCESSING = JobState.RUNNING
JobStatus.COMPLETED = JobState.COMPLETED
JobStatus.PARTIAL = JobState.PARTIAL
JobStatus.FAILED = JobState.ERROR
JobStatus.ERROR = JobState.ERROR
JobStatus.CANCELLED = JobState.CANCELLED
