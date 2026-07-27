"""Domain errors, raised by the service and domain layers.

Pure exceptions with no web-framework dependency, so business logic can signal
failure without importing FastAPI. The HTTP mapping lives in one place —
``api/error_handlers.py`` — which means routes never need try/except.
"""


class DomainError(Exception):
    """Base for expected, user-facing domain failures."""


class NotFoundError(DomainError):
    """A requested resource does not exist (maps to HTTP 404)."""


class BadRequestError(DomainError):
    """The request is invalid in a domain sense (maps to HTTP 400)."""


class ConflictError(DomainError):
    """The request collides with existing state (maps to HTTP 409)."""


class UnprocessableError(DomainError):
    """Well-formed but semantically unusable input (maps to HTTP 422)."""


class UpstreamError(DomainError):
    """A dependency (LLM, third-party API, storage) failed (maps to HTTP 502)."""
