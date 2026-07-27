"""Logging setup — structured in production, readable in development.

Called once from ``main.py``. Production emits one JSON object per line so a log
aggregator can index the fields; development emits plain text a human can scan.

Structured context goes in ``extra=``::

    logger.info("analysis_complete", extra={"analysis_id": id, "clause_count": n})

One trap worth knowing: ``extra`` keys that collide with a built-in LogRecord
attribute make the stdlib raise ``KeyError``, not silently shadow. The reserved
names are listed in ``RESERVED_LOG_KEYS`` below — prefix around them
(``source_filename``, not ``filename``).
"""

import json
import logging
import sys
from datetime import UTC, datetime

from core.config import settings

# Attributes present on every LogRecord; anything else a caller attached via
# `extra=` is application context worth emitting.
_STANDARD_ATTRS = frozenset(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {
    "message",
    "asctime",
    "taskName",
}

# Passing any of these in `extra=` raises KeyError inside logging itself.
# The most commonly hit are `filename`, `module`, `name`, and `args`.
RESERVED_LOG_KEYS = _STANDARD_ATTRS


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD_ATTRS:
                payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        JsonFormatter()
        if settings.is_production
        else logging.Formatter("%(levelname)-8s %(name)s  %(message)s")
    )

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(settings.log_level.upper())

    # Uvicorn installs its own handlers; let them bubble up to ours instead so
    # every line in the process shares one format.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(name).handlers.clear()
        logging.getLogger(name).propagate = True
