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
| Turbidity/salinity cleared (mooring) | **2016-10-29 17:15 local** | Reported by paper |
| Turbidity/salinity cleared in UTC | **2016-10-29T14:15:00Z** | Timezone-converted |
| Elevated turbidity duration | **31.42 h** (06:50Z Oct 28 → 14:15Z Oct 29) | Timezone-converted, then differenced — see note below |
| Peak suspended sediment (mooring) | **2.18 g/L**, near seafloor | Reported by paper |
| Mooring salinity minimum | **38.75 ‰** | Reported by paper |
| Mooring 9-month background salinity mean | **40.53 ‰** | Reported by paper |
| Mooring salinity anomaly | **−1.75 ‰, 19σ below background** | Reported by paper |

**Widespread rainfall reference (2016-10-27T06:00:00Z)** means: by this time,
showers and rainstorms had been registered across the Negev region. It is a
*"rainfall was widespread by now"* marker — **not** the onset and **not** the
peak.

**Offshore instrument response (09:50 local)** is when offshore salinity and
turbidity began fluctuating. This is the **marine signal**, **not the rainfall
peak** — it lags the rainfall by design and is a validation target, not an
input.

**Turbidity/salinity cleared (17:15 local, Oct 29)** is when the mooring's
salinity/turbidity signal returned to background (Kalman et al. 2025, Fig. 6).
Both this and the 09:50 Oct 28 onset are within IDT (UTC+3) — DST does not end
until 2016-10-30, so both convert with the same offset; converted independently
with `ZoneInfo("Asia/Jerusalem")`, not assumed. **31.42 h** is the *paper's own
duration figure, reproduced by differencing the two converted timestamps* —
the paper separately states "~31 hours" in prose; the two agree, which is a
consistency check, not two different measurements.

**Mooring location.** The paper gives only "~250 m offshore the Kinnet Canal
outlet, 13 m depth" — no decimal coordinate. A position was derived from Fig. 1b
plus the project's own coastline and bathymetry data:
[`docs/mooring_coordinate_derivation.md`](mooring_coordinate_derivation.md).
**Read the uncertainty radius (1.5 km) before using that coordinate for
anything.** That document also surfaces a correction: the Kinnet Canal
discharges on the **Eilat (Israel) shoreline**, not at Mahdi's Jordanian
`AQ-O01` pour point — the two are related (same trans-national watershed) but
are not the same point, and are 1.40 km apart.

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

**1. ~~The derived rainfall peak falls AFTER the documented flood arrival.~~
RESOLVED 2 August 2026 — the cause was the bounding box, exactly as suspected.**

The original finding stands as recorded: over the retired box, peak intensity
was at `2016-10-28T02:30Z`, **2.5 hours after** the reported flood arrival at
`2016-10-28T00:00:00Z` — the opposite of the paper's sequence.

Both preconditions named above have since been met. The catchments were
delineated from 30 m GLO-30, and the event was re-fetched over the terrain AOI
(`34.75, 29.15, 35.94, 30.30`) rather than the coastal box that cut off ~85 %
of Wadi Yutum. Recomputed over the catchment polygons themselves:

| Catchment | Peak 3 h window starts | mm | vs flood arrival |
|---|---|---:|---|
| **`AQ-C01` Wadi Yutum** | **2016-10-27T14:00Z** | 4.539 | **10.0 h BEFORE** |
| `AQ-C02` | 2016-10-28T01:00Z | 7.615 | 1.0 h after |
| `AQ-C03` | 2016-10-28T00:00Z | 6.179 | 0.0 h |
| `AQ-C04` | 2016-10-28T00:00Z | 7.987 | 0.0 h |
| `AQ-C05` | 2016-10-28T00:00Z | 7.831 | 0.0 h |

**The ordering is now physically coherent, and the pattern is itself
evidence.** Wadi Yutum — 4,453 km², reaching ~90 km inland, and named by
Kalman et al. as a generating catchment — peaks **10 hours before** the flood
reaches the sea, which is the travel time down the wadi. The four small
coastal catchments (36–65 km²) peak essentially *at* arrival, because there is
almost no distance for water to travel. A large upstream catchment leading a
small coastal one is what a real flood wave looks like.

> **The peak magnitude also changed, and that is expected.** 11.715 mm was the
> wettest single 0.1° cell in the old box; 4.539 mm is the area-weighted mean
> over 4,453 km². A catchment mean is necessarily lower than its own peak
> cell. These two numbers are not comparable and neither supersedes the other
> — one is a cell maximum, the other a catchment mean.

Recomputation: `scripts/analyse_ordering_anomaly.py`.
Full output: `data/processed/events/ordering_anomaly_analysis.json`.

