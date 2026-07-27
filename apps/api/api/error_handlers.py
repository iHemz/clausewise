"""Maps domain errors to HTTP responses, once, for the whole app.

Registering one handler on the base ``DomainError`` (Starlette walks the
exception MRO) means routes never need try/except — they call the service and
return, and any domain error is translated here. The catch-all keeps an
unexpected exception from leaking a stack trace to the client while still
logging it in full.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from core.errors import (
    BadRequestError,
    ConflictError,
    DomainError,
    NotFoundError,
    UnprocessableError,
    UpstreamError,
)

logger = logging.getLogger("app.errors")

# Ordered most-specific first; the first isinstance match wins.
_STATUS: list[tuple[type[DomainError], int]] = [
    (NotFoundError, 404),
    (BadRequestError, 400),
    (ConflictError, 409),
    (UnprocessableError, 422),
    (UpstreamError, 502),
]


def register_error_handlers(app: FastAPI) -> None:
    async def handle_domain_error(_: Request, exc: Exception) -> JSONResponse:
        status = next((s for cls, s in _STATUS if isinstance(exc, cls)), 500)
        return JSONResponse(status_code=status, content={"detail": str(exc)})

    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "unhandled_error", extra={"path": request.url.path, "method": request.method}
        )
        return JSONResponse(status_code=500, content={"detail": "Internal server error."})

    app.add_exception_handler(DomainError, handle_domain_error)
    app.add_exception_handler(Exception, handle_unexpected)
