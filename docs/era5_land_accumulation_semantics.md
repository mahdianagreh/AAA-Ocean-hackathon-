# ERA5-Land Accumulation Semantics

How ReefShield converts ERA5-Land's cumulative hydrological fields into
correct hourly increments.

**Applies to:** `tp` (total precipitation), `sro` (surface runoff),
`ssro` (sub-surface runoff).
**Does not apply to:** `swvl1`, `t2m`, `u10`, `v10` — instantaneous state
variables that must never be deaccumulated.

Implemented by `deaccumulate_era5_land()` in
`backend/src/ingestion/era5_land.py`.

---

## 1. The official convention

ERA5-Land accumulated fields are **forecast accumulations from 00 UTC to the
forecast step**:

| Timestamp | What the raw value means |
|---|---|
| 01:00 | accumulation from 00:00 to 01:00 (**one hour**) |
| 02:00 | accumulation from 00:00 to 02:00 (**two hours**) |
| 12:00 | accumulation from 00:00 to 12:00 (**twelve hours**) |
| 23:00 | accumulation from 00:00 to 23:00 (**twenty-three hours**) |
| 00:00 | the **previous UTC day's full 24-hour total** |

> ⚠️ **Raw accumulated values must never be summed across timestamps.**
> Adding 01:00 + 02:00 + 03:00 counts the first hour three times. Every value
> already contains everything before it that day.

## 2. Why 00:00 belongs to the previous day

The 00:00 stamp is the *end* of the previous day's accumulation window, not
the start of the new one. The forecast run that produced it began at 00 UTC
**the day before** and ran a full 24 hours.

Consequence for the calendar: the value labelled `2016-10-27T00:00:00Z` is the
total rainfall for **26 October**, not for the 27th. Reading it as "the 27th's
midnight rainfall" shifts an entire day of rainfall onto the wrong date — the
single most damaging mistake available here, and one that would silently
misalign every event we backtest.

## 3. Why 01:00 is a reset and must not be differenced against 00:00

At 01:00 the accumulator has restarted from zero. The raw 01:00 value **is**
the first hour's total. Differencing it against 00:00 subtracts an entire
previous day from a single hour, producing a large negative number:

```
00:00  =  5.0 mm   (previous day's 24-hour total)
01:00  =  0.4 mm   (00:00 -> 01:00 of the new day)

WRONG:  0.4 - 5.0 = -4.6 mm
RIGHT:  0.4 mm
```

This is the failure mode the `hour == 1` branch exists to prevent, and the one
`test_zero_one_hundred_reset_uses_raw_value` locks down.

## 4. The rule, in full

| UTC hour | Hourly increment |
|---|---|
| **01** | the raw 01:00 value itself — the daily reset |
| **02–23** | current cumulative − previous cumulative |
| **00** | current 24-hour total − previous day's 23:00 cumulative |

Hours 02–23 and 00 share the same arithmetic (`value[i] − value[i−1]`), because
the predecessor of a 00:00 stamp is the previous day's 23:00 stamp. Only 01:00
is special.

**First timestamp with no predecessor:** if it is 01:00 the increment is still
valid; otherwise the increment is **NaN, never zero**. An unknown hour is not a
dry hour, and zero would understate rainfall silently.

## 5. Interval-end timestamp convention

Derived hourly variables are labelled by **interval end time**:

```
value at 02:00  covers  01:00 -> 02:00
value at 00:00  covers  23:00 -> 00:00 (crossing midnight)
```

Recorded as `interval_label = "interval_end"` on every derived variable. It
matches the raw ERA5 labelling, so raw and derived series stay index-aligned
and a day's 24 increments end at the following 00:00.

**A UTC day spans `DAY T01:00` through `DAY+1 T00:00`** — not `T00:00` through
`T23:00`. Section 7 of the validation script relies on exactly this.

## 6. Metre-to-millimetre conversion

ERA5-Land delivers these fields in **metres of water equivalent**.

```
millimetres = metres * 1000
```

Both forms are kept:

| Variable | Units |
|---|---|
| `tp`, `sro`, `ssro` | `m` — raw cumulative, unchanged |
| `tp_hourly_m`, `sro_hourly_m`, `ssro_hourly_m` | `m` — hourly increment |
| `total_precipitation_hourly_mm` | `mm` |
| `surface_runoff_hourly_mm` | `mm` |
| `subsurface_runoff_hourly_mm` | `mm` |

Conversion happens **after** deaccumulation, never before — scaling first only
adds a factor to every later subtraction.

