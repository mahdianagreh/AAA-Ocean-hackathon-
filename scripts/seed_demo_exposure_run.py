#!/usr/bin/env python
"""Seed a real, reconstructable exposure run for the demo event.

Why this exists: `GET /api/v1/alerts` answers 200 with an empty list whenever
`exposure_runs.sqlite` has no rows — technically healthy, useless on screen, and it
reads as a bug to anyone watching the demo. The fix is not to hand-write a sqlite
row: `exposure.store.save_run()` refuses a result with no `formula_terms`, and a
score nobody can reconstruct six hours later is a number nobody can defend. So this
calls the ACTUAL FastAPI route, `POST /exposure/calculate`, exactly the way a real
client would, for every outlet against the demo event. The default `--event` is
read from `da.events()` (which parses `docs/event_dates.md`, the single source of
truth per that file's own rule 1), not written as a literal here — `AQ-2016-10-28`
below is what that parse happens to resolve to today, referenced for the reader's
benefit, not hardcoded into any code path this script exercises.


Every score comes out 0.0 today because Mahdi's sediment term is unanchored and
exposure is a product of five terms. That is expected, not a bug in this script —
seed anyway: the shape is what Ali needs, and the numbers fill in once the sediment
anchor lands (tasks/phase3/02-mahdi.md).

Usage:
    .venv/bin/python scripts/seed_demo_exposure_run.py
    .venv/bin/python scripts/seed_demo_exposure_run.py --db /app/var/exposure_runs.sqlite
    .venv/bin/python scripts/seed_demo_exposure_run.py --event AQ-2016-10-28 --outlet AQ-O02

Run inside the api container (or against the same REEFSHIELD_EXPOSURE_DB path) to
seed the volume the running stack actually reads from — seeding a different sqlite
file than the one `/alerts` queries reproduces the exact bug this script exists to
fix, just moved one level down.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend" / "src"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db", default=None,
        help="Path for REEFSHIELD_EXPOSURE_DB. Defaults to the store's own default "
             "(data/outputs/exposure_runs.sqlite) if REEFSHIELD_EXPOSURE_DB is unset.",
    )
    parser.add_argument("--event", default=None, help="Defaults to the documented demo event.")
    parser.add_argument(
        "--outlet", default=None,
        help="Seed one outlet only. Default: seed every outlet, so /alerts has "
             "coverage across whichever reef zones each outlet's plume reaches.",
    )
    parser.add_argument("--horizon-hours", type=int, default=24)
    args = parser.parse_args()

    if args.db:
        os.environ["REEFSHIELD_EXPOSURE_DB"] = args.db

    from api import data_access as da
    from api.main import PREFIX, app
    from fastapi.testclient import TestClient

    client = TestClient(app)

    event_id = args.event
    if event_id is None:
        events = da.events()
        if not events:
            print("no events found via da.events() (docs/event_dates.md unreadable?)", file=sys.stderr)
            return 1
        # The documented demo event is the Oct 2016 flood; fall back to the first
        # parsed event only if that one is somehow absent.
        demo = next((e for e in events if e["event_id"] == "AQ-2016-10-28"), None)
        event_id = (demo or events[0])["event_id"]

    outlet_ids = [args.outlet] if args.outlet else [o["outlet_id"] for o in da.outlets()]
    if not outlet_ids:
        print("no outlets found via da.outlets() — is outlets.geojson readable?", file=sys.stderr)
        return 1

    from exposure import store

    print(f"seeding event={event_id!r} db={store.db_path()}")
    seeded = []
    for outlet_id in outlet_ids:
        r = client.post(
            f"{PREFIX}/exposure/calculate",
            json={"event_id": event_id, "outlet_id": outlet_id, "horizon_hours": args.horizon_hours},
        )
        if r.status_code != 200:
            print(f"  {outlet_id}: SKIP ({r.status_code} {r.text[:120]})")
            continue
        body = r.json()
        n = len(body.get("results", []))
        print(f"  {outlet_id}: run_id={body.get('run_id')} zones_scored={n}")
        seeded.append(body.get("run_id"))

    if not seeded:
        print("nothing seeded — every outlet was skipped", file=sys.stderr)
        return 1

    print(f"\n{len(seeded)} run(s) written to {store.db_path()}")
    recent = store.recent_runs(limit=len(seeded) + 5, event_id=event_id)
    print(f"store now reports {len(recent)} run(s) for {event_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