**What this retires:** the caveat above no longer blocks causal statements
about this event, provided they are made over catchments. It does **not**
license the old box's numbers for anything.

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
| Turbidity/salinity cleared `2016-10-29T14:15:00Z` | **Timezone-converted** (`ZoneInfo("Asia/Jerusalem")`, IDT UTC+3) |
| Elevated turbidity duration `31.42 h` | **Derived** — differenced from the two converted timestamps above; agrees with the paper's own "~31 h" prose |
| Peak suspended sediment `2.18 g/L` · salinity minimum `38.75 ‰` · background mean `40.53 ‰` · anomaly `19σ` | **Directly reported by the paper** |
| Mooring coordinate `34.98151, 29.53799 ± 1.5 km` | **Derived** — see `docs/mooring_coordinate_derivation.md`; not a reported coordinate |
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
    turbidity_salinity_cleared_local: 2016-10-29T17:15:00
    rainfall_duration_hours: 66
    accumulation_before_arrival_hours: 51
    concentrated_spell_hours: 18
    concentrated_spell_fraction: 0.82
    rain_start_to_sea_hours: 50
    rain_end_to_arrival_hours: 3
    peak_suspended_sediment_g_l: 2.18
    peak_suspended_sediment_location: near seafloor
    salinity_minimum_psu: 38.75
    salinity_background_mean_psu: 40.53
    salinity_anomaly_sigma: 19
  converted:
    flood_arrival_utc: 2016-10-28T00:00:00Z
    offshore_instrument_response_utc: 2016-10-28T06:50:00Z
    turbidity_salinity_cleared_utc: 2016-10-29T14:15:00Z
    tz_rule: IDT (UTC+3); DST ended 2016-10-30
  derived:
    elevated_turbidity_duration_hours: 31.42
    duration_method: "differenced from offshore_instrument_response_utc and turbidity_salinity_cleared_utc; agrees with paper's own '~31 h' prose"
    mooring_position:
      lon: 34.98151
      lat: 29.53799
      uncertainty_radius_m: 1500
      full_derivation: docs/mooring_coordinate_derivation.md
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
      RESOLVED 2026-08-02. Over the retired box the derived peak (02:30Z) fell
      after the reported flood arrival (00:00Z). Recomputed over the real
      catchments and the terrain AOI, Wadi Yutum (AQ-C01) peaks at
      2016-10-27T14:00Z, 10 h BEFORE arrival, while the small coastal
      catchments peak at arrival - the travel-time pattern of a real flood
      wave. See scripts/analyse_ordering_anomaly.py and
      data/processed/events/ordering_anomaly_analysis.json.
    ordering_resolved: true
    ordering_resolved_utc: 2026-08-02

backup_event:
  event_id: TO_BE_RESOLVED_FROM_KATZ_2015
  month: 2013-02
  source_citation: Katz et al. (2015)
  timing_status: unresolved
  note: February is IST (UTC+2), not IDT

