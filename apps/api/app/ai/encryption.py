"""Envelope encryption for provider API keys.

Master key from APP_SECRETS_KEY (or JWT secret in development). A random DEK
encrypts the plaintext; the DEK is wrapped with the master Fernet key.
Never log or return decrypted material to the browser.
"""

from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings


def _master_fernet() -> Fernet:
    settings = get_settings()
    raw = (settings.app_secrets_key or settings.jwt_secret).encode("utf-8")
    # Derive a stable 32-byte url-safe key from the app secret.
    digest = hashlib.sha256(raw).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_secret(plaintext: str) -> dict[str, Any]:
    """Return an envelope blob safe to store in JSONB."""
    if not plaintext:
        raise ValueError("Cannot encrypt empty secret")
    master = _master_fernet()
    dek = Fernet.generate_key()
    data_fernet = Fernet(dek)
    ciphertext = data_fernet.encrypt(plaintext.encode("utf-8")).decode("ascii")
    wrapped_dek = master.encrypt(dek).decode("ascii")
    return {
        "v": 1,
        "alg": "fernet-envelope",
        "wrapped_dek": wrapped_dek,
        "ciphertext": ciphertext,
    }


def decrypt_secret(envelope: dict[str, Any] | None) -> str | None:
    """Decrypt an envelope blob. Returns None when missing."""
    if not envelope:
        return None
    if envelope.get("v") != 1 or envelope.get("alg") != "fernet-envelope":
        raise ValueError("Unsupported secret envelope")
    master = _master_fernet()
    try:
        dek = master.decrypt(envelope["wrapped_dek"].encode("ascii"))
        data_fernet = Fernet(dek)
        return data_fernet.decrypt(envelope["ciphertext"].encode("ascii")).decode("utf-8")
    except (InvalidToken, KeyError, TypeError) as exc:
        raise ValueError("Failed to decrypt secret envelope") from exc


def envelope_to_json(envelope: dict[str, Any]) -> str:
    return json.dumps(envelope, separators=(",", ":"), sort_keys=True)


def has_secret(envelope: dict[str, Any] | None) -> bool:
    return bool(envelope and envelope.get("ciphertext"))
