"""Small, dependency-free admin authentication for the owner dashboard.

The browser receives an opaque, short-lived bearer token after a successful
password check. Only a SHA-256 digest of that token is kept in memory, so a
process dump cannot be used to replay an active session directly. Render runs a
single API process today; a restart intentionally signs every admin session out.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass

from fastapi import HTTPException, Request, status


_SESSION_TTL_SECONDS = 8 * 60 * 60
_LOGIN_WINDOW_SECONDS = 15 * 60
_MAX_FAILED_LOGINS = 5

# This PBKDF2 digest is the server-only fallback for the owner's requested
# initial password. ADMIN_PASSWORD overrides it in every environment where the
# secret is configured. The plaintext password never enters the frontend bundle.
_FALLBACK_SALT = bytes.fromhex("a1f24a40a53f82e6922b687402fa8737")
_FALLBACK_DIGEST = bytes.fromhex(
    "927bcdac94fc84865da841f73c0c09d7398ce31e2e18d277763ebc98e2d3ae4c"
)
_PBKDF2_ROUNDS = 600_000


@dataclass(frozen=True)
class AdminSession:
    token: str
    expires_at: float


_sessions: dict[str, float] = {}
_failed_logins: dict[str, deque[float]] = defaultdict(deque)
_lock = threading.Lock()


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _password_matches(candidate: str) -> bool:
    configured = os.getenv("ADMIN_PASSWORD")
    if configured:
        return hmac.compare_digest(candidate.encode("utf-8"), configured.encode("utf-8"))

    candidate_digest = hashlib.pbkdf2_hmac(
        "sha256",
        candidate.encode("utf-8"),
        _FALLBACK_SALT,
        _PBKDF2_ROUNDS,
    )
    return hmac.compare_digest(candidate_digest, _FALLBACK_DIGEST)


def _client_key(request: Request) -> str:
    # Render supplies the public client address first. Falling back to the
    # socket peer keeps local development and tests deterministic.
    forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
    if forwarded:
        return forwarded
    return request.client.host if request.client else "unknown"


def _prune(now: float) -> None:
    expired = [digest for digest, expiry in _sessions.items() if expiry <= now]
    for digest in expired:
        _sessions.pop(digest, None)


def create_session(password: str, request: Request) -> AdminSession:
    """Verify a login and return a new opaque session, with brute-force limits."""
    now = time.time()
    client = _client_key(request)

    with _lock:
        attempts = _failed_logins[client]
        while attempts and now - attempts[0] > _LOGIN_WINDOW_SECONDS:
            attempts.popleft()
        if len(attempts) >= _MAX_FAILED_LOGINS:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many login attempts. Try again later.",
                headers={"Retry-After": str(_LOGIN_WINDOW_SECONDS)},
            )

    if not _password_matches(password):
        with _lock:
            _failed_logins[client].append(now)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin credentials.",
        )

    token = secrets.token_urlsafe(32)
    expires_at = now + _SESSION_TTL_SECONDS
    with _lock:
        _failed_logins.pop(client, None)
        _prune(now)
        _sessions[_token_digest(token)] = expires_at
    return AdminSession(token=token, expires_at=expires_at)


def require_admin(request: Request) -> str:
    """FastAPI dependency that validates and returns the raw bearer token."""
    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    digest = _token_digest(token)
    now = time.time()
    with _lock:
        _prune(now)
        expires_at = _sessions.get(digest)
    if expires_at is None or expires_at <= now:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin session expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token


def revoke_session(token: str) -> None:
    with _lock:
        _sessions.pop(_token_digest(token), None)
