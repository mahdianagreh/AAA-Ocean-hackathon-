# Event Audit — Satellite Imagery for Plume Validation

**Owner:** Abd · **Project:** AQABA AQUA AI · **Workstream:** B (Remote Sensing)

This is the project's gating deliverable per `tasks/abd.md` §1: confirm at least one
historical event has a usable post-event scene before anything downstream is built.

> **Status: IN PROGRESS.** Scene-metadata search is done for both candidate events.
> Pixel-level visual QC (cloud % over AOI water specifically, sun glint, plume
> visibility) is **blocked** — see §4. Do not treat the verdicts below as final
> until that QC is complete.

---

## 0. Method and a real gap this caught

**Search sources:**
- Sentinel-2 metadata — official **Copernicus Data Space OData catalog**
  (`https://catalogue.dataspace.copernicus.eu/odata/v1/Products`). Search is
  **anonymous, no account needed.**
- Landsat metadata + pixels — **Earth Search STAC** (AWS, Element84),
  `https://earth-search.aws.element84.com/v1`, collection `landsat-c2-l2`.
  Also anonymous.

**⚠️ Cross-validation caught a real archive gap.** Earth Search's own
`sentinel-2-l2a` collection (an AWS mirror) has **zero scenes for our tiles
(36RXT / 36RYT) before 2017-01-01**, despite claiming a 2015-06-27 temporal
extent. Querying the *official* Copernicus Data Space catalog directly shows
coverage from at least January 2016. **Conclusion: never trust the AWS
Earth-Search mirror alone for Sentinel-2 dates before 2017 over this AOI** —
always cross-check against the official catalog, or a false "no coverage"
verdict would have been reported for the entire October 2016 event.

**Search extent:** padded box `34.80, 29.25, 35.15, 29.70` (contract
`DOWNLOAD_BBOX`). AOI water-specific cloud scoring (per the acceptance
criteria) is not yet computed — see §4.

---

## 1. Event AQ-2016-10-28 (primary) — Sentinel-2

Flood arrival: `2016-10-28T00:00:00Z` (see `docs/event_dates.md`).
Search window: `2016-10-18` → `2016-11-07` (±10 days).

**Only two acquisition dates fall in this window** — Sentinel-2B did not launch
until April 2017, so 2016 had single-satellite (S2A-only) coverage at this
tile's ~10-day revisit, not the ~5-day revisit possible today.

| Date | Tiles | Days from event | Cloud cover (scene-level metadata) | Role |
|---|---|---:|---:|---|
| 2016-10-23 | 36RXT, 36RYT | −5 (pre) | 82.8% / 85.4% | pre-event — **too cloudy to use** |
| **2016-11-02** | 36RXT, 36RYT | **+5 (post)** | **3.9% / 4.2%** | **post-event candidate** |

**Numerically clears the gate** (§1 of `abd.md`: within ~5 days, <20% cloud) —
but see §1a below: **the visual/plume-visibility half of the gate fails.**

**Product IDs** (Copernicus Data Space `Id`, and the Planetary Computer STAC
IDs actually used for pixel access — see §1a):
- `S2A_MSIL2A_20161102T082112_N0500_R121_T36RYT_20231026T122456` — id
  `6ea1d505-8d0a-4bc4-aa28-2e0ce64e8b26`
- `S2A_MSIL2A_20161102T082112_N0500_R121_T36RXT_20231026T122456` — id
  `bc4a6f07-9dcb-4408-875e-e36fdc01607c` — Planetary Computer:
  `S2A_MSIL2A_20161102T082112_R121_T36RXT_20210213T163836`

### 1a. Pixel-level QC — done, using Microsoft Planetary Computer (no credentials needed)

**Unblocked without Copernicus/Earth Engine credentials.** The AWS Earth
Search mirror has no Sentinel-2 scenes for this tile before 2017 (§0), and
Copernicus Data Space needs a login for actual pixel bytes — but **Microsoft
Planetary Computer's STAC API (`planetarycomputer.microsoft.com/api/stac/v1`)
serves both Sentinel-2 L2A and Landsat Collection 2 L2 publicly**, with
per-asset SAS tokens issued anonymously via the `planetary-computer` Python
package (`pip install planetary-computer`, `pc.sign(item)`). This is how every
pixel-level result below was produced — reproducible via
`scripts/run_plume_extraction.py`.

**AOI-water cloud % (the actual gate metric, not scene-level metadata):**
computed from the post-event scene's own SCL band, restricted to a stable
water mask (SCL class 6, majority vote across 8 clear 2016 baseline scenes —
see §1b). Result: **0.07% cloud/shadow over AOI water, 0.71% suspected glint.**
Both trivially clear. This part of the gate is genuinely satisfied.

