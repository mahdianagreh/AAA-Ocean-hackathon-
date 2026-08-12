"""
Phase 8, Track B — Supabase Auth JWT verification.

Decision: tasks/00-contracts.md §9. This project's Supabase project uses the
newer `sb_publishable_`/`sb_secret_` key format, which signs session JWTs
asymmetrically (ES256) and publishes the public verification key at a JWKS
endpoint — so there is no shared "JWT secret" to configure, only
`SUPABASE_URL`, which this repo already has everywhere else.

Only two endpoints in this API require a verified session
(main.py's report-review and sensitivity-weight-approve routes) — everything
else stays public reads, per the same decision.

Absolute-ish import note: this module lives in `backend/src/api/`, imported
from `main.py` as `from . import auth` (level-1 relative) — never `from ..x`,
which `tests/test_api_startup.py` treats as a real failure, not a style
nit (it already caught this exact class of mistake once on this project).
"""

from __future__ import annotations

import os
from pathlib import Path

import jwt
from dotenv import load_dotenv
from fastapi import Header, HTTPException
from jwt import PyJWKClient

# docker-compose.yml's `${SUPABASE_URL:-}` passthrough sets SUPABASE_URL to
# an empty STRING in the container (no root .env exists) -- not unset, so
# load_dotenv's default (never override an already-set var) would keep that
# empty string forever, confirmed live: SUPABASE_URL read as "" until this
# override=True was added. backend/.env's real value must win.
load_dotenv(Path(__file__).resolve().parents[3] / "backend" / ".env", override=True)

_SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
_JWKS_URL = f"{_SUPABASE_URL}/auth/v1/.well-known/jwks.json" if _SUPABASE_URL else ""

# PyJWKClient caches keys and only re-fetches on a kid it hasn't seen —
# module-level so the cache survives across requests, not re-built per call.
_jwk_client: PyJWKClient | None = PyJWKClient(_JWKS_URL) if _JWKS_URL else None


class CurrentUser:
    """The verified identity a protected endpoint receives — never a
    client-supplied string. `sub` is the Supabase Auth user id, `email` is
    only for display/audit text, never for authorization decisions."""

    def __init__(self, sub: str, email: str | None):
        self.sub = sub
        self.email = email

    def __repr__(self) -> str:  # pragma: no cover - debug convenience only
        return f"CurrentUser(sub={self.sub!r}, email={self.email!r})"


def _verify(token: str) -> dict:
    if _jwk_client is None:
        raise HTTPException(
            503,
            "Auth is not configured on this deployment: SUPABASE_URL is not set.",
        )
    try:
        signing_key = _jwk_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256"],
            audience="authenticated",
            issuer=f"{_SUPABASE_URL}/auth/v1",
            options={"require": ["exp", "sub", "iss", "aud"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(401, "Session expired.") from exc
    except jwt.PyJWTError as exc:
        raise HTTPException(401, f"Invalid session token: {exc}") from exc
    return payload


def get_current_user(authorization: str | None = Header(default=None)) -> CurrentUser:
    """FastAPI dependency. `Authorization: Bearer <token>` only — no cookie
    fallback, no query-param token (that class of leak is exactly what this
    is meant to avoid)."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Missing or malformed Authorization header.")
    token = authorization.split(" ", 1)[1].strip()
    payload = _verify(token)
    return CurrentUser(sub=payload["sub"], email=payload.get("email"))


def get_current_user_optional(
    authorization: str | None = Header(default=None),
) -> CurrentUser | None:
    """Same verification as `get_current_user`, but returns `None` on a missing
    header instead of raising — for `/recommendations/trigger`, where auth is
    only required on the human-override path (Phase 9 §2), not on the default
    automatic gate. A malformed or invalid token still raises; this only makes
    the header itself optional, never weakens verification of one that's present."""
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    payload = _verify(token)
    return CurrentUser(sub=payload["sub"], email=payload.get("email"))


def jwks_reachable() -> bool:
    """For a startup/health-style check, not used on the request path —
    confirms the JWKS endpoint actually answers, since a wrong SUPABASE_URL
    would otherwise fail silently until the first protected request."""
    if _jwk_client is None:
        return False
    try:
        _jwk_client.fetch_data()
        return True
    except Exception:
        return False


# Re-exported so main.py's own docstring convention (module-level constants
# documenting intent) has somewhere to point when explaining why these two
# routes, and only these two, take a dependency on this module.
PROTECTED_ROUTES = (
    "PATCH /api/v1/reports/{id}/review",
    "POST /api/v1/reef-zones/{id}/sensitivity-weight/approve",
)

# Conditionally protected: POST /api/v1/recommendations/trigger uses
# get_current_user_optional above, and only requires the header when the
# request carries min_risk_level_override (the human-override path).
