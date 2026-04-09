"""Fernet encryption for API keys and bot credentials."""

from __future__ import annotations

import base64
import hashlib
import logging
import os

from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

_fernet: Fernet | None = None


def _fernet_from_secret(secret: str) -> Fernet:
    """Build Fernet from a url-safe key, or derive a stable key from a passphrase."""
    raw = secret.encode("utf-8")
    try:
        return Fernet(raw)
    except Exception:
        derived = base64.urlsafe_b64encode(hashlib.sha256(raw).digest())
        return Fernet(derived)


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        from app.core.config import get_config

        secret = (os.environ.get("QFBJ_ENCRYPT_KEY") or "").strip() or get_config().encrypt_key
        if not secret.strip():
            secret = "qfbj-default-encrypt-key-change-in-prod-32b"
            logger.warning("QFBJ_ENCRYPT_KEY empty; using built-in default (change in production)")
        _fernet = _fernet_from_secret(secret)
    return _fernet


def encrypt(plaintext: str) -> str:
    if not plaintext:
        return ""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    if not ciphertext:
        return ""
    return _get_fernet().decrypt(ciphertext.encode()).decode()


def generate_key() -> str:
    return Fernet.generate_key().decode()
