"""Application entry point — wiring only, no logic."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.error_handlers import register_error_handlers
from api.routes import analyses
from core.config import settings
from core.logging import configure_logging

configure_logging()

app = FastAPI(
    title="Clausewise API",
    version="0.1.0",
    description=(
        "Upload a contract, get back every risky clause with a severity, a "
        "plain-English reason, a suggested rewrite, and a citation pointing at "
        "the exact source text."
    ),
    # Hide the interactive docs in production; they are a free map of the API.
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None,
)

register_error_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analyses.router)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    """Liveness probe for the platform's health check."""
    return {"status": "ok", "environment": settings.environment}
