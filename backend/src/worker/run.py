"""Worker loop — the jobs an HTTP request cannot wait for.

A particle simulation takes minutes. The API drops a job, this picks it up.
Currently a heartbeat: the queue lands with Nizar's Supabase schema, and the
first real job is the daily rainfall sweep.

Kept deliberately dumb. A worker that crashes silently is worse than one that
does nothing visibly, so it logs every tick and exits loudly on failure.
"""

import os
import sys
import time
from datetime import datetime, timezone

POLL_SECONDS = int(os.environ.get("REEFSHIELD_WORKER_POLL", "30"))


def log(msg: str) -> None:
    print(f"[worker {datetime.now(timezone.utc):%H:%M:%S}] {msg}", flush=True)


def main() -> int:
    log(f"started · poll {POLL_SECONDS}s · python {sys.version.split()[0]}")
    if not os.environ.get("SUPABASE_URL"):
        log("SUPABASE_URL unset — idling. No queue to read yet "
            "(Nizar, workstream 3).")
    ticks = 0
    while True:
        ticks += 1
        # Placeholder for: claim job -> run -> write result -> mark done.
        if ticks % 10 == 1:
            log(f"alive, {ticks} ticks, no queue configured")
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    raise SystemExit(main())
