# Event Audit — Satellite Imagery for Plume Validation

**Owner:** Abd · **Project:** ReefShield Aqaba · **Workstream:** B (Remote Sensing)

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

**Preliminary read:** 2016-11-02 numerically clears the gate (§1 of `abd.md`:
within ~5 days, <20% cloud) on scene-level metadata alone. This is the
strongest lead in the project for the demo event.

**Why this is preliminary, not a verdict:** scene-level cloud % is explicitly
*not* the metric the gate requires — it includes land, and can hide a locally
clouded AOI even at a low scene average (or vice versa). Plume visibility and
sun glint have not been checked at all; both require actually looking at the
scene. See §4.

**Product IDs** (for reproducibility, Copernicus Data Space `Id`):
- `S2A_MSIL2A_20161102T082112_N0500_R121_T36RYT_20231026T122456` — id
  `6ea1d505-8d0a-4bc4-aa28-2e0ce64e8b26`
- `S2A_MSIL2A_20161102T082112_N0500_R121_T36RXT_20231026T122456` — id
  `bc4a6f07-9dcb-4408-875e-e36fdc01607c`

**Baseline composite note:** the pre-event scene in-window (2016-10-23) is
unusable, so the 5–10 clear pre-event scenes for the baseline composite must
be pulled from further back (outside the ±10-day gate window — that window is
only for the post-event gate check, not the baseline). Not yet done.

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

## 3. Go / no-go — preliminary

**Primary event (Oct 2016): promising, not yet confirmed.** 2016-11-02
clears the numeric gate on scene metadata. Visual QC required before calling
it Gold/Silver/Bronze (§12.4).

**Backup event (Feb 2013): weaker than assumed.** No Sentinel-2 possible at
all; Landsat 8 is not an option (contra the task doc); only degraded Landsat 7
remains, and even that can't be scored until the exact date is known.

**Practical implication:** if Oct 2016 fails visual QC, there currently is
**no strong fallback** — matches the risk `abd.md` §3 warned about ("if
Landsat can't validate [Feb 2013], there is effectively no backup and Oct
2016 has to work"), now with harder evidence behind it.

---

## 4. Blockers — need input to proceed

1. **Pixel-level access for visual QC.** Metadata search is anonymous, but
   downloading actual bands/thumbnails (to compute AOI-water-specific cloud %,
   check sun glint, and confirm the plume is visible) requires a real
   Copernicus Data Space login. `.env` currently holds only placeholder values
   for `CDSE_USERNAME` / `CDSE_PASSWORD` (2 characters each — not real
   credentials). Registration: https://dataspace.copernicus.eu/. Google Earth
   Engine (`EARTHENGINE_PROJECT` also a placeholder) is an alternative fast
   path per `tasks/abd.md` §"Before you start," but needs the shared GEE
   project Mahdi's task list assigns him to create — not yet visible as
   configured either.
2. **Katz et al. (2015) full text**, for the exact February 2013 date. Needed
   from someone with journal access (or the original authors). Until then,
   the February event stays a whole-month coarse scan rather than a scored
   ±10-day window.

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

## 7. Next steps once unblocked

- [ ] Pull SCL band for the two 2016-11-02 tiles, clip to AOI, compute cloud %
      over the water mask specifically (not scene-level).
- [ ] Pull true-color visual asset for 2016-11-02 and confirm a plume is
      visible and glint is tolerable.
- [ ] If 2016-11-02 passes: pull 5–10 clear pre-event Sentinel-2 scenes
      (outside the Oct 2016 gate window) for the baseline composite.
- [ ] Once the Feb 2013 date resolves: re-run the Landsat search as a proper
      ±10-day window instead of a whole-month scan, and check the SLC-off gap
      position against the coastline.
- [ ] Escalate this file's verdicts to the team the same day either is
      confirmed — this is the Day-2 gate `abd.md` describes.
