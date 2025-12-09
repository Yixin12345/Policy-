"""Domain exceptions."""


class DomainException(Exception):
    """Base exception for domain layer errors."""
    pass


class RepositoryError(DomainException):
    """Exception raised when repository operations fail."""
    
    def __init__(self, message: str, cause: Exception = None):
        super().__init__(message)
        self.cause = cause


class EntityNotFoundError(RepositoryError):
    """Exception raised when an entity is not found in the repository."""
    
    def __init__(self, entity_type: str, entity_id: str, *, message: str | None = None):
        final_message = message or f"{entity_type} not found: {entity_id}"
        super().__init__(final_message)
        self.entity_type = entity_type
        self.entity_id = entity_id


class EntityValidationError(DomainException):
    """Exception raised when entity validation fails."""
    
    def __init__(self, entity_type: str, errors: dict):
        message = f"Validation failed for {entity_type}: {errors}"
        super().__init__(message)
        self.entity_type = entity_type
        self.errors = errors


class DomainValidationError(DomainException):
    """Exception raised when validation fails at the domain boundary."""

    def __init__(self, message: str):
        super().__init__(message)
