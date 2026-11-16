"""Domain exceptions for core business logic and state validation.

Services raise these domain-specific exceptions. The API layer / exception handlers
translate them into standard HTTP status responses.
"""

from __future__ import annotations


class DomainException(Exception):
    """Base class for all business domain exceptions."""

    def __init__(self, message: str = "A domain error occurred", details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class EntityNotFoundError(DomainException):
    """Raised when an entity requested by ID or unique key is not found."""

    def __init__(self, entity_name: str, identifier: str | int) -> None:
        super().__init__(
            message=f"{entity_name} with identifier '{identifier}' was not found.",
            details={"entity": entity_name, "identifier": str(identifier)},
        )


class EntityConflictError(DomainException):
    """Raised when creating an entity violates uniqueness or a business conflict."""

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message, details)


class AuthenticationError(DomainException):
    """Raised on invalid credentials, expired session, or unverified identity."""

    def __init__(self, message: str = "Authentication failed", details: dict | None = None) -> None:
        super().__init__(message, details)


class PermissionDeniedError(DomainException):
    """Raised when an actor attempts an action forbidden to their role."""

    def __init__(self, message: str = "Permission denied", details: dict | None = None) -> None:
        super().__init__(message, details)


class ValidationError(DomainException):
    """Raised when business validation rules fail."""

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message, details)


class StateTransitionError(DomainException):
    """Raised when an entity lifecycle transition is invalid."""

    def __init__(self, from_state: str, to_state: str, reason: str | None = None) -> None:
        msg = f"Invalid state transition from '{from_state}' to '{to_state}'."
        if reason:
            msg += f" Reason: {reason}"
        super().__init__(msg, details={"from_state": from_state, "to_state": to_state})


class PaymentProcessingError(DomainException):
    """Raised when a payment transaction verification or wallet debit fails."""

    def __init__(self, message: str, tx_ref: str | None = None, details: dict | None = None) -> None:
        details = details or {}
        if tx_ref:
            details["tx_ref"] = tx_ref
        super().__init__(message, details)

