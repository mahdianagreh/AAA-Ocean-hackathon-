# Event Dates — ReefShield Aqaba

Timing contract for the historical flash-flood events used for backtesting.

This file is the **single source of truth for event timing**. Any script that
needs an event window reads its values from here rather than hard-coding dates.
Fulfils task **P3 · Event dates** in `tasks/00-contracts.md`.

> **Read the "Source vs Derived" table before using any timestamp below.**
> Some values are reported by the paper, one is timezone-converted, two are
> engineering windows chosen by us, and one is still unresolved. They are not
> interchangeable.

---

## Primary source

Kalman, A., Katz, T., Vincze, M., Longenecker, J., Mathalon, A., Hill, P., and
Goodman-Tchernov, B. (2025). *Anatomy of a Flash Flood in a Hyperarid
Environment: From Atmospheric Masses to Sediment Dispersal in the Sea.*
Natural Hazards and Earth System Sciences, **25**, 3201–3219.

- DOI: https://doi.org/10.5194/nhess-25-3201-2025
- Published 10 September 2025

> ⚠️ **Citation correction.** `tasks/00-contracts.md:131`, `tasks/karam.md:43`,
> and `tasks/abd.md:27` cite this article as **"Ginat et al. 2025"**. The first
> author is **Kalman**; the article number (25/3201/2025) and DOI are the same
> paper. Cite it as **Kalman et al. (2025)**. Those three task files still need
> fixing — not changed here, because this task scoped edits to this file only.

---

## 1. Primary event — October 2016

### Canonical event ID

```
AQ-2016-10-28
```

**Reason:** the canonical date is the **flood-arrival date in UTC**. Rainfall
began days earlier, so a rainfall-onset ID would disagree with the marine
arrival that the project actually forecasts. Fixing the ID to the arrival date
in UTC keeps event IDs, marine observations, and model targets on one clock.

This resolves the `AQ-2016-10-XX` placeholders in the concept doc
(`reefshield_aqaba_concept.md:481`, `:1117`, `:1502`).

> **Note:** `tasks/00-contracts.md:68` shows `AQ-2016-10-25` in the ID-format
> table. That is a **formatting example**, not this event. The correct ID for
> the October 2016 event is `AQ-2016-10-28`.

### Literature aliases

The same event appears under several names. All refer to `AQ-2016-10-28`:

- October 2016 Aqaba–Eilat flash flood
- 27 October 2016 rainfall/flood event
- 28 October 2016 marine-arrival event

Expect all three in the literature and in search results. The 27 vs 28 October
split is not a contradiction: 27 October refers to the **rainfall**, 28 October
to the **flood reaching the sea**.

### Documented timing

| Item | Value | Basis |
|---|---|---|
| Widespread rainfall reference | **2016-10-27T06:00:00Z** | Reported by paper |
| Flood arrival (witnesses, Eilat) | **2016-10-28 03:00 local** | Reported by paper |
| Flood arrival in UTC | **2016-10-28T00:00:00Z** | Timezone-converted |
| Offshore instrument response | **2016-10-28 09:50 local** | Reported by paper |
| Offshore instrument response in UTC | **2016-10-28T06:50:00Z** | Timezone-converted |

**Widespread rainfall reference (2016-10-27T06:00:00Z)** means: by this time,
showers and rainstorms had been registered across the Negev region. It is a
*"rainfall was widespread by now"* marker — **not** the onset and **not** the
peak.

**Offshore instrument response (09:50 local)** is when offshore salinity and
turbidity began fluctuating. This is the **marine signal**, **not the rainfall
peak** — it lags the rainfall by design and is a validation target, not an
input.

### Timezone conversion (performed, not assumed)

Israel/Eilat local time was converted with `zoneinfo`, not a hard-coded offset:

```python
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

local = datetime(2016, 10, 28, 3, 0, 0, tzinfo=ZoneInfo("Asia/Jerusalem"))
utc = local.astimezone(timezone.utc)
```

Verbatim output:

```
flood arrival (witnesses, Eilat)
  local      : 2016-10-28T03:00:00+03:00
  tzname     : IDT
  utcoffset  : 3:00:00
  dst()      : 1:00:00
  UTC        : 2016-10-28T00:00:00Z

offshore instrument response
  local      : 2016-10-28T09:50:00+03:00
  tzname     : IDT
  utcoffset  : 3:00:00
  dst()      : 1:00:00
  UTC        : 2016-10-28T06:50:00Z
```

