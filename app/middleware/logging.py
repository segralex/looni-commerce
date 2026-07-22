"""Request logging middleware — no business logic."""
from __future__ import annotations

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from domain.events.context import reset_correlation_id, set_correlation_id

logger = logging.getLogger("looni.commerce.http")

_SENSITIVE_HEADERS = frozenset({"authorization", "cookie", "set-cookie"})


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs one structured record per HTTP request.

    Fields logged: timestamp, level, message, method, path, status_code,
    duration_ms, correlation_id.

    Sensitive headers (Authorization, Cookie, Set-Cookie) are never logged.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        correlation_id = (
            request.headers.get("x-correlation-id") or str(uuid.uuid4())
        )
        token = set_correlation_id(correlation_id)

        start = time.monotonic()
        status_code = 500
        try:
            response: Response = await call_next(request)
            status_code = response.status_code
        except Exception:
            logger.error(
                "Unhandled exception",
                exc_info=True,
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": status_code,
                    "duration_ms": round((time.monotonic() - start) * 1000, 2),
                    "correlation_id": correlation_id,
                },
            )
            raise
        finally:
            reset_correlation_id(token)

        duration_ms = round((time.monotonic() - start) * 1000, 2)

        logger.info(
            f"{request.method} {request.url.path} {status_code}",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": status_code,
                "duration_ms": duration_ms,
                "correlation_id": correlation_id,
            },
        )

        response.headers["x-correlation-id"] = correlation_id
        return response