# ---------------------------------------------------------------------------
# The gold validation set for "did sediment reach the sea".
#
# Added 4 August 2026. Kalman et al. (2025) states that 28 October 2016 was
# "the 13th flood recorded since records began in 1994" - so thirteen such
# events exist. We hold the COUNT but only ONE date. The remaining twelve are
# in two papers not on disk; see docs/karam_handoff.md Request 0.
#
# scripts/24_gold_event_validation.py parses this block. Its power calculation
# uses `total_documented`, so the harness reports honestly on a partial list
# rather than silently scoring against n=1 and calling it validation.
#
# Rule 1 still holds: no script hard-codes a date. Add confirmed dates HERE.
# ---------------------------------------------------------------------------
sea_reaching_flood_record:
  total_documented: 13
  record_begins: 1994
  record_ends: 2016-10-28
  source_citation: Kalman et al. (2025), quoting Katz et al. (2015) and Kalman et al. (2020b)
  source_quote: "The flood was the 13th flood recorded since records began in 1994"
  measurement_location: Kinnet Canal outlet, Eilat shoreline
  location_caveat: >-
    These are floods documented on the ISRAELI side. Our five catchments are
    Jordanian. A day absent from this list is NOT a confirmed negative - it may
    be an Aqaba-side flood that nobody recorded. Precision is therefore not
    computable against this set; recall and rank are.
  base_rate:
    floods_per_year_1994_2012: 0.17
    floods_per_year_2012_2020: 1.7
    daily_probability_quote: "less than 0.5%"
    period_label_1994_2012: drought
  dates_confirmed:
    - date: 2016-10-28
      event_id: AQ-2016-10-28
      ordinal_in_record: 13
      sediment_mass_t: 24400
      evidence: mooring time series, Kalman et al. (2025)
  dates_pending:
    count: 12
    blocked_on:
      - citation: Kalman et al. (2020b)
        doi: 10.1111/sed.12737
        journal: Sedimentology 67, 3152-3166
        holds: the 1994- flood record behind the 0.17/yr and 1.7/yr rates
      - citation: Katz et al. (2015)
        holds: the earlier hyperpycnal plume event, approx 20,000 t
    status: unresolved
  known_unresolved_candidates:
    # Mentioned in the literature WITHOUT a usable date. Not usable as labels
    # until a date is confirmed - listed so nobody re-discovers them.
    #
    # PARTIAL PROGRESS 5 Aug 2026 (Karam, Request 0). The twelve missing DATES are
    # still blocked on the two paywalled papers, but Kalman et al. (2025) is fully
    # open access at 10.5194/nhess-25-3201-2025 and quotes enough of them to attach
    # a MAGNITUDE to two candidates and to date a third event outright. Text
    # extracted from the preprint PDF; quotes verified verbatim.
    - period: 2013-02
      note: same as backup_event above; Katz et al. paywalled, no exact day
      sediment_mass_t: 21000
      mass_source_citation: Katz et al. (2015b), quoted in Kalman et al. (2025)
      mass_source_quote: >-
        "similar to the reported 21,000 tons of suspended sediment transported to
        the GEA from the Kinnet Canal during the Feb 2013 flash flood event"
      status_change: >-
        Previously recorded as dead for lack of any figure. The MASS is now
        confirmed from an open-access source, so this event is usable for
        sediment-mass validation even though satellite matching remains
        impossible without a day. 86% of the Oct 2016 mass.
      imerg_candidates_derived:
        # DERIVED, not reported. The two wettest February 2013 storms in our own
        # IMERG record; the paper gives only the month, so which of these is the
        # Katz event is unknown. Listed to narrow a future search from 28 days to 2.
        - event_id: AQ-2013-02-01
          max_daily_mm: 6.95
          catalogue_rank: 31
        - event_id: AQ-2013-02-06
          max_daily_mm: 5.93
          catalogue_rank: 42
    - period: 2006-02
      note: "exceptionally large Aqaba flood, extensive damage (Farhan and Anbar 2014)"
      magnitude_source_citation: Katz et al. (2015), quoted in Kalman et al. (2025)
      seafloor_deposition_kg_m2: 10
      comparison_quote: >-
        "circa 10 kg sediment per meter square coverage of the alluvium on the
        seafloor primary deposition zone after a historical flooding in February
        2006, which magnitude corresponds with 6 kg sediment on average per meter
        square coverage produced by the October 2016 event"
      significant_because: >-
        LARGER THAN OUR DEMO EVENT. 10 kg/m2 against Oct 2016's 6 kg/m2 on the
        same measure and in the same deposition zone. AQ-2016-10-28 is the
        best-INSTRUMENTED documented flood, not the biggest. Do not describe it as
        the largest.
      imerg_candidate_derived:
        event_id: AQ-2006-02-02
        max_daily_mm: 3.36
        catalogue_rank: 96
    - period: 1966-03-11
      note: "50-year return period storm (Farhan and Anbar 2014); pre-satellite, not usable"
    - period: 1940
      note: "'washed away half of modern Aqaba'; historical record only"

# ---------------------------------------------------------------------------
# Dated flood-producing RAINFALL events that are not confirmed sea-reaching
# floods. Kept separate from sea_reaching_flood_record on purpose: a storm that
# flooded streets is not evidence that sediment reached the reef, and merging the
# two would inflate the very base rate Mahdi found to be 21x too generous.
#
# Added 5 Aug 2026 from Kalman et al. (2025), open access.
# ---------------------------------------------------------------------------
dated_flood_producing_rainfall:
  - date: 2017-03-01
    location: Eilat, Israel
    source_citation: Kalman et al. (2025)
    source_quote: >-
      "a local flashflood event recorded on 1 March 2017, when 14.5 mm of rain
      fell in under 3 hours and temporarily flooded the streets of Eilat"
    reported:
      rain_mm: 14.5
      duration_hours_under: 3
      effect: streets of Eilat temporarily flooded
    published_use: >-
      The paper uses this 14.5 mm / 3 h figure AS A THRESHOLD for assessing
      flashflood potential across the basin from GPM-IMERG - the same product our
      pipeline is built on.
    derived_from_our_imerg:
      # DERIVED. This comparison is the reason the threshold cannot be adopted
      # as-is, and it must travel with the number.
      our_max_catchment_daily_mm: 2.93
      our_wettest_catchment: AQ-C01
      our_catalogue_rank: 106
      discrepancy_factor: 4.9
      interpretation: >-
        NOT a contradiction and NOT a product failure. The published 14.5 mm is a
        POINT total over <3 h in Eilat city; ours is an AREA MEAN over a 4,453 km2
        catchment for a whole day. A localised convective cell that floods a town
        averages away over a catchment that size, and IMERG's ~11 km cells smooth
        it further.
      consequence: >-
        A published point threshold cannot be compared to a catchment-mean daily
        depth without a scale correction. Any threshold we quote must state which
        of the two it is. This is the same class of mismatch Mahdi found between
        ERA5 and IMERG - a detection-scale problem, not a calibration one.
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