**Critical detail — the event falls inside Israel Daylight Time (UTC+3).**
IDT ended on **30 October 2016**, two days *after* the flood:

```
2016-10-25 12:00 -> IDT offset 3:00:00
2016-10-28 12:00 -> IDT offset 3:00:00      <- event: UTC+3
2016-10-29 12:00 -> IDT offset 3:00:00
2016-10-30 12:00 -> IST offset 2:00:00      <- DST ends here
2016-10-31 12:00 -> IST offset 2:00:00
```

Assuming Israel's standard UTC+2 would shift every timestamp **one hour early**
and place the 03:00 arrival at `01:00Z` instead of `00:00Z`. Always convert with
`ZoneInfo("Asia/Jerusalem")`; never subtract a fixed offset.

### Reported rainfall characteristics

Directly from the paper:

- **≈ 66 hours** from rainfall onset to final cessation
- **≈ 51 hours** of accumulation before flood arrival
- **≈ 82 %** of total rainfall fell during a concentrated **18-hour** spell
- flood reached the sea **≈ 50 hours** after rain started
- flood arrived **≈ 3 hours** after most rainfall had ended

The 18-hour/82 % concentration is the reason a 3-hour window can be either
nearly dry or extremely wet depending on placement — which is exactly why the
wettest window must be derived, not guessed.

### Literature-constrained IMERG scan window

```
start : 2016-10-25T00:00:00Z
end   : 2016-10-28T06:00:00Z
```

**⚠️ This is a CONSERVATIVE ANALYSIS WINDOW, derived — not a paper-reported
onset/cessation pair.** The paper reports a ≈66-hour rainfall duration but no
exact onset and cessation timestamps in the text. This window spans ~78 hours,
padding the ≈66-hour event on both sides so the true onset and cessation are
enclosed with margin, and extending past the `00:00Z` flood arrival to cover the
`06:50Z` offshore instrument response.

Use it as the **search space** for deriving exact rainfall timing from IMERG.
Do not cite it as the paper's stated event duration.

### Engineering 3-hour smoke-test window

```
start : 2016-10-27T03:00:00Z
end   : 2016-10-27T05:59:59Z
```

Yields exactly **6 half-hourly IMERG granules**: `03:00, 03:30, 04:00, 04:30,
05:00, 05:30`.

Explicitly:

- **This window ends at the documented 06:00 UTC widespread-rainfall
  reference.** It covers the three hours immediately before rainfall was
  reported as widespread across the Negev.
- **It is selected for multi-granule pipeline testing** — verifying that
  consecutive granule downloads, timestamp ordering, and 30-minute spacing all
  work.
- **It is NOT claimed to be the event's wettest 3-hour period.** No such claim
  is made or implied. Do not use it for any scientific statement about rainfall
  intensity.

### Wettest 3-hour window — DERIVED FROM IMERG

```
wettest_3h_window_utc:
  start : 2016-10-28T02:30:00Z
  end   : 2016-10-28T05:30:00Z
  max_rain_3h_mm : 11.715
  lat : 29.650
  lon : 35.050
```

> **Derived from NASA GPM IMERG V07 over the Aqaba `DOWNLOAD_BBOX`, not
> directly reported by the paper.**

The paper does not give a timestamped intensity maximum in text — it reports
duration, the 18-hour/82 % concentration, and totals. This window was computed
from the half-hourly series across the full literature-constrained scan window
(156 granules, 100 % complete) using trailing rolling 3-hour sums with
`min_periods = 6` and NaN propagation, no interpolation.

Produced by `scripts/process_imerg_oct2016_event.py`; full output in
`data/processed/events/AQ-2016-10-28_summary.json`.

Other derived maxima over the same grid:

| Window | Max (mm) | UTC span | Cell |
|---|---|---|---|
| 1 h | 6.760 | 2016-10-28T02:00Z → 03:00Z | 29.450, 35.050 |
| **3 h** | **11.715** | **2016-10-28T02:30Z → 05:30Z** | **29.650, 35.050** |
| 6 h | 12.990 | 2016-10-28T00:00Z → 06:00Z | 29.650, 35.050 |
| 24 h | 20.545 | 2016-10-27T05:30Z → 2016-10-28T05:30Z | 29.450, 34.850 |

