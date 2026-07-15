"""Structured logging configuration using Python standard library only."""
from __future__ import annotations

import json
import logging
import sys
from typing import Any

from infrastructure.config.settings import settings


class _JsonFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects."""

    _SKIP_KEYS = frozenset(
        {
            "msg",
            "args",
            "levelname",
            "levelno",
            "pathname",
            "filename",
            "module",
            "exc_info",
            "exc_text",
            "stack_info",
            "lineno",
            "funcName",
            "created",
            "msecs",
            "relativeCreated",
            "thread",
            "threadName",
            "processName",
            "process",
            "name",
            "taskName",
        }
    )

    def format(self, record: logging.LogRecord) -> str:
        record.message = record.getMessage()
        if record.exc_info:
            record.exc_text = self.formatException(record.exc_info)

        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.message,
        }

        # Include any extra fields attached by the middleware.
        for key, value in record.__dict__.items():
            if key not in self._SKIP_KEYS and not key.startswith("_"):
                payload[key] = value

        if record.exc_text:
            payload["exception"] = record.exc_text

        return json.dumps(payload, default=str)


def configure_logging() -> None:
    """Apply log level and formatter from current settings to the root logger."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        _JsonFormatter() if settings.json_logs else logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s"
        )
    )

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, settings.log_level, logging.INFO))

    # Silence noisy third-party loggers at WARNING.
    for name in ("uvicorn.access", "uvicorn.error", "fastapi"):
        logging.getLogger(name).setLevel(logging.WARNING)