**Visual inspection — no plume visible.** True-color mosaics were pulled for
both the full AOI and a tight crop on the head of the gulf (where the Kinnet
outlet is) for **two independent sensors**:
- Sentinel-2, 2016-11-02 (+5 days, 10 m) — clean, cloud-free, no visible
  sediment discoloration anywhere near the outlet or the shoreline.
- Landsat 8, 2016-11-01 (+4 days, 30 m, tile 174039 only — the other half of
  the scene, tile 174040, was 32.8% cloud) — same result, one day closer to
  the event, independently confirms no visible plume.

**Why: the plume was already gone before either satellite pass.** The Kalman
et al. (2025) mooring record (§6a) shows the turbidity/salinity anomaly at
250 m offshore lasted from 09:50 Oct 28 to ~17:15 Oct 29 — about 31 hours.
Both satellite passes are **2.5–3.5 days after that signal had already
returned to background.** The absence of a visible plume in imagery isn't a
failed detection — it's the physically expected outcome given how fast this
particular flood's plume dispersed relative to the ~5-day revisit gap
(single-satellite S2A cadence in 2016; abd.md's own "Watch out" already
flagged 24–72 h dispersal against a 5-day revisit as the central risk here).

**Spectral-anomaly attempt confirms this, and surfaces a real methodology
lesson.** Ran the full pipeline (§4/§1c below): baseline composite (8 clear
2016 scenes, median) vs. the 2016-11-02 scene, four candidate indices
(NDSSI, NSMI, red/green ratio, plain red-band reflectance anomaly). The
result was **not a localized signal near the outlet** — it was a large,
uniform anomaly hugging the **entire coastline on both shores**, including
stretches tens of kilometers from any wadi outlet (see
`docs/qa_screenshots/plume_index_comparison_AQ-2016-10-28.png` and
`plume_polygons_over_baseline.png`-equivalent inspection). Repeating with a
same-season single-scene baseline (Oct 13, only 20 days before) and a much
larger coastal buffer (80 m erosion) did **not** remove this — ruling out
"seasonal mismatch" as the explanation. This is a **mixed-pixel /
atmospheric-correction artifact inherent to differencing Sentinel-2 L2A
reflectance over open water across dates** (Sen2Cor's atmospheric correction
is land-optimized; sun-angle and residual aerosol differences between
acquisitions swamp subtle water-leaving-radiance signals at basin scale). Not
a bug in the water mask or index math — a documented limitation of naive
per-pixel differencing over water, worth remembering before trusting this
pipeline's raw anomaly output as "the plume" on any other event.

**Manual QC figure:** `docs/qa_screenshots/plume_manual_qc_AQ-2016-10-28.png`
— true color vs. the raw anomaly side by side, with this caveat captioned
directly on the figure.

**Verdict on this scene: NO real plume detected, by three independent lines
of evidence** (two-sensor visual inspection, in-situ mooring timing, and a
spectral anomaly check that itself only surfaces an artifact, not a
localized signal). See §3 for what this means for the project.

### 1b. Baseline composite — built

8 clear Sentinel-2 scenes, all <1.1% cloud, S2A-only (2016 pre-dates S2B),
2016-06-25 through 2016-10-13 (search window widened past the post-event
±10-day gate on purpose — that window is only for the post-event gate check,
per abd.md; the baseline just needs clear pre-event scenes, however far back):

`S2A_MSIL2A_20161013T082002`, `20161003T081752`, `20160923T082002`,
`20160913T081602`, `20160903T082012`, `20160824T081602`, `20160814T082012`,
`20160725T082012` — all tile T36RXT, Planetary Computer IDs, median-composited
per band. Saved: `data/processed/plume/baseline_composite.tif`.

### 1c. Pipeline code

- `backend/src/models/plume_segmentation.py` — reusable functions: scene
  search/load (Planetary Computer), stable SCL-based water mask, unusable/
  glint masks, the four spectral indices, baseline compositing, anomaly,
  percentile-stretch "probability," polygon vectorization.
- `scripts/run_plume_extraction.py` — runs the whole thing end to end for
  AQ-2016-10-28 and writes every output file.
- Outputs exist (`data/processed/plume/observed_plume_probability.tif`,
  `data/processed/vectors/observed_plume.gpkg`, 110 polygons, ~2.0 km² total)
  **but per §1a these represent the coastal artifact, not a validated plume —
  do not hand these to Nizar or the backtest as ground truth without that
  caveat attached.** Grade: **not gradable Gold/Silver/Bronze — this is a
  null result**, not a weak-but-real detection (§12.4 doesn't have a category
  for "pipeline ran, found nothing real"; recommend the team add one, or just
  say so plainly in the demo).

