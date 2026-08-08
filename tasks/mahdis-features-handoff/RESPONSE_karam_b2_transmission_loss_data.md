# Response: a real measured transmission-loss dataset — for Mahdi, B2

Answers [`HANDOFF_karam_b2_transmission_loss_data.md`](HANDOFF_karam_b2_transmission_loss_data.md).
Not "nothing exists" — found a real, open-access, multi-catchment dataset with an
actual table, not just a range.

## The source

**Cataldo, J.C., Behr, C., Montalto, F.A., & Pierce, R.J. (2010). "Prediction of
Transmission Losses in Ephemeral Streams, Western U.S.A." *The Open Hydrology
Journal*, 4, 19–34.** Open access (CC BY-NC 3.0), full PDF:
https://benthamopen.com/contents/pdf/TOHYDJ/TOHYDJ-4-19.pdf

This paper itself compiles measurements from **three underlying studies** — its own
Walnut Gulch/Queen Creek analysis, plus two literature sources it re-tabulates:
Jordan (1977) and Sharp & Saxton (1962) — which is exactly the "more than one study"
the original ask named as ideal, not just one paper's own site.

## What's in the extracted tables (`data/` in this folder)

- **`cataldo_2010_stream_characteristics.csv`** — Table 1 from the paper, transcribed
  in full: 16 rows (Walnut Gulch's 4 sub-reaches + 12 other named streams/rivers
  across AZ/KS/NE/ND/SD/OK). Columns: reach length (km), contributing area (km²),
  D10 grain size (mm), hydraulic conductivity K (cm/s ×10⁻⁴), annual precip, annual
  runoff.
- **`cataldo_2010_measured_transmission_loss.csv`** — Tables 2, 3 and 4's
  **observed/computed** transmission-loss values (m³/km) — the *measured* column,
  not either paper's own model predictions. 90 storm-event rows, verified by
  parsing the file (not hand-counted): 30 Walnut Gulch storms, 15 Queen Creek
  storms, 45 Midwest storms across 11 more named systems. Each row keys back to
  `system` in the characteristics file, so one stream's fixed characteristics join
  against every storm event measured there — this is what turns 16
  stream-characteristic rows into 90 regression-ready examples (88 joinable —
  see the `Cheyenne River SD` gap below).

## What doesn't map 1:1 to B2's exact ask, stated rather than hidden

1. **No direct "slope" or "drainage density" column.** The paper reports reach
   length, contributing area, D10 (grain size) and K (hydraulic conductivity) instead
   — D10/K are real soil-texture/infiltration proxies, not the same variables B2's
   spec names. Slope and drainage density would need to be derived separately (e.g.
   from DEM data for these same named catchments) if the model needs those exact
   features; alternatively, treat D10/K as the model's soil-texture input directly
   and drop slope/drainage density, or engineer them from public DEMs for these 13
   systems — a real but bounded follow-up, not a blocker to starting.
2. **`Cheyenne River SD` has measured TL (2 storms, Table 4) but no characteristics
   row anywhere in Table 1.** The paper itself doesn't give this one physical
   characteristics — included in the TL file for completeness, flagged as
   non-joinable, not dropped silently and not backfilled with invented numbers.
3. **The source paper is internally inconsistent on two stream names/states**,
   transcribed exactly as printed rather than silently corrected: "Republica Creek"
   (Table 1) vs. "Republic Creek" (Table 4); "Sappa" listed as KS (Table 1) vs. NE
   (Table 4); "Moreau River" listed as SD (Table 1) vs. ND (Table 4). Noted per-row
   in the CSV's `source` column.
4. **Queen Creek's `Q3` event is a statistical outlier** by the paper's own analysis
   (its TL is well below the others) — kept in the data, flagged in the CSV, not
   removed; that's a modeling decision for whoever fits the regression, not mine to
   make by deleting the row.

## What this unblocks

A real regression target (measured TL, m³/km) against real per-catchment physical
data, 79 rows across 13 real systems and 3 independent studies — enough to fit and
sanity-check a model, with the caveats above stated up front rather than discovered
after the fact. If D10/K aren't the right features for B2's exact spec, this is still
the concrete example needed to go find slope/drainage-density data for these same
named, real catchments next, which is a much narrower search than "find a
transmission-loss dataset" was.
