"""Custom exception hierarchy for BEW application."""


class ValidationError(Exception):
    """Raised when user input fails a business rule.

    Use this for form validation, missing required fields,
    or any constraint the user can fix by correcting input.
    """
    pass


class AuthorizationError(Exception):
    """Raised when an action requires authorization that was not provided."""
    pass


class DuplicateError(Exception):
    """Raised when a unique constraint would be violated."""
    pass


class FileUploadError(Exception):
    """Raised when a file upload operation fails."""
    pass


class NotFoundError(Exception):
    """Raised when a requested resource does not exist."""

    def __init__(self, resource: str, id=None) -> None:
        if id is not None:
            detail = f"{resource} '{id}' not found."
        else:
            detail = f"{resource} not found."
        super().__init__(detail)
        self.resource = resource
        self.id = id


class DatabaseError(Exception):
    """Raised when a database operation fails unexpectedly."""

    def __init__(self, message: str = "A database error occurred.") -> None:
        super().__init__(message)


class ExternalServiceError(Exception):
    """Raised when an external service fails."""

    def __init__(self, service: str, message: str, details: dict | None = None) -> None:
        super().__init__(f"{service} error: {message}")
        self.service = service
        self.details = details or {}

