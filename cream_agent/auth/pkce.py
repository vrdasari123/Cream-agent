"""Pure helper functions for the OAuth 2.1 + PKCE flow (RFC 7636).

Kept separate from the network-heavy OAuth client so the crypto/encoding
logic is trivially unit-testable without mocking HTTP calls.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


@dataclass(frozen=True)
class PkcePair:
    verifier: str
    challenge: str
    method: str = "S256"


def generate_pkce_pair() -> PkcePair:
    """Generate a PKCE code_verifier / code_challenge pair using S256."""
    verifier = _b64url(secrets.token_bytes(64))
    challenge = _b64url(hashlib.sha256(verifier.encode("ascii")).digest())
    return PkcePair(verifier=verifier, challenge=challenge)


def generate_state() -> str:
    return _b64url(secrets.token_bytes(32))


def canonical_resource_uri(url: str) -> str:
    """Normalize an MCP server URL into the canonical form used for the
    OAuth ``resource`` parameter (RFC 8707): lowercase scheme/host, no
    trailing slash, no fragment.
    """
    from urllib.parse import urlsplit, urlunsplit

    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    netloc = parts.netloc.lower()
    path = parts.path.rstrip("/") if parts.path != "/" else ""
    normalized = urlunsplit((scheme, netloc, path, "", ""))
    return normalized