Per-cell 78-hour totals range 16.09–20.82 mm (mean 18.58 mm). Peak half-hourly
intensity over the box is 9.79 mm/hr.

#### ⚠️ Two caveats before using this window scientifically

**1. The derived rainfall peak falls AFTER the documented flood arrival.**
Peak intensity is at `2016-10-28T02:30Z` and the wettest 3 h ends `05:30Z`, but
witnesses report the flood arriving in Eilat at `2016-10-28T00:00:00Z`. The
paper states the flood arrived ≈3 h *after* most rainfall ended — the opposite
ordering. This is **not** grounds to change the literature timestamps. The
likely explanation is spatial: the ~11 km IMERG cell and this small padded box
sample coastal rainfall, while the flood was generated by rainfall over
upstream catchments that may lie largely **outside** `DOWNLOAD_BBOX`. Resolve
this once real catchment polygons exist — recompute over the catchments, not
the box, before drawing any causal conclusion.

**2. The 6 h and 24 h maxima abut the scan-window edge.** The 6 h maximum's
window ends exactly at `06:00:00Z`, the last instant in the scan window, and
its label sits on the final time step. Rainfall is still non-zero at the last
granule (0.42 mm/hr), so a longer window could yield a larger 6 h or 24 h total.
**The 1 h and 3 h maxima are safe** — they peak at indices 149–154 with rates
clearly declining afterwards (9.43 → 0.42 mm/hr), so the intensity peak is
genuinely enclosed. If 6 h or 24 h figures matter, extend the scan window past
`2016-10-28T06:00:00Z` and recompute.

---

## 2. Backup event — February 2013

**Exact timing: UNRESOLVED.** Pending extraction from:

Katz, T. et al. (2015). *Desert flash floods form hyperpycnal flows in the
coral-rich Gulf of Aqaba.* Earth and Planetary Science Letters.
https://www.sciencedirect.com/science/article/pii/S0012821X15001119

```
event_id                : TO_BE_RESOLVED_FROM_KATZ_2015
rainfall_onset_utc      : TO_BE_RESOLVED_FROM_KATZ_2015
flood_arrival_local     : TO_BE_RESOLVED_FROM_KATZ_2015
flood_arrival_utc       : TO_BE_RESOLVED_FROM_KATZ_2015
imerg_scan_window_utc   : TO_BE_RESOLVED_FROM_KATZ_2015
wettest_3h_window_utc   : TO_BE_DERIVED_FROM_IMERG
```

**No date is invented here.** What is known: the concept doc
(`reefshield_aqaba_concept.md:160`) cites ≈21,000 tonnes of suspended sediment
for a February 2013 event, versus ≈24,000 tonnes for October 2016. Month and
year only — no day, no time.

When resolved, note that **February is outside DST**: Israel is on IST
(UTC+2) then, so the offset differs from the October 2016 event. Convert with
`ZoneInfo("Asia/Jerusalem")` rather than reusing UTC+3.

---

## 3. Source vs Derived

| Value | Classification |
|---|---|
| Widespread rainfall reference `2016-10-27T06:00:00Z` | **Directly reported by the paper** |
| Flood arrival `2016-10-28 03:00` local, Eilat | **Directly reported by the paper** |
| Offshore instrument response `2016-10-28 09:50` local | **Directly reported by the paper** |
| ≈66 h duration · ≈51 h pre-arrival accumulation · ≈82 % in 18 h · ≈50 h to sea · ≈3 h rain-end-to-arrival | **Directly reported by the paper** |
| Flood arrival `2016-10-28T00:00:00Z` | **Timezone-converted** (`ZoneInfo("Asia/Jerusalem")`, IDT UTC+3) |
| Offshore response `2016-10-28T06:50:00Z` | **Timezone-converted** (`ZoneInfo("Asia/Jerusalem")`, IDT UTC+3) |
| Canonical ID `AQ-2016-10-28` | **Project convention** — UTC flood-arrival date |
| Scan window `2016-10-25T00:00:00Z → 2016-10-28T06:00:00Z` | **Engineering analysis window** — conservative, padded around the ≈66 h duration |
| Smoke-test window `2016-10-27T03:00:00Z → 2016-10-27T05:59:59Z` | **Engineering analysis window** — pipeline testing only |
| `wettest_3h_window_utc` = `2016-10-28T02:30:00Z → 05:30:00Z`, 11.715 mm | **Derived from IMERG** (Oct 2016; not paper-reported) |
| `wettest_1h / 6h / 24h` maxima | **Derived from IMERG** (6 h and 24 h edge-truncated) |
| February 2013 timing | **Unresolved** — pending Katz et al. (2015) |

