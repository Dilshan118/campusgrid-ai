"""
CampusGrid AI: Agent 2 — MCP Message Integrity and Replay Protection
Module Owner: Member 3 (Digital Twin, Cyber-Physical Physics & Simulation)

The mitigation for Student 4 findings TC-S4-14 and TC-S4-15: a tool-call message altered in
transit (10 kW rewritten to 999 kW, still inside every bounds check) used to execute as-is,
and a captured message could be replayed any number of times.

Each JSON-RPC request is now signed by the calling agent and verified by the tool server:

    params._meta["campusgrid/integrity"] = {
        "key_id":    which shared key signed it (lets keys rotate without downtime),
        "timestamp": Unix seconds when it was signed,
        "nonce":     a random value never reused,
        "signature": hex HMAC-SHA256(secret, "<key_id>\\n<timestamp>\\n<nonce>\\n<canonical body>"),
    }

The canonical body is the request with the integrity block removed, serialized as JSON with
sorted keys and no whitespace, so the signer and the verifier hash identical bytes. The
server rejects a request whose signature is missing or wrong (tampering, or a sender without
the key), whose timestamp is outside the allowed clock skew (a stale capture), or whose nonce
was already used inside that window (a replay). `params._meta` is the place MCP reserves for
protocol metadata, so a client that does not know this extension still sends valid MCP.

This gives integrity and authenticity, not confidentiality: the arguments remain readable
on the wire. Encrypting them is the transport's job (HTTPS/mTLS at the reverse proxy),
which is deployment work owned by the Team Lead.
"""

import hashlib
import hmac
import json
import secrets
import threading
import time
from typing import Any, Callable, Dict, Mapping, Optional, Union

INTEGRITY_META_KEY = "campusgrid/integrity"
DEFAULT_MAX_SKEW_SECONDS = 300
DEFAULT_MAX_TRACKED_NONCES = 100_000

Secret = Union[str, bytes]


def _secret_bytes(secret: Secret) -> bytes:
    return secret.encode("utf-8") if isinstance(secret, str) else secret


def _without_integrity(request: Dict[str, Any]) -> Dict[str, Any]:
    """A copy of the request with the integrity block removed (and an emptied _meta dropped)."""
    body = dict(request)
    params = body.get("params")
    if isinstance(params, dict) and isinstance(params.get("_meta"), dict):
        meta = {k: v for k, v in params["_meta"].items() if k != INTEGRITY_META_KEY}
        params = {k: v for k, v in params.items() if k != "_meta"}
        if meta:
            params["_meta"] = meta
        body["params"] = params
    return body


def canonical_body(request: Dict[str, Any]) -> str:
    """The exact bytes both sides sign: sorted keys, no whitespace, integrity block removed."""
    return json.dumps(_without_integrity(request), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _signature(secret: Secret, key_id: str, timestamp: int, nonce: str, body: str) -> str:
    message = f"{key_id}\n{timestamp}\n{nonce}\n{body}".encode("utf-8")
    return hmac.new(_secret_bytes(secret), message, hashlib.sha256).hexdigest()


def sign_request(
    request: Dict[str, Any],
    key_id: str,
    secret: Secret,
    timestamp: Optional[int] = None,
    nonce: Optional[str] = None,
) -> Dict[str, Any]:
    """Client side: returns a copy of `request` carrying a fresh integrity block."""
    ts = int(time.time()) if timestamp is None else int(timestamp)
    nonce = nonce or secrets.token_hex(16)
    signed = json.loads(json.dumps(_without_integrity(request)))  # deep copy; the caller's dict is untouched
    block = {"key_id": key_id, "timestamp": ts, "nonce": nonce}
    signed.setdefault("params", {}).setdefault("_meta", {})[INTEGRITY_META_KEY] = block
    # Signed over the message as sent (the block itself excluded), exactly as the server sees it.
    block["signature"] = _signature(secret, key_id, ts, nonce, canonical_body(signed))
    return signed


class MessageIntegrityGuard:
    """Server side: verifies signatures, freshness and nonce uniqueness. Thread-safe."""

    def __init__(
        self,
        keys: Mapping[str, Secret],
        max_skew_seconds: int = DEFAULT_MAX_SKEW_SECONDS,
        max_tracked_nonces: int = DEFAULT_MAX_TRACKED_NONCES,
        clock: Callable[[], float] = time.time,
    ):
        if not keys:
            raise ValueError("MessageIntegrityGuard needs at least one signing key")
        self._keys = {key_id: _secret_bytes(secret) for key_id, secret in keys.items()}
        self._max_skew = max_skew_seconds
        self._max_nonces = max_tracked_nonces
        self._clock = clock
        self._seen: Dict[str, float] = {}  # "<key_id>:<nonce>" -> when it stops mattering
        self._lock = threading.Lock()

    def verify(self, request: Any) -> Optional[str]:
        """None if the request is authentic, fresh and unused; otherwise why it is rejected."""
        params = request.get("params") if isinstance(request, dict) else None
        meta = params.get("_meta") if isinstance(params, dict) else None
        block = meta.get(INTEGRITY_META_KEY) if isinstance(meta, dict) else None
        if not isinstance(block, dict):
            return "missing message signature"

        key_id, timestamp, nonce, signature = (block.get(k) for k in ("key_id", "timestamp", "nonce", "signature"))
        if not (isinstance(key_id, str) and isinstance(nonce, str) and nonce
                and isinstance(signature, str) and isinstance(timestamp, int) and not isinstance(timestamp, bool)):
            return "malformed message signature"
        secret = self._keys.get(key_id)
        if secret is None:
            return "unknown signing key"

        expected = _signature(secret, key_id, timestamp, nonce, canonical_body(request))
        if not hmac.compare_digest(expected, signature):
            return "message signature does not match its contents"

        now = self._clock()
        if abs(now - timestamp) > self._max_skew:
            return "message timestamp outside the allowed window"

        # Checked last, and only for authentic messages, so an attacker without the key
        # cannot fill the nonce table.
        with self._lock:
            self._forget_expired(now)
            nonce_key = f"{key_id}:{nonce}"
            if nonce_key in self._seen:
                return "message already processed (replay)"
            if len(self._seen) >= self._max_nonces:
                # Fail closed: evicting a live nonce would reopen the replay window.
                return "too many recent messages; retry shortly"
            self._seen[nonce_key] = timestamp + self._max_skew
        return None

    def _forget_expired(self, now: float) -> None:
        # A nonce only needs remembering while its timestamp could still pass the skew check.
        expired = [k for k, until in self._seen.items() if until < now]
        for k in expired:
            del self._seen[k]
