"""Envelope encryption unit tests."""

from app.ai.encryption import decrypt_secret, encrypt_secret, has_secret


def test_envelope_roundtrip() -> None:
    blob = encrypt_secret("sk-test-secret")
    assert blob["v"] == 1
    assert blob["alg"] == "fernet-envelope"
    assert "wrapped_dek" in blob and "ciphertext" in blob
    assert decrypt_secret(blob) == "sk-test-secret"
    assert has_secret(blob) is True


def test_envelope_missing() -> None:
    assert decrypt_secret(None) is None
    assert has_secret(None) is False