---

## 2. Backup event — February 2013

**Exact date: UNRESOLVED.** `docs/event_dates.md` §2 already flags this — Katz
et al. (2015) is paywalled on ScienceDirect (403 on automated fetch), and no
free full text was found (checked: academia.edu mirror blocked automated
fetch, ADS abstract page returned empty, the 2025 NHESS companion paper only
repeats the 21,000-tonne sediment figure without a date). **Needs a
teammate with journal/institutional access to pull the actual day.** See §4.

### Sentinel-2 — confirmed impossible, not just unlikely

Sentinel-2A launched **2015-06-27**, over two years after this event.
Confirmed (not assumed): the official catalog has no Sentinel-2 product of any
kind before its launch date. **There is no Sentinel-2 path for this event,
full stop** — matches `tasks/abd.md` §3's expectation.

### Landsat — the real finding, and it overturns an assumption in `abd.md`

`tasks/abd.md` §3 says Landsat 8 (launched Feb 2013) is "marginal but usable."
**That does not hold.** Coarse-scanned the full month (exact day unknown, so
±10-day framing isn't yet possible):

| Date | Scene | Cloud cover | Platform | Note |
|---|---|---:|---|---|
| 2013-02-02 | path 174 / row 039 | 33% | **Landsat 7** | SLC-off striping |
| 2013-02-02 | path 174 / row 040 | 21% | **Landsat 7** | SLC-off striping |
| 2013-02-18 | path 174 / row 039 | 0% | **Landsat 7** | SLC-off striping |
| 2013-02-18 | path 174 / row 040 | 5% | **Landsat 7** | SLC-off striping |

**Landsat 8: zero scenes over Aqaba in February 2013.** It launched
2013-02-11 but was still in its ~100-day in-orbit checkout phase and was not
yet acquiring routine science data. **Landsat 8 is not an option for this
event at all** — this corrects the assumption in `tasks/abd.md`.

**What's actually available is Landsat 7**, which has flown with the Scan
Line Corrector failed since 2003 — every scene has ~22% of pixels missing in
widening diagonal stripes toward the scene edges. Whether that gap falls on
the coastline (where the plume signal lives) or clear of it is unverified.

**2013-02-18 is strikingly clean (0–5% cloud)**, but usefulness depends
entirely on the still-unknown exact flood date: a flood plume disperses in
24–72 hours, so if the flood happened near 2013-02-02 (consistent with that
date's elevated cloud, itself possibly storm-related), a scene 16 days later
shows nothing. **Resolving the exact date is now higher-value than before** —
it decides between two structurally different Landsat 7 candidates, not just
a matter of scoring precision.

**Verdict so far: February 2013 is validatable only through Landsat 7 with
SLC-off gaps, if at all, and only once the exact date is known.** If it
happened outside `2013-02-01 – 2013-02-28` reasoning changes entirely. This is
weaker than `abd.md` assumed — worth flagging to the team now rather than at
Day 5, per the escalation principle in `abd.md` §"Why your stream matters."

---

## 3. Go / no-go — FINAL, pixel-level QC complete

**Primary event (Oct 2016): NO-GO for image-based validation.** The only
candidate post-event scene (2016-11-02, +5 days) numerically clears the gate
(cloud, timing) but **fails the visual-plume criterion** — confirmed by two
independent sensors (Sentinel-2 + Landsat 8) and explained by the in-situ
mooring record showing the plume signal had already dispersed 2.5–3.5 days
before either satellite pass (§1a). This is not a weak/marginal result to
grade Silver or Bronze — it's a genuine null: **no plume is present in any
imagery this project can access for this event**, for a real physical reason
(dispersal faster than the revisit gap), not a data-quality problem.

**Backup event (Feb 2013): weaker still.** No Sentinel-2 possible at all
(pre-launch); Landsat 8 unavailable (pre-commissioning); only degraded
Landsat 7 remains, and even that can't be properly scored until the exact
date resolves (§2).

**What this means, concretely, per `abd.md`'s own escalation framing
("different event, a weaker label, or repositioning around forecast
capability"):**

1. **A different event doesn't obviously help.** Feb 2013 is strictly worse
   on sensor availability, and nothing else in the literature so far names a
   third candidate event with better satellite timing.
2. **There is no "weaker label" to fall back to** — Silver/Bronze (§12.4)
   describe a plume that's partially obscured or uncertain, not a plume
   that's provably absent from every accessible scene.
3. **Recommended pivot: use the in-situ mooring record as the validation
   target instead of a satellite-derived mask.** The Kalman et al. (2025)
   mooring 250 m offshore the outlet recorded salinity and turbidity every
   5 minutes through the whole event (§6a) — a quantitative, continuous,
   satellite-independent measurement of exactly what this project wants to
   validate: did sediment-laden water reach the sea, how much, for how long.
   This is arguably a **stronger** validation target than a qualitative
   satellite plume mask would have been, and it already exists — no further
   imagery work unlocks it. Concretely: Nizar's transport model can be
   checked against *measured* salinity drop (−1.75 ‰) and turbidity peak
   (2.18 g/L) at a known point (250 m offshore, 13 m depth) and time
   (turbidity onset 09:50 Oct 28, cleared ~17:15 Oct 29) — a real
   quantitative comparison, not a visual judgment call.
4. **The plume-extraction pipeline itself is still a real deliverable**,
   independent of whether this specific event has a detectable plume — it's
   built, documented, and ready to point at a different scene/event if one
   ever does show a clear signal (e.g., if a future real-time flood is
   caught with better revisit timing).

**This needs to go to the team today**, per `abd.md`'s own instruction that a
bad answer found early leaves time to react — this is that bad answer, found
now rather than at a later demo rehearsal.

**Backup event (Feb 2013): weaker than assumed.** No Sentinel-2 possible at
all; Landsat 8 is not an option (contra the task doc); only degraded Landsat 7
remains, and even that can't be scored until the exact date is known.

**Practical implication:** if Oct 2016 fails visual QC, there currently is
**no strong fallback** — matches the risk `abd.md` §3 warned about ("if
Landsat can't validate [Feb 2013], there is effectively no backup and Oct
2016 has to work"), now with harder evidence behind it.

---

## 4. Blockers

1. ~~Pixel-level access for visual QC~~ — **RESOLVED without needing
   Copernicus Data Space or Earth Engine credentials.** Microsoft Planetary
   Computer (`planetarycomputer.microsoft.com/api/stac/v1`) serves both
   Sentinel-2 L2A and Landsat C2 L2 pixels publicly, anonymous SAS-token
   signing via `pip install planetary-computer`. `.env`'s `CDSE_*` /
   `EARTHENGINE_PROJECT` placeholders are no longer blocking this workstream
   — see §1a. (Still worth registering for real if another workstream needs
   Copernicus Data Space specifically, e.g. Copernicus Marine for Nizar.)
2. **Still open: Katz et al. (2015) full text**, for the exact February 2013
   date. Needed from someone with journal access (or the original authors).
   Until then, the February event stays a whole-month coarse scan rather
   than a scored ±10-day window, and its Landsat 7 candidate stays
   unresolved between two structurally different dates (§2).
3. **Still open: site-photo provenance** (§6c) — capture date/location
   unconfirmed, EXIF stripped.

---

## 6. New source material collected on-site (2026-08-02)

Three items filed under `data/raw/`:

### a. Kalman et al. (2025) — full text with tracked changes

`data/raw/literature/kalman_et_al_2025_fulltext_ATC1.pdf` — the actual paper behind
`docs/event_dates.md`'s Oct 2016 numbers, not just the abstract. Cross-checked
against what's already recorded here: sediment mass (paper: "2.44 × 10⁴ tons" ≈
24,400 t), flood arrival (paper: "~3:00 am October 28th"), and rainfall timing all
match what's already in `docs/event_dates.md`. No contradiction found.

**The real find: an independent, quantitative marine validation dataset that isn't
satellite imagery at all.** The paper's mooring station — anchored 250 m offshore
the Kinnet Canal outlet at 13 m depth — recorded salinity and turbidity (OBS 3+
sensors) at 5-minute intervals through the whole flood. Reported numbers:

- Salinity dropped to **38.75 ‰**, ~1.75 ‰ below the 9-month background mean
  (40.53 ‰) — 19× the background standard deviation.
- Turbidity peaked at **2.18 g/L** suspended sediment near the seafloor.
- Elevated turbidity lasted **~31 hours**, from 09:50 Oct 28 to ~17:15 Oct 29.
- The plume alternated between **hypopycnal (surface) and hyperpycnal (bottom)**
  transport — bottom-water density calculations (their Fig. 8c) show it crossed
  into hyperpycnal (denser-than-seawater, plunges to the seafloor) territory for
  part of the event.

This is a **second, independent go/no-go signal for the same Oct 28 2016 event** —
one that doesn't depend on cloud cover or satellite revisit timing at all. It also
gives Nizar an actual measured plume-arrival timeline (turbidity/salinity anomaly
starting 09:50 Oct 28, not just the witness-reported 03:00 arrival) to calibrate
against, independent of whatever the Sentinel-2 scene shows. Coordinates for the
mooring itself aren't given as decimal lat/lon in the text — only "~250 m offshore
the Kinnet Canal outlet, 13 m depth."

**Still doesn't resolve Feb 2013.** This paper only reports the 2016 event; it
repeats the same 21,000 t figure for Feb 2013 (citing Katz et al. 2015) with no
date, same as before.

### b. Levenson (2020) MSc thesis — Satellite-Derived Bathymetry methodology

`data/raw/literature/levenson_2020_sdb_thesis.pdf` — Hebrew University thesis,
supervised by Amotz Agnon, on automating shallow-water bathymetry from Landsat 8.
**One of its four study areas is the Gulf of Eilat/Aqaba itself** (path 174, row
40). Two things transfer directly to this task:

1. **Otsu's method for automatic land/water thresholding** on the SWIR band —
   exactly the kind of "derive your own water mask from the imagery" approach
   `tasks/abd.md` assigns here (there for Landsat SWIR, here for Sentinel-2 SCL).
   Worth a look if the SCL-based mask needs a cross-check.
2. **A possible bathymetry lead for Mahdi/Pulga, not Abd** — the thesis cites
   "Hall, J.K. & Levenson, S. (2017), *Compilation of a 100 m bathymetric grid for
   the Arabian Plate; Red Sea, Arabian and Oman Seas and Persian Gulf*" as its
   depth ground-truth source. `docs/data_dictionary.md` §5 documents that the
   project substituted GMRT for GEBCO because every scripted GEBCO download route
   is closed. This Hall & Levenson grid is a named, citable 100 m compilation
   that might be a better-provenance stand-in than GMRT — flagged for Pulga/Mahdi,
   not pursued further here since it's outside this workstream.

### c. Site photos — Kinnet Canal outlet

`data/raw/photos/kinnet_canal_site/` — 14 images (`imag1.jpg`–`imag14.jpg`,
`image7.jpg`), showing a three-barrel concrete culvert discharging into a narrow
channel that widens into open water, banks with algae and litter, and calm,
non-turbid conditions throughout.

**⚠️ Provenance unconfirmed — do not cite as evidence yet.** EXIF metadata (GPS,
capture date, camera model) was stripped from every file; only the download
timestamp survives. Before these go into `docs/data_dictionary.md` or get used to
anchor the outlet location:
- Confirm these are actually the Kinnet Canal outlet (the three-barrel culvert
  matches the kind of structure Mahdi's team is locating, but that's an inference,
  not a confirmed ID).
- Get the capture date — needed to know if this is baseline (pre/post-event, calm
  water) or something else.
- If available, get the coordinates the drone was flown at, even approximately —
  this could cross-check Mahdi's Day-4 outlet coordinate deliverable independently.

If confirmed, this becomes a genuinely useful **baseline reference set**: knowing
what calm, non-flood conditions look like right at the outlet strengthens the
"is a plume really visible and distinguishable from normal" judgment call the
gate criteria in §1 requires.

## 7. Remaining open items

- [x] ~~Pull SCL band, compute AOI-water cloud %~~ — done, §1a (0.07%).
- [x] ~~Pull true-color visual asset, confirm plume visibility~~ — done, §1a
      (no plume, two independent sensors).
- [x] ~~Pull 5–10 clear pre-event scenes, build baseline composite~~ — done,
      §1b (8 scenes).
- [x] ~~Build the plume-extraction pipeline~~ — done, §1c
      (`backend/src/models/plume_segmentation.py`,
      `scripts/run_plume_extraction.py`, `notebooks/03_plume_extraction.ipynb`).
- [x] ~~Final go/no-go~~ — done, §3: **NO-GO**, escalated in this file.
- [ ] **Feb 2013 exact date** — confirmed unreachable through free/legitimate
      channels (ScienceDirect 403, academia.edu blocked, ADS empty, OpenAlex
      confirms zero open-access copies exist anywhere). Needs a teammate with
      institutional/journal access, or direct contact with the authors.
      Once resolved: re-run the Landsat search as a proper ±10-day window
      instead of a whole-month scan, and check the SLC-off gap position
      against the coastline.
- [ ] **Site-photo provenance** (§6c) — capture date/location unconfirmed.
- [ ] **Team decision needed**: which pivot from §3 to take (mooring record as
      Nizar's validation target is the recommendation) — this is a
      product/demo-scope call for the whole team, not something to decide
      unilaterally from this file.
