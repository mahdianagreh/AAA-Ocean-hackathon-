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
