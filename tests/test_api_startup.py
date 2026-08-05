"""The API must import the way the CONTAINER imports it.

OPEN-ISSUES #21: `docker compose up` brought the api container up unhealthy and the
worker never started behind `depends_on: service_healthy`, so nothing in the stack ran
— while `pytest` was fully green.

The cause was an import root mismatch, not a missing package:

    container   uvicorn --app-dir /app/backend/src   ->  `api` is top-level
    tests       from backend.src.api.main import app ->  `api` is a subpackage

`from ..exposure import engine, store` resolves under the second and raises
"attempted relative import beyond top-level package" under the first. Three further
`from ..models import ...` lines sat inside `try/except Exception` blocks, so in the
container they degraded silently instead of failing loudly: `/health` would report
`model_available: false` and `/models` would return 503 no matter what was registered.

So these tests import the app under the container's own layout. A relative import that
reaches above `api` fails here immediately, rather than at `docker compose up` on the
morning of a demo.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = PROJECT_ROOT / "backend" / "src"
API_MAIN = BACKEND_SRC / "api" / "main.py"


def test_no_import_reaches_above_the_api_package():
    """Static check, so it holds even where an optional dependency is absent.

    Parsed rather than grepped: a `from ..x import y` inside a function body is just
    as fatal to the container, and three of the four originals were exactly that.
    """
    tree = ast.parse(API_MAIN.read_text())
    offenders = [
        f"line {node.lineno}: from {'.' * node.level}{node.module or ''} import ..."
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.level >= 2
    ]
    assert not offenders, (
        "imports reaching above the `api` package will break `docker compose up`, "
        "because the container runs uvicorn with --app-dir /app/backend/src which "
        "makes `api` top-level. Use absolute imports (`from exposure import ...`).\n  "
        + "\n  ".join(offenders)
    )


def test_the_app_imports_under_the_container_layout():
    """Import `api.main` in a subprocess with only backend/src on the path.

    A subprocess is deliberate: this process already has the repo root importable, so
    checking in-process would prove nothing about the container.
    """
    code = (
        "import sys; sys.path.insert(0, r'%s')\n"
        "from api.main import app\n"
        "paths = sorted({r.path for r in app.routes if hasattr(r, 'methods')})\n"
        "assert '/health' in paths, paths\n"
        "print('OK', len(paths))\n" % BACKEND_SRC
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    if result.returncode != 0:
        tail = (result.stderr or "").strip().splitlines()[-4:]
        pytest.fail(
            "api.main does not import under the container's layout "
            "(only backend/src on sys.path):\n  " + "\n  ".join(tail)
        )
    assert result.stdout.startswith("OK")


def test_health_is_at_the_unversioned_path_the_healthcheck_uses():
    """The Dockerfile HEALTHCHECK curls /health. If that path moves, the container is
    marked unhealthy and the worker never starts behind `depends_on: service_healthy`
    — an outage caused purely by a route rename."""
    dockerfile = (PROJECT_ROOT / "backend" / "Dockerfile").read_text()
    assert "localhost:8000/health" in dockerfile

    from api.main import app
    paths = {r.path for r in app.routes if hasattr(r, "methods")}
    assert "/health" in paths, "the HEALTHCHECK target is gone"
