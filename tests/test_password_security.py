"""Tests for password hashing (EO-LC-000021)."""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure the external LICOS kernel package is importable.
LICOS_ROOT = Path(__file__).resolve().parents[3] / "200_LICOS" / "licos-core"
if LICOS_ROOT.is_dir() and str(LICOS_ROOT) not in sys.path:
    sys.path.insert(0, str(LICOS_ROOT))

import pytest

from infrastructure.security.passwords import hash_password, verify_password


def test_hash_differs_from_plaintext():
    password = "MySecurePassword123!"
    hashed = hash_password(password)
    assert hashed != password


def test_correct_password_verifies():
    password = "MySecurePassword123!"
    hashed = hash_password(password)
    assert verify_password(password, hashed) is True


def test_wrong_password_fails():
    password = "MySecurePassword123!"
    hashed = hash_password(password)
    assert verify_password("WrongPassword123!", hashed) is False


def test_short_password_rejected():
    with pytest.raises(ValueError, match="at least 10 characters"):
        hash_password("short")


def test_empty_password_rejected():
    with pytest.raises(ValueError):
        hash_password("")