## 7. Missing data and negative-noise policy

**Sea mask.** ERA5-Land is land-only; cells over water are permanently NaN.
They stay NaN through deaccumulation and are **never interpolated or filled**.
A coastal catchment will legitimately show reduced valid area.

**Negative increments.** After correct reset handling, an accumulated field
cannot decrease. Residual tiny negatives come from float representation:

| Increment | Action |
|---|---|
| `[-1e-10, 0)` m | clamped to `0.0`, counted, and reported |
| `< -1e-10` m | raises `ERA5LandValidationError` |
| `NaN` | left as `NaN` |

The function's default tolerance is `negative_noise_tolerance_m = 1e-10` m.
**That default is calibrated for float64 noise and is too tight for real
ERA5-Land data — pass a larger value when reading CDS downloads.**

### GRIB quantisation, measured

ERA5-Land arrives GRIB-packed, so cumulative values are quantised. Over
2016-10-26/27 the negative increments were **exactly** `-7.45e-9 m` (2⁻²⁷) and
`-1.49e-8 m` (2⁻²⁶) — one and two quantisation steps, never anything between.
Only 11 of 1632 increments were affected (`tp` 5, `sro` 6, `ssro` 0), with the
worst at `-1.49e-5 mm`.

For comparison, float32 spacing near a cumulative value of 1e-6 m is about
1e-13 — five orders of magnitude smaller. So these are *packing* artefacts,
not floating-point rounding.

`scripts/validate_era5_land_deaccumulation.py` therefore passes
`negative_tolerance_m = 1e-7` m (1e-4 mm): roughly 7x the observed step, and
still far below any meteorologically meaningful amount, so a genuine decrease
would still raise.

### Knock-on effect on the daily sum check

Clamping a negative increment to zero **necessarily raises that day's sum** by
the clamped amount, so the day-sum-versus-raw-total check cannot be exactly
zero wherever clamping occurred. The residual is fully attributable, not
mysterious: on 2016-10-26 one cell had `-7.45e-9` clamped at 12:00 and
`-1.49e-8` at 18:00, producing exactly the observed `2.235e-8 m` residual.
2016-10-27 needed no clamping in the compared cells and matched to `0.000e+00`.

The daily check therefore uses the same `1e-7 m` tolerance, documented as
quantisation-driven rather than rounding-driven.

**Nothing is interpolated anywhere in this pipeline.**

## 8. Worked example

Raw cumulative values for one grid cell:

```
2016-10-27T00:00  =  5.0 mm    <- previous day (26 Oct) 24-hour total
2016-10-27T01:00  =  0.4 mm    <- reset; cumulative since 00:00
2016-10-27T02:00  =  1.1 mm    <- cumulative since 00:00
```

Correct hourly increments:

```
00:00  =  derived from the previous day's 23:00 value, when available
01:00  =  0.4 mm                (the reset value itself)
02:00  =  1.1 - 0.4  =  0.7 mm  (ordinary differencing)
```

Incorrect:

```
01:00  =  0.4 - 5.0  =  -4.6 mm     <-- differencing across the reset
```

Cross-check: summing a day's 24 increments (`T01:00` … `T+1 T00:00`) must
reproduce the raw cumulative value at the following `00:00` exactly. The
validation script performs this per variable, per day.

## 9. Validation status

`scripts/validate_era5_land_deaccumulation.py` verifies this against real data
for 2016-10-26 and 2016-10-27 (49 raw timestamps → 48 hourly periods), with
per-day, per-variable sum checks. Results are recorded in
`data/processed/events/era5_land_hourly_20161026_20161027_summary.json`.

Synthetic coverage lives in `tests/test_era5_land_ingestion.py`: reset
handling, midnight arithmetic, NaN-not-zero for the leading hour, two-day
sums, unit conversion, raw-variable immutability, sea-mask preservation,
noise clamping, and rejection of duplicate, unsorted, or gapped timestamps.

## 10. Rules for consumers

1. **Never sum raw `tp`/`sro`/`ssro` across timestamps.** Use the `_hourly_`
   variables.
2. **Never difference across 01:00.** Use `deaccumulate_era5_land()` rather
   than a hand-rolled `.diff("time")`.
3. **Never attribute a 00:00 value to the day it is labelled with** — it
   belongs to the day before.
4. **Never deaccumulate `swvl1`, `t2m`, `u10`, `v10`.** They are instantaneous
   states; the function raises if you try.
5. **Never fill sea-mask NaNs.**
6. A UTC day is `T01:00` → `T+1 T00:00` for these variables.
