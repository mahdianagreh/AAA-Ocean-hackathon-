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

import pytest

ROOT = Path(__file__).resolve().parent

for path in (ROOT, ROOT / "backend" / "src", ROOT / "scripts"):
    p = str(path)
    if p not in sys.path:
        sys.path.append(p)


# --------------------------------------------------------------------------
# THE SECOND HAZARD: tests that could not fail
# --------------------------------------------------------------------------
# Five test files in this workstream — test_api_contracts, test_ask_citations,
# test_explain_fidelity, test_exposure_engine, test_soilgrids_units — were written
# as runnable scripts first. Each has a `check(name, cond, detail)` helper that
# PRINTS pass/fail and appends to a module-level FAILURES list, and a
# `if __name__ == "__main__"` block that exits non-zero if FAILURES is non-empty.
#
# Run directly, they work. Run under pytest — which is how the build gates — the
# helper only printed: it never raised, so a test function whose every check FAILED
# still returned normally and was reported as PASSED. `pytest -q` said 429 passed
# while a failing assertion inside those files would have been invisible. That is the
# project's own recurring failure mode (plausible, wrong, no error) turned on the
# thing that is supposed to catch it, and "all green" was partly unearned until this.
#
# Fixed here rather than by rewriting ~60 check() calls into asserts, because the
# printed tables ARE the deliverable for several of them — the caveat-coverage matrix
# is meant to be read, not just passed. So the checks still record everything and the
# whole table still prints; this wrapper then fails the test if anything was recorded.
# One place, all five files, no output lost.
#
# It wraps the CALL phase rather than being an autouse fixture on purpose: a fixture
# can only raise during teardown, which pytest reports as "1 passed, 1 error" for the
# same test — technically a non-zero exit, but it reads like an infrastructure problem
# rather than "your assertion is wrong". Forcing the exception into the call phase
# reports an ordinary FAILED, which is what a reader needs to see.
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item):
    failures = getattr(getattr(item, "module", None), "FAILURES", None)
    tracked = isinstance(failures, list)
    before = len(failures) if tracked else 0

    outcome = yield

    if not tracked:
        return
    recorded = failures[before:]
    # Don't mask a real exception — if the test already blew up, that is the more
    # informative failure and the recorded checks are likely downstream of it.
    if recorded and outcome.excinfo is None:
        outcome.force_exception(AssertionError(
            f"{len(recorded)} check(s) failed and were recorded but never raised "
            f"(see the printed table above):\n  - "
            + "\n  - ".join(str(f) for f in recorded)
        ))
