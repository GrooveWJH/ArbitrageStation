"""Shared domain error types."""

class AppError(Exception):
    """Base application error."""

class DomainError(AppError):
    """Domain-level business error."""

class IntegrationError(AppError):
    """External integration failure."""
