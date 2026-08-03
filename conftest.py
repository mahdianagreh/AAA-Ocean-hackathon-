"""Pytest path setup — and the reason there are two roots, not one.

THE HAZARD THIS FILE DOCUMENTS
------------------------------
The project has two import roots:

    backend/src/    the application. `config` here is the PROJECT-WIDE spatial
                    contract package (backend/src/config/spatial.py).
    scripts/        the data-preparation chain. Its settings module is
                    `pulga_config`.

Until 2 August 2026 the scripts module was also called `config`. Standalone that
was fine — running `cd scripts && python process_worldcover.py` puts scripts/ first
on sys.path and the right one wins. Under pytest it was not fine: every test shares
one interpreter, so whichever root got imported first bound `sys.modules["config"]`
for the whole session, and `tests/test_soilgrids_units.py` failed with

    ImportError: cannot import name 'RAW' from 'config'
                 (backend/src/config/__init__.py)

purely because an alphabetically-earlier test had already claimed the name. The fix
was to rename the scripts module to `pulga_config`, so the bare name `config`
belongs unambiguously to the contract package. Please do not reintroduce a
top-level module named `config` anywhere else.

Both roots are added here so individual test files no longer need their own
sys.path stanza, though existing ones are harmless.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

for path in (ROOT, ROOT / "backend" / "src", ROOT / "scripts"):
    p = str(path)
    if p not in sys.path:
        sys.path.append(p)