---

## 4. Machine-readable summary

```yaml
primary_event:
  event_id: AQ-2016-10-28
  canonical_date_basis: flood arrival date in UTC
  source_doi: 10.5194/nhess-25-3201-2025
  source_citation: Kalman et al. (2025)
  aliases:
    - October 2016 Aqaba-Eilat flash flood
    - 27 October 2016 rainfall/flood event
    - 28 October 2016 marine-arrival event
  reported:
    widespread_rainfall_reference_utc: 2016-10-27T06:00:00Z
    flood_arrival_local: 2016-10-28T03:00:00
    flood_arrival_timezone: Asia/Jerusalem
    offshore_instrument_response_local: 2016-10-28T09:50:00
    rainfall_duration_hours: 66
    accumulation_before_arrival_hours: 51
    concentrated_spell_hours: 18
    concentrated_spell_fraction: 0.82
    rain_start_to_sea_hours: 50
    rain_end_to_arrival_hours: 3
  converted:
    flood_arrival_utc: 2016-10-28T00:00:00Z
    offshore_instrument_response_utc: 2016-10-28T06:50:00Z
    tz_rule: IDT (UTC+3); DST ended 2016-10-30
  engineering:
    imerg_scan_window_utc:
      start: 2016-10-25T00:00:00Z
      end: 2016-10-28T06:00:00Z
      note: conservative padded window covering the reported ~66 h event
    smoke_test_3h_window_utc:
      start: 2016-10-27T03:00:00Z
      end: 2016-10-27T05:59:59Z
      expected_granules: 6
      note: pipeline testing only; NOT the wettest 3 h period
  derived_from_imerg:
    # Derived from NASA GPM IMERG V07 over the Aqaba DOWNLOAD_BBOX,
    # not directly reported by the paper.
    wettest_3h_window_utc:
      start: 2016-10-28T02:30:00Z
      end: 2016-10-28T05:30:00Z
      max_rain_3h_mm: 11.715
      lat: 29.650
      lon: 35.050
    wettest_1h_window_utc:
      start: 2016-10-28T02:00:00Z
      end: 2016-10-28T03:00:00Z
      max_rain_1h_mm: 6.760
    wettest_6h_window_utc:
      start: 2016-10-28T00:00:00Z
      end: 2016-10-28T06:00:00Z
      max_rain_6h_mm: 12.990
      caveat: window ends at the scan-window edge; may be truncated
    wettest_24h_window_utc:
      start: 2016-10-27T05:30:00Z
      end: 2016-10-28T05:30:00Z
      max_rain_24h_mm: 20.545
      caveat: window ends at the scan-window edge; may be truncated
    granules_used: 156
    completeness_percent: 100.0
    produced_by: scripts/process_imerg_oct2016_event.py
    summary: data/processed/events/AQ-2016-10-28_summary.json
    caveat_ordering: >-
      Derived rainfall peak (02:30Z) falls after the reported flood arrival
      (00:00Z). Likely because upstream catchments lie outside DOWNLOAD_BBOX;
      recompute over catchment polygons before any causal claim.

backup_event:
  event_id: TO_BE_RESOLVED_FROM_KATZ_2015
  month: 2013-02
  source_citation: Katz et al. (2015)
  timing_status: unresolved
  note: February is IST (UTC+2), not IDT
```

---

## 5. Rules for consumers of this file

1. **Never hard-code an event date in a script.** Read it from here.
2. **Never use `smoke_test_3h_window_utc` for a scientific claim.** It is a
   plumbing test window.
3. **Never substitute a placeholder for `wettest_3h_window_utc`.** If it still
   reads `TO_BE_DERIVED_FROM_IMERG`, the derivation has not been run.
4. **Always convert local times with `ZoneInfo("Asia/Jerusalem")`.** The
   October 2016 event is UTC+3; February 2013 will be UTC+2.
5. **When the wettest window is derived, record it here** together with the
   script that produced it, and keep the classification table current.
