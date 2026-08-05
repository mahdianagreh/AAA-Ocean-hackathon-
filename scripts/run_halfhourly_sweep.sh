#!/usr/bin/env bash
# Supervisor for the stage-2 half-hourly IMERG sweep.
#
# WHY THIS EXISTS
# ---------------
# The sweep itself has no retry. On 4 Aug 2026 a one-second DNS failure made every
# one of 675 events fail inside the same second — `Failed to resolve
# urs.earthdata.nasa.gov` — and the script then logged **"STAGE 2 DONE: 83/675
# event(s) complete"** and exited 0. A network blip therefore looks exactly like a
# finished sweep, which is the worst possible failure mode for an unattended job.
#
# That is not a hypothetical here: this runs on a laptop that moves between home and
# the office, so the network drops, the IP changes and the machine sleeps mid-run.
# Each of those ends the sweep early and silently.
#
# WHAT PROTECTS IT
# ----------------
# Resume is by granule on disk, so relaunching is free and never re-downloads. This
# loop therefore just keeps relaunching until the manifest says every event is
# complete, and — the important part — it decides completion from GRANULES ON DISK
# rather than from the child's exit status, because the child exits 0 on the failure
# we are guarding against.
#
# An IP change is harmless: Earthdata authenticates by token, not by address.
#
#   ./scripts/run_halfhourly_sweep.sh
#   MAX_ATTEMPTS=200 ./scripts/run_halfhourly_sweep.sh
#
set -uo pipefail
cd "$(dirname "$0")/.."

PY=".venv/bin/python"
LOG="${HALFHOURLY_LOG:-data/interim/halfhourly_sweep_full.log}"
MAX_ATTEMPTS="${MAX_ATTEMPTS:-200}"
BACKOFF="${BACKOFF:-60}"
STALL_ROUNDS="${STALL_ROUNDS:-5}"

#: Kill a child that has written no granule for this long. Generous enough that a slow
#: Harmony queue is not mistaken for a hang — a single job can legitimately take a few
#: minutes — and short enough that a night of sleep costs minutes rather than 18 hours.
STALL_MINUTES="${STALL_MINUTES:-12}"
STALL_CHECK_SECONDS="${STALL_CHECK_SECONDS:-60}"

mkdir -p "$(dirname "$LOG")"

granules() { find data/raw/imerg/events -name '*.nc*' 2>/dev/null | wc -l | tr -d ' '; }

# Events still missing granules, straight from the sweep's own manifest.
incomplete() {
    "$PY" - <<'PY' 2>/dev/null || echo 99
import json, pathlib
p = pathlib.Path("data/processed/events/halfhourly_sweep_manifest.json")
if not p.exists():
    print(99); raise SystemExit
m = json.loads(p.read_text())
events = m.get("events") or []
# Field names are `present` / `expected`, checked against the real manifest rather
# than guessed. A wrong key reads every event as incomplete forever, so the
# supervisor would never recognise success and would exit only on the stall guard.
print(sum(1 for e in events if e.get("present", 0) < e.get("expected", 1)))
PY
}

# Resolve + TCP connect, not ping. Plenty of office and hotel networks drop ICMP while
# HTTPS works fine, and a ping-based gate would idle forever on one of those — exactly
# the networks this laptop is moving between.
online() {
    "$PY" -c "
import socket, sys
try:
    socket.create_connection(('urs.earthdata.nasa.gov', 443), timeout=8).close()
except Exception:
    sys.exit(1)
" >/dev/null 2>&1
}

last=$(granules)
stalled=0

for attempt in $(seq 1 "$MAX_ATTEMPTS"); do
    # Wait for the network rather than burning an attempt on a dead link. This is the
    # case that matters when the laptop wakes up somewhere else.
    for _ in $(seq 1 60); do
        online && break
        echo "supervisor: no route to Earthdata — waiting ${BACKOFF}s" | tee -a "$LOG"
        sleep "$BACKOFF"
    done

    echo "" >> "$LOG"
    echo "=== halfhourly attempt $attempt/$MAX_ATTEMPTS at $(date '+%F %H:%M:%S') ===" >> "$LOG"

    # Run the child in the background and watch it for a STALL, not just for exit.
    #
    # This is the failure that got through on 4 Aug. The laptop slept, the TCP socket
    # died under an in-flight Harmony download, and the client blocked on a socket read
    # with no timeout — forever. The process stayed alive for 18h34m having consumed
    # 1m17s of CPU, held no sockets, and wrote nothing. The supervisor was waiting on a
    # child that would never return, so a loop designed to survive network changes sat
    # out the entire night. ERA5 rode through the same sleep because its client has
    # timeouts; harmony-py does not.
    #
    # So progress is judged by GRANULES ON DISK on a timer. If none appear for
    # STALL_MINUTES the child is killed, which drops us into the normal retry path and
    # the whole thing self-heals. Resume is per-granule, so killing mid-download costs
    # only the granule in flight.
    "$PY" scripts/sweep_imerg_halfhourly.py "$@" >> "$LOG" 2>&1 &
    child=$!

    last_seen=$(granules)
    quiet=0
    while kill -0 "$child" 2>/dev/null; do
        sleep "$STALL_CHECK_SECONDS"
        now_seen=$(granules)
        if [ "$now_seen" -gt "$last_seen" ]; then
            last_seen=$now_seen
            quiet=0
        else
            quiet=$((quiet + STALL_CHECK_SECONDS))
            if [ "$quiet" -ge "$((STALL_MINUTES * 60))" ]; then
                echo "supervisor: no new granule in ${STALL_MINUTES} min at $now_seen — child $child looks hung on a dead socket, killing it" | tee -a "$LOG"
                kill "$child" 2>/dev/null
                sleep 5
                kill -9 "$child" 2>/dev/null
                break
            fi
        fi
    done
    wait "$child" 2>/dev/null

    now=$(granules)
    left=$(incomplete | tail -1)

    if [ "$left" -eq 0 ] 2>/dev/null; then
        echo "supervisor: sweep COMPLETE — $now granule(s), 0 incomplete event(s)" | tee -a "$LOG"
        exit 0
    fi

    # Exit status is deliberately ignored above: the child returns 0 after the
    # all-events-failed DNS case. Progress is judged by granule count instead.
    if [ "$now" -le "$last" ]; then
        stalled=$((stalled + 1))
        echo "supervisor: attempt $attempt added nothing ($now granules, $left event(s) left) — stall $stalled/$STALL_ROUNDS" | tee -a "$LOG"
        if [ "$stalled" -ge "$STALL_ROUNDS" ]; then
            echo "supervisor: $STALL_ROUNDS attempts with no progress — stopping so this does not spin silently. Check $LOG." | tee -a "$LOG"
            exit 1
        fi
    else
        stalled=0
        echo "supervisor: attempt $attempt -> $now granule(s), $left event(s) still incomplete" | tee -a "$LOG"
    fi

    last=$now
    sleep "$BACKOFF"
done

echo "supervisor: gave up after $MAX_ATTEMPTS attempts at $(granules) granule(s)" | tee -a "$LOG"
exit 1
