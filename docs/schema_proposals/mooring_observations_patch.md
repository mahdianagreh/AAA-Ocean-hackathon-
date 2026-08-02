# Schema proposal — `mooring_observations` table + `calibration_trials` FK fix

**Status: DRAFT — not applied to `data-model.md`. For Karam (schema arbitration) and
Nizar (implements it in the live Supabase migration) to review and land.**

Per `data-model.md`'s own instruction to the team ("Transcribe it. Do not redesign it. If
you find something genuinely wrong, raise it with Karam and change it once, in that file,
for everyone"), this is that raise — not a unilateral edit to the shared schema file.

---

## The problem

`data-model.md` (§4.7) defines:

```sql
CREATE TABLE calibration_trials (
    id                     bigserial PRIMARY KEY,
    event_id               text NOT NULL REFERENCES events(id),
    observed_plume_id      bigint NOT NULL REFERENCES observed_plumes(id),
    run_id                 text REFERENCES simulation_runs(id),
    diffusion_m2_s         numeric,
    settling_velocity_mm_s numeric,
    windage_fraction       numeric,
    iou                    numeric,
    dice                   numeric,
    centroid_distance_m    numeric,
    area_ratio             numeric,
    is_selected            boolean NOT NULL DEFAULT false
);
```

This table was designed to calibrate a simulated plume against a satellite-derived
observed mask: the `NOT NULL` foreign key to `observed_plumes`, and the metric columns
(`iou`, `dice`, `centroid_distance_m`, `area_ratio`), are all spatial-mask metrics.

That calibration target no longer exists for `AQ-2016-10-28`. `05-abd.md` and
`docs/pitch_limitations.md` are explicit: the Sentinel-2-derived `observed_plumes` row for
this event is a documented coastline artifact, not ground truth, and must never be used as
a calibration target. The real target is the Kalman et al. (2025) mooring record
(`docs/mooring_coordinate_derivation.md`, `data/processed/marine/mooring_target_AQ-2016-10-28.json`),
and the objective is a **time-series match** (arrival time, duration, peak timing), not a
**spatial overlap** (IoU/Dice/centroid).

As written, every calibration trial run against the mooring would either violate the
`NOT NULL` constraint on `observed_plume_id`, or be forced to reference a row
(`observed_plumes`) that has nothing to do with what was actually being fitted — silently
miscategorizing a time-series calibration as a spatial one.

## The proposed fix

Add a new table, and relax the one constraint that assumes every calibration has a
spatial target:

```sql
CREATE TABLE mooring_observations (
    id                       bigserial PRIMARY KEY,
    event_id                 text NOT NULL REFERENCES events(id),
    source_citation          text NOT NULL,          -- 'Kalman et al. (2025)'
    lon                      numeric NOT NULL,
    lat                      numeric NOT NULL,
    position_uncertainty_m  numeric,                 -- 1500 for AQ-2016-10-28; see derivation doc
    position_derivation_doc  text,                   -- 'docs/mooring_coordinate_derivation.md'
    depth_m                  numeric,
    turbidity_onset_utc      timestamptz,
    turbidity_cleared_utc    timestamptz,
    elevated_duration_hours  numeric,
    peak_suspended_sediment_g_l numeric,
    salinity_minimum_psu     numeric,
    salinity_background_mean_psu numeric,
    is_provisional           boolean NOT NULL DEFAULT false
);

-- calibration_trials: relax the spatial-only assumption
ALTER TABLE calibration_trials
    ALTER COLUMN observed_plume_id DROP NOT NULL;

ALTER TABLE calibration_trials
    ADD COLUMN mooring_observation_id bigint REFERENCES mooring_observations(id),
    ADD COLUMN arrival_time_error_hours numeric,
    ADD COLUMN duration_error_hours      numeric,
    ADD COLUMN peak_timing_error_hours   numeric,
    ADD COLUMN transport_regime          text CHECK (transport_regime IN ('hypopycnal','hyperpycnal')),
    ADD CONSTRAINT calibration_trials_target_chk
        CHECK (observed_plume_id IS NOT NULL OR mooring_observation_id IS NOT NULL);
```

**Why a new table rather than overloading `observed_plumes`:** `observed_plumes` is keyed
to a `scene_id` (a specific satellite acquisition) and carries `geom`/`area_km2`/
`reef_overlap_km2` — none of which apply to a fixed in-situ station. Bending it to also
represent a mooring would make every consumer of `observed_plumes` (Pulga's exposure
engine, the API) handle a case that isn't a polygon. A second table keeps each honest.

**Why `ALTER ... DROP NOT NULL` rather than a new `mooring_calibration_trials` table:**
Every future event will have exactly one of {a real observed mask, a mooring record, or
neither} as its calibration target, never both meaningfully at once for this project's
scope. One table with two optional target references, guarded by the new CHECK constraint
(at least one of the two must be present), avoids duplicating `diffusion_m2_s` /
`settling_velocity_mm_s` / `windage_fraction` / `is_selected` across two tables that would
otherwise need to be UNIONed for every "show me all calibration trials" query.

## What this does NOT change

- `observed_plumes` itself is untouched — still exactly as `data-model.md` defines it,
  still populated by the satellite pipeline for the *live* path per `05-abd.md` §4.
- Existing spatial metric columns (`iou`, `dice`, `centroid_distance_m`, `area_ratio`) stay
  — a future event with a real observed mask still uses them.
- No table is dropped or renamed.

## Action needed

1. Karam: confirm this doesn't collide with anything already written against
   `calibration_trials` elsewhere (Pulga's exposure engine reads `plume_forecasts`, not
   this table, so it should be safe — but Karam owns the final call).
2. Nizar: fold the `CREATE TABLE mooring_observations` and `ALTER TABLE calibration_trials`
   statements above into the next migration, and update `data-model.md` §4.7 itself once
   applied — this file is the proposal, not the record of what shipped.
3. Once the table exists, `data/processed/marine/mooring_target_AQ-2016-10-28.json`
   (already built) is the one row to load into it.
