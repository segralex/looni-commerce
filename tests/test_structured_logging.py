"""Tests for structured HTTP request logging (EO-LC-000020)."""
from __future__ import annotations

import json
import logging
import sys
import uuid
from pathlib import Path

# Ensure the external LICOS kernel package is importable.
LICOS_ROOT = Path(__file__).resolve().parents[3] / "200_LICOS" / "licos-core"
if LICOS_ROOT.is_dir() and str(LICOS_ROOT) not in sys.path:
    sys.path.insert(0, str(LICOS_ROOT))

import pytest
from fastapi.testclient import TestClient

import app.dependencies as deps
from app.main import app

client = TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _capture_http_logs(caplog) -> list[logging.LogRecord]:
    """Return log records emitted by the HTTP middleware logger."""
    return [r for r in caplog.records if r.name == "looni.commerce.http"]


# ---------------------------------------------------------------------------
# Correlation ID tests
# ---------------------------------------------------------------------------


def test_response_contains_x_correlation_id():
    response = client.get("/health")
    assert "x-correlation-id" in response.headers


def test_supplied_correlation_id_is_preserved():
    my_id = "my-custom-correlation-id-abc"
    response = client.get("/health", headers={"x-correlation-id": my_id})
    assert response.headers["x-correlation-id"] == my_id


def test_generated_correlation_id_is_valid_uuid():
    response = client.get("/health")
    cid = response.headers["x-correlation-id"]
    # Must be parseable as a UUID — will raise ValueError if not.
    parsed = uuid.UUID(cid)
    assert str(parsed) == cid


# ---------------------------------------------------------------------------
# Log record tests
# ---------------------------------------------------------------------------


def test_successful_request_produces_one_log_record(caplog):
    with caplog.at_level(logging.INFO, logger="looni.commerce.http"):
        client.get("/health")
    http_logs = _capture_http_logs(caplog)
    assert len(http_logs) == 1


def test_log_record_contains_required_fields(caplog):
    with caplog.at_level(logging.INFO, logger="looni.commerce.http"):
        client.get("/health")
    record = _capture_http_logs(caplog)[0]
    assert record.method == "GET"
    assert record.path == "/health"
    assert record.status_code == 200
    assert isinstance(record.duration_ms, float)
    assert record.correlation_id


def test_404_request_is_logged(caplog):
    with caplog.at_level(logging.INFO, logger="looni.commerce.http"):
        client.get("/does-not-exist")
    http_logs = _capture_http_logs(caplog)
    assert len(http_logs) == 1
    assert http_logs[0].status_code == 404


def test_duration_ms_is_non_negative(caplog):
    with caplog.at_level(logging.INFO, logger="looni.commerce.http"):
        client.get("/health")
    record = _capture_http_logs(caplog)[0]
    assert record.duration_ms >= 0


def test_correlation_id_in_log_matches_response_header(caplog):
    with caplog.at_level(logging.INFO, logger="looni.commerce.http"):
        response = client.get("/health")
    record = _capture_http_logs(caplog)[0]
    assert record.correlation_id == response.headers["x-correlation-id"]


def test_supplied_correlation_id_appears_in_log(caplog):
    cid = str(uuid.uuid4())
    with caplog.at_level(logging.INFO, logger="looni.commerce.http"):
        client.get("/health", headers={"x-correlation-id": cid})
    record = _capture_http_logs(caplog)[0]
    assert record.correlation_id == cid


# ---------------------------------------------------------------------------
# Unhandled exception test
# ---------------------------------------------------------------------------


def test_unhandled_exception_is_logged_with_correlation_id(caplog, monkeypatch):
    """Inject a route that raises to verify error-level logging with correlation_id."""
    from fastapi import FastAPI
    from app.middleware.logging import RequestLoggingMiddleware

    boom_app = FastAPI()
    boom_app.add_middleware(RequestLoggingMiddleware)

    @boom_app.get("/boom")
    def boom():
        raise RuntimeError("test explosion")

    boom_client = TestClient(boom_app, raise_server_exceptions=False)

    with caplog.at_level(logging.ERROR, logger="looni.commerce.http"):
        boom_client.get("/boom", headers={"x-correlation-id": "test-cid"})

    error_logs = [r for r in caplog.records if r.name == "looni.commerce.http" and r.levelno == logging.ERROR]
    assert len(error_logs) >= 1
    assert error_logs[0].correlation_id == "test-cid"


# ---------------------------------------------------------------------------
# JSON formatter output shape
# ---------------------------------------------------------------------------


def test_json_formatter_produces_valid_json(caplog):
    from infrastructure.logging.config import _JsonFormatter

    formatter = _JsonFormatter()
    record = logging.LogRecord(
        name="looni.commerce.http",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="GET /health 200",
        args=(),
        exc_info=None,
    )
    record.method = "GET"
    record.path = "/health"
    record.status_code = 200
    record.duration_ms = 3.14
    record.correlation_id = "abc-123"

    output = formatter.format(record)
    parsed = json.loads(output)

    assert parsed["level"] == "INFO"
    assert parsed["message"] == "GET /health 200"
    assert parsed["method"] == "GET"
    assert parsed["status_code"] == 200
    assert parsed["duration_ms"] == 3.14
    assert parsed["correlation_id"] == "abc-123"
    assert "timestamp" in parsed
