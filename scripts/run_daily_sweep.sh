#!/usr/bin/env bash
# Supervisor for the stage-1 daily IMERG sweep.
#
# The sweep itself is resumable — granules already on disk are skipped — so the
# safe way to survive a dropped connection is simply to restart it. This loop
# does that until the sweep reports it is complete, or until MAX_ATTEMPTS.
#
# Why it exists: on 2 Aug the laptop slept mid-download, harmony-py blocked on a
# socket that never returned, and the process sat idle for 2 h 40 min while
# still appearing to run. The sweep now exits 75 when it stalls; this loop
# restarts it. Nothing already downloaded is refetched.
#
#   ./scripts/run_daily_sweep.sh              # full record
#   ./scripts/run_daily_sweep.sh --start-year 2016 --end-year 2016
#
set -uo pipefail

cd "$(dirname "$0")/.."

PY=".venv/bin/python"
LOG="${SWEEP_LOG:-data/interim/daily_sweep.log}"
MAX_ATTEMPTS="${MAX_ATTEMPTS:-40}"

mkdir -p "$(dirname "$LOG")"

echo "supervisor: logging to $LOG" | tee -a "$LOG"

for attempt in $(seq 1 "$MAX_ATTEMPTS"); do
    echo "" >> "$LOG"
    echo "=== attempt $attempt/$MAX_ATTEMPTS at $(date '+%Y-%m-%d %H:%M:%S') ===" >> "$LOG"

    "$PY" scripts/sweep_imerg_daily.py "$@" >> "$LOG" 2>&1
    status=$?

    on_disk=$(ls data/raw/imerg/daily_final 2>/dev/null | wc -l | tr -d ' ')

    if [ "$status" -eq 0 ]; then
        echo "supervisor: sweep finished cleanly, $on_disk granule(s) on disk" | tee -a "$LOG"
        exit 0
    fi

    if [ "$status" -eq 75 ]; then
        echo "supervisor: stalled at $on_disk granule(s) — restarting (resume)" | tee -a "$LOG"
    else
        echo "supervisor: exited $status at $on_disk granule(s) — restarting" | tee -a "$LOG"
    fi

    sleep 20
done

echo "supervisor: gave up after $MAX_ATTEMPTS attempts" | tee -a "$LOG"
exit 1
