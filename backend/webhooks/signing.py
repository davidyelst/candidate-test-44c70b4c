"""Webhook request signing (HMAC-SHA256).

Each delivery is signed with the destination endpoint's secret: we HMAC the exact JSON
body we send and pass the hex digest in ``X-Webhook-Signature``. The consumer recomputes
``hmac_sha256(secret, raw_body)`` and constant-time compares it against the header to
confirm the request genuinely came from us and was not tampered with.
"""

import hashlib
import hmac
import json


def canonical_json(payload):
    """Deterministic JSON bytes for `payload`: sorted keys, compact separators.

    These are the exact bytes we sign *and* send, so the consumer verifies against the
    raw body it receives. Pinning the serialisation (not default `json.dumps` spacing)
    keeps the signed bytes stable and reproducible.
    """
    return json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()


def hmac_sha256(secret, message):
    """Hex HMAC-SHA256 of `message` (bytes) keyed by `secret` (str)."""
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
