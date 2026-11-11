"""Errors raised by the services; the API maps them to HTTP status codes."""


class ServiceError(Exception):
    """Base class of every business-logic error."""


class NotFoundError(ServiceError):
    """The requested record does not exist."""


class ConflictError(ServiceError):
    """The operation violates a uniqueness rule."""


class InvalidReferenceError(ServiceError):
    """The data refers to records that do not exist or do not match each other."""


class TranscriptionError(ServiceError):
    """The speech-to-text provider failed."""


class EmptyTranscriptionError(ServiceError):
    """The audio contained no recognisable speech."""


class ConfigurationError(ServiceError):
    """A required setting is missing (e.g. the seller's data for invoices)."""


class EmailError(ServiceError):
    """The email could not be sent."""
