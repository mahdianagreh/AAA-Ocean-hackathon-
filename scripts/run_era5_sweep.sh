#!/usr/bin/env bash
# Supervisor for the ERA5-Land sweep, with a CDS-capacity gate.
#
# CDS limits CONCURRENT jobs per user and rejects the surplus rather than
# queueing it. Two consequences learned the hard way on 2 Aug 2026:
#
#   1. Submitting more in parallel does not go faster, it goes to zero. Ten
#      workers produced twenty consecutive 400s.
#   2. Killing a running sweep ORPHANS its accepted jobs. They keep occupying
#      the quota until they finish, so an immediate restart gets rejected —
#      which looks like the sweep is broken when it is only waiting.
#
# So this waits for the user's queue to drain before each attempt, instead of
# retrying blindly into a full queue.
#
#   ./scripts/run_era5_sweep.sh
#
set -uo pipefail
cd "$(dirname "$0")/.."

PY=".venv/bin/python"
LOG="${ERA5_LOG:-data/interim/era5_sweep.log}"
MAX_ATTEMPTS="${MAX_ATTEMPTS:-12}"
WAIT_SECONDS="${WAIT_SECONDS:-60}"
MAX_WAIT_ROUNDS="${MAX_WAIT_ROUNDS:-30}"

mkdir -p "$(dirname "$LOG")"

active_jobs() {
    "$PY" - <<'PY' 2>/dev/null || echo 99
import cdsapi
jobs = cdsapi.Client().client.get_jobs().json.get("jobs", [])
print(sum(1 for j in jobs if j.get("status") in {"accepted", "running"}))
PY
}

for attempt in $(seq 1 "$MAX_ATTEMPTS"); do
    for round in $(seq 1 "$MAX_WAIT_ROUNDS"); do
        n=$(active_jobs | tail -1)
        if [ "$n" -le 0 ] 2>/dev/null; then
            break
        fi
        echo "supervisor: $n job(s) still active in the CDS queue — waiting ${WAIT_SECONDS}s" | tee -a "$LOG"
        sleep "$WAIT_SECONDS"
    done

    echo "" >> "$LOG"
    echo "=== era5 attempt $attempt/$MAX_ATTEMPTS at $(date '+%H:%M:%S') ===" >> "$LOG"

    "$PY" scripts/sweep_era5_land_events.py "$@" >> "$LOG" 2>&1
    status=$?

    on_disk=$(find data/raw/era5_land/events -name '*.nc' 2>/dev/null | wc -l | tr -d ' ')

    if [ "$status" -eq 0 ]; then
        echo "supervisor: ERA5 sweep complete, $on_disk month(s) on disk" | tee -a "$LOG"
        exit 0
    fi

    echo "supervisor: attempt $attempt ended at $on_disk month(s) — backing off" | tee -a "$LOG"
    sleep 120
done

echo "supervisor: gave up after $MAX_ATTEMPTS attempts" | tee -a "$LOG"
exit 1
