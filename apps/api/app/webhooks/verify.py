"""HMAC webhook signature verification for GitHub, GitLab, Bitbucket, Gitea."""

from __future__ import annotations

import hashlib
import hmac


def verify_webhook_signature(
    *,
    provider: str,
    body: bytes,
    secret: str,
    signature_header: str | None,
    alt_header: str | None = None,
) -> bool:
    """Return True when the payload signature matches the shared secret."""
    if not secret:
        return False
    name = provider.lower().strip()
    if name in ("github", "gitea", "forgejo"):
        # X-Hub-Signature-256: sha256=<hex>
        header = signature_header or ""
        if header.startswith("sha256="):
            expected = header.removeprefix("sha256=")
            digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
            return hmac.compare_digest(digest, expected)
        if header.startswith("sha1="):
            expected = header.removeprefix("sha1=")
            digest = hmac.new(secret.encode(), body, hashlib.sha1).hexdigest()  # noqa: S324
            return hmac.compare_digest(digest, expected)
        return False
    if name == "gitlab":
        # X-Gitlab-Token: plain shared secret
        token = signature_header or alt_header or ""
        return hmac.compare_digest(token, secret)
    if name == "bitbucket":
        # X-Hub-Signature: sha256=<hex> (Cloud) or custom DC secret header
        header = signature_header or ""
        if header.startswith("sha256="):
            expected = header.removeprefix("sha256=")
            digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
            return hmac.compare_digest(digest, expected)
        return hmac.compare_digest(header, secret) if header else False
    if name in ("azure_devops", "azure", "ado"):
        # Basic shared secret in header
        token = signature_header or alt_header or ""
        return hmac.compare_digest(token, secret) if token else False
    return False
