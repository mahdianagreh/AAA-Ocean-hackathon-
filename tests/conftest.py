"""Shared import paths for the test suite.

Every test file was inserting `backend/src` on `sys.path` itself. Doing it once here
is not only tidier — it is what lets `backend/src/api/main.py` use **absolute**
imports (`from exposure import ...`) instead of relative ones that reach above the
`api` package.

That distinction is why the API could not start in Docker while the whole suite was
green. The container runs `uvicorn --app-dir /app/backend/src`, which makes `api` the
top-level package, so `from ..exposure import ...` raises
"attempted relative import beyond top-level package". The tests imported
`backend.src.api.main`, giving `..` a parent to resolve against, so the same line
worked here and failed there. A test suite that validates a package layout the
deployment does not use will pass forever while the product is down.

`tests/test_api_startup.py` now asserts the container's layout directly.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = PROJECT_ROOT / "backend" / "src"

for path in (PROJECT_ROOT, BACKEND_SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


# --------------------------------------------------------------- Phase 8, Track B
# Two endpoints now require a verified Supabase session (tasks/00-contracts.md §9):
# the report-review route and the sensitivity-weight approve route. Both derive the
# reviewer identity from the TOKEN, never from the request body — which is the whole
# point of protecting them, and is why these tests must not simply post a
# `reviewed_by` string and expect it back.
#
# Verifying a real ES256 JWT here would mean either shipping a signing key in the
# repo or reaching out to Supabase's JWKS endpoint from the test suite — a network
# call in a unit test, on a project whose suite must run offline. So the dependency
# is overridden instead: the identity plumbing is exercised end to end, while the
# signature verification itself is auth.py's own concern.

import pytest  # noqa: E402


TEST_USER_EMAIL = "reviewer@aqaba.test"
TEST_USER_SUB = "00000000-0000-4000-8000-00000000test"


@pytest.fixture
def authed_client():
    """A TestClient carrying a verified session, plus the identity it carries.

    Yields `(client, identity)` — `identity` is what the endpoints will record as
    `reviewed_by`/`approved_by`, so a test asserts against it rather than against a
    string it made up.
    """
    from fastapi.testclient import TestClient

    from api import auth
    from api.main import app

    def _fake_user() -> auth.CurrentUser:
        return auth.CurrentUser(sub=TEST_USER_SUB, email=TEST_USER_EMAIL)

    app.dependency_overrides[auth.get_current_user] = _fake_user
    try:
        yield TestClient(app), TEST_USER_EMAIL
    finally:
        # Never leave the override in place: it would silently authenticate every
        # later test in the session, hiding exactly the 401s these routes exist to
        # produce.
        app.dependency_overrides.pop(auth.get_current_user, None)
