# Mahdi — Terrain, Hydrology, the Runoff Model, and Four New AI Features

**Phase 5 · Workstream 2**
**Feeds:** Ali (dashboards for B1/B2/B3/B9), Pulga (B4/B8/B9 cross-deps), Nizar (B6)
Read [`00-phase5-plan.md`](00-phase5-plan.md) first.

---

## Why this phase matters

You carry the heaviest Part B load this phase — four owned features (B1, B2, B3, B9)
plus support on B6 and B8 — on top of one genuinely urgent Part A item. Do the urgent
one first. Everything else on this list can slip a day; a live credential exposure
cannot.

---

## 0 · Close your Phase 2 items — Day 0, before anything else

- [ ] **A2.3 — rotate the `.env` credentials. This is today's first task, not a
      cleanup item.** `.env` with real team credentials was committed on 1 Aug
      (`2f0a6d6`, "add .env with team credentials", reachable from `main`) and later
      removed from the tip (`bf5f894`) **without a history rewrite**. Anyone with
      clone access to this repo can still retrieve those exact credentials from git
      history today, regardless of the current `.gitignore` being correct. Rotate
      every credential that file ever held — NASA Earthdata, Copernicus CDS,
      Copernicus Data Space, Copernicus Marine, Supabase, anything else — and confirm
      the *old* values now fail. `.gitignore` being correct today does not undo this;
      only rotation does.
- [x] **A2.1 — `docs/model_card.md` is complete and in the RAG corpus.** Confirmed:
      629 lines, 20+ real sections, listed in `backend/src/rag/corpus.py`'s
      `CORPUS_FILES` allowlist. No action needed — verify it's still true after
      anything below touches it.
- [x] **A2.2 — standalone temporal-holdout metric recorded.** Confirmed in
      `data/models/model_versions.jsonl` row 3: `temporal_holdout_AP: 0.5923`, full
      split metadata (`cutoff_year: 2015`, 6,300/5,510 rows), matches
      `docs/model_card.md` exactly. No action needed.
- [x] **A2.4 — culvert cross-check / `position_confidence` / `AQ-O04` caveat live.**
      Confirmed wired end to end: `schemas.py`'s typed `Literal`,
      `data_access.py::outlets()`, the live `/outlets` route,
      `particle_engine.py::HarbourBasinReleaseError`, `caveats.py::harbour_outlet()`.
      No action needed.
- [ ] **A2.5 — `docker compose up` with wifi physically off.** The automated proxy
      (`frontend/tests/wifi-off.offline.spec.ts`) exists and is well-targeted, but
      whether it has ever actually been run and passed is unconfirmed — its own
      comment says the real gate is the manual, physical run. Do that run yourself
      once this phase's Docker-relevant changes (B1/B9's new model artifacts) land,
      not before.

---

## 1 · B1 — Automated Plume Segmentation Model (with Abd)

**Model & data**

- [ ] U-Net or a lightweight segmentation model, trained on the accumulated labelled
      plume-mask library.
- [ ] Create `data/processed/plume/masks/` with a **fixed schema now**, before the
      first mask is added — retrofitting a schema after masks exist is expensive,
      defining one before costs nothing.
- [ ] Every mask stores `human_reviewed: bool` and, once reviewed, an
      `agreement_score` against the human correction — this is the training signal,
      not an afterthought field.

**Backend & storage**

- [ ] New model-serving path parallel to the runoff classifier's, with its own row in
      `model_versions.jsonl` (same file, new `component: "plume_segmentation"` value —
      do not create a second ledger).
- [ ] Confidence output per generated mask, stored alongside it.

**Dashboard sub-features (Ali builds — full spec also in [`06-ali.md`](06-ali.md))**

- Confidence heatmap toggle directly on the plume layer.
- "Flag for human review" action on any auto-generated mask, feeding straight back
  into the training set.
- A running counter in the Provenance Panel: "X of Y plume masks now auto-segmented, Z
  still manual" — visibly improving over time, never silently hiding the manual count.
- Directly upgrades **Storm Replay Mode** (feature 1): once wired, replay shows a real
  plume shape for any past event, not just the flagship demo.

**Limitation to state on the same screen this ships on:** the training set is
whatever masks have accumulated so far — almost certainly one digit's worth of events.
A model trained on a handful of masks is a first pass, not a validated segmenter. Say
that in `docs/model_card.md`'s new B1 section, in the same words, not softened.

---

## 2 · B2 — Learned Transmission-Loss Model

**Model & data**

- [ ] Regression model predicting per-catchment transmission loss from terrain slope,
      soil texture (Pulga's clay/sand/silt extraction), and drainage density.
- [ ] Replaces the borrowed Negev `[0.20, 0.85]` range (`docs/HANDOFF_transmission_loss_2026-08-06.md`)
      with a site-specific learned estimate — **the borrowed range does not disappear**,
      it becomes the fallback when the learned model has nothing to say.

**Backend & storage**

- [ ] New field on the sediment-proxy response: `transmission_loss_basis: "learned" |
      "negev_proxy"` — the response is always honest about which value is in use.
      This slots next to the `transmission_loss` field Pulga's
      `transmission_loss_override` parameter already echoes back
      (`backend/src/api/schemas.py`) — add the basis flag there, don't invent a
      parallel field.
- [ ] Feeds directly into the exposure engine's `formula_terms`, per Standing Law
      rule 10 — the basis flag travels with the number, not just in a log.

**Dashboard sub-features (Ali builds)**

- The existing transmission-loss slider's default position moves to the learned
  prediction instead of a blank midpoint.
- A tooltip showing the top features driving that specific catchment's prediction —
  same SHAP-style pattern the runoff model's driver list already uses
  (`DriverBars.tsx`, `frontend/src/components/`).
- A comparison chart: "this catchment's predicted loss vs. the old Negev proxy range"
  — visually shows the honesty caveat narrowing.

**Limitation to state, explicitly, in `docs/pitch_limitations.md` — this closes R1
("biggest unmodelled scientific gap") but do not let it read as "now solved":** a
learned model trained on this project's thin local data is not automatically more
trustworthy than a wide, borrowed proxy range. State both the win (site-specific,
not a Negev import) and the honest cost (validated on very few real events) on the
same slide.

---

## 3 · B3 — Cross-Site Transfer Learning (with Karam)

**Model & data**

- [ ] Pre-train on Aqaba's validated model, fine-tune on a new site's thin data.
- [ ] Formalize the fine-tuning pipeline as a **reusable script**, not a one-off
      notebook — Karam is generalizing the rainfall ingestion side (his file, §"Your
      role in B3") specifically so this script never special-cases input format per
      site.

**Backend & storage**

- [ ] `site_id` dimension added to `model_versions.jsonl`, so multiple sites' models
      coexist with clean lineage. **Do not repurpose any existing ID scheme for
      this** — `AQ-C`/`AQ-O`/`R-`/`AQ-YYYY-MM-DD`/`sim_{ULID}` are Aqaba-specific and
      frozen (`tasks/00-contracts.md` §2); `site_id` is a new, separate field.

**Dashboard sub-features (Ali builds)**

- A "model maturity" badge per site — number of validated local events vs. Aqaba's
  baseline, shown honestly, never hidden or smoothed over.
- Powers a future multi-site switcher in the map UI: same dashboard, different
  coastline, with an honest "this site has N validated events, Aqaba has M"
  comparison built directly into the switch action.
- Directly supports B4: a newly-scored candidate site (Pulga's site-scoring agent)
  gets a transfer-learned starter model immediately instead of starting from zero.

**Limitation to state:** a site with zero validated local events cannot be
meaningfully scored against Aqaba's own accuracy — the maturity badge exists
specifically so nobody mistakes "we ran the model on it" for "we validated it here."

---

## 4 · B9 — Automated Culvert/Drainage-Conflict Detector (with Pulga)

**Model & data**

- [ ] Formalizes the existing manual OSM-vs-DEM cross-check
      (`docs/osm_dem_conflicts.md`) into a reusable, automatic detector — trained or
      rule-based on the pattern that already found **27 real culverts**. Start
      rule-based (the pattern is already known and documented); only reach for a
      trained model if the rule-based version demonstrably misses cases the manual
      check caught.

**Backend & storage**

- [ ] Runs automatically on every new site port (ties directly into B3's transfer
      pipeline — a new site's outlets get their own conflict report as part of
      onboarding, not a separate manual task someone has to remember to run), producing
      a conflict report as a structured artifact instead of a one-off manual task.
- [ ] All distance/proximity math in this detector is **EPSG:32636, never degrees**
      (Standing Law rule 8) — this is exactly the kind of "how close is this culvert
      to this outlet" calculation that silently produces a wrong number in degrees.

**Dashboard sub-features (Ali builds)**

- A map layer showing detected conflicts as clickable pins.
- DEM-vs-OSM shown side by side on click.
- Directly feeds `outlet.position_confidence` — currently three of five outlets are
  marked `"low"` (per A2.4's live-verified field) — this is the mechanism that
  improves that number with evidence instead of a manual guess. **Improves it
  toward a new value with evidence attached, never silently flips `"low"` to
  `"high"` without the evidence being inspectable** — same non-negotiable pattern as
  B8's `sensitivity_weight` safeguard below.

**Limitation to state:** the detector is trained/tuned on one coastline's known
culvert pattern (27 real hits). Its false-positive/false-negative rate on a genuinely
different terrain (a new B3 site) is unknown until tested there — say this before
running it on a second site, not after.

---

## 5 · Your role in B6 — Live Anomaly Detection (primary: Nizar, [`03-nizar.md`](03-nizar.md))

Nizar owns the detector and the `forecast_anomalies` table. What he needs from you:

- [ ] Confirm which catchment-climatology artifact (per Karam's A1.3 resolution) is
      the correct baseline for "what's normal" — the anomaly detector is only honest
      if its baseline is the same real climatology the rest of the project already
      uses, not a second, independently-computed one.

---

## 6 · Your role in B8 — Coral Health Vision Model, the CV pipeline (primary: Pulga, [`04-pulga.md`](04-pulga.md))

Pulga owns the backend/storage/dashboard for this feature. Your specific piece is the
CV classifier itself.

- [ ] Build the CNN classifying diver-uploaded reef photos into health states
      (healthy/stressed/bleached).
- [ ] **The non-negotiable design requirement, stated here in writing, not just
      implied:** accumulated photo classifications per zone may **propose** a
      `sensitivity_weight` update, flagged explicitly for marine-scientist review.
      They must **never silently overwrite the placeholder**
      (`sensitivity_weight = 1.0`, `PLACEHOLDER_PENDING_MARINE_SCIENTIST`,
      `tasks/00-contracts.md` §5 swap-in #5, still open). Automating the
      evidence-gathering is good; automating the final judgement call is exactly the
      failure mode Standing Law rule 13 exists to prevent.

---

## 7 · Continue the 3D Aqaba Journey ([`mahdi-3D-implementation-plan.md`](../../mahdi-3D-implementation-plan.md)) — yours end to end

This is your feature this phase, full stack — terrain, buildings, water, camera,
QA — not a shared item split across teammates. Work straight down the plan's own
section order:

- [ ] **§3.1 — fetch the DEM. It is not currently on disk.** Run `scripts/03_dem_fetch.py`;
      confirm the output lands at `data/processed/dem/dem_utm36n.tif`. This is the plan's
      literal first task, not an assumption to build on top of.
- [ ] Confirm the fetched DEM's bounding box matches `TERRAIN_AOI` — import it from
      `backend.src.config.spatial`, never retype the literal (`tests/test_spatial_contract.py`
      enforces this for existing modules; hold any new script to the same rule).
- [ ] Apply the documented nodata gotcha: GLO-30 encodes sea as exactly `0.0` — set nodata
      explicitly, or reprojection welds the raster frame onto the coastline (this already
      cost the project 1,080 km² of phantom "sea" once).
- [ ] **§3.1 — merge the fetched DEM with the already-verified `depth_utm36n.tif`
      bathymetry into one continuous elevation surface** (land positive, sea negative,
      coastline geometry as the seam) — this is the surface the plan's Terrain-RGB tile
      set encodes. Reproject through EPSG:32636 for the merge math, never degrees, then
      back to EPSG:4326/Web Mercator for tiling.
- [ ] State the 30 m (DEM) / 50 m (bathymetry) resolution caveat explicitly wherever this
      surface is documented — don't silently upsample and imply false detail.
- [ ] Render a quick elevation-shaded top-down comparison against reference photos 1, 3,
      8 and save it to `docs/3d_journey/qa/screenshots/`, per the plan's own QA protocol
      (§6).
- [ ] **§3.2 — filter the buildings layer and apply the documented height rule**
      (`building_height_rules.json`), Aqaba Fort and Ayla Lagoon special-cased.
- [ ] **§3.3 — reuse `depth_utm36n.tif` and `coastline.gpkg` directly**; cross-check the
      coastline against reference photo 1 (does it correctly narrow from the wide
      Eilat/Aqaba bay down to the narrower southern stretch in photo 8?).
- [ ] **§3.4 — reuse `reef_zones.gpkg` (`R-01`…`R-08`)** as the marine leg and terminal
      point.
- [ ] **§4 — build the camera waypoint script** from the plan's verified real coordinates
      (reef-zone centroids, `outlets.geojson`), geocoding the remaining landmark rows in
      §2a before locking them in.
- [ ] **§6 — run the full QA protocol**, all 8 photo comparisons saved with captions.
- [ ] **§7 — fold the limitations into `docs/pitch_limitations.md`.**

**Limitation to state, same as everywhere else in the plan:** the merged terrain surface
combines two already-caveated products (30 m DEM, 50 m bathymetry) — the merge doesn't
improve either one's resolution, and close-up steep terrain or reef-scale seafloor detail
still won't resolve. Building heights are estimated for 99.7%+ of the corridor, per §0.4.

---

## Definition of done

1. A2.3 — every credential ever held in the committed `.env` is rotated and the old
   values confirmed dead.
2. A2.5 — the physical wifi-off run has been done this phase, not just the automated
   spec existing.
3. B1 — segmentation model live-serving with per-mask confidence and a `model_versions`
   row; the "still manual" count is visible, not hidden.
4. B2 — `transmission_loss_basis` distinguishes learned vs. Negev-proxy on every
   response; `docs/pitch_limitations.md` states both the win and the honest cost.
5. B3 — fine-tuning pipeline runs against at least one real second-site bounding box;
   the maturity badge shows a real, non-zero validated-event count comparison.
6. B9 — conflict detector runs automatically on a new site port; `position_confidence`
   updates carry inspectable evidence, never a silent flip.
7. B6/B8 support items handed off with the artifacts named in the tables below.

---

## Handoffs

| Teammate | What they get | When |
|---|---|---|
| **Ali** | B1 confidence/review-flag API, B2 basis flag + SHAP-style feature endpoint, B3 maturity-badge data, B9 conflict-pin GeoJSON | Day 4 |
| **Pulga** | B9's outlet-side conflict detector output (feeds his B4 site-scoring agent's terrain criteria); B8's CV classifier endpoint | Day 3–4 |
| **Nizar** | Confirmation of which climatology artifact is B6's correct baseline | Day 2 |

## What you depend on

| From | What | Blocked? |
|---|---|---|
| **Karam** | Generalized rainfall ingestion pipeline + one test bounding box (B3) | Yes, partly — start the fine-tuning script's structure now, plug in his pipeline when it lands Day 3 |
| **Karam** | Confirmed climatology artifact (A1.3), for B6's baseline | No — proceed with the existing 5-row summary, swap if a daily series is confirmed (Day 2) |
| **Pulga** | B8's photo-upload endpoint and storage schema, before the CV classifier has anywhere real to write its output | Yes — build/train the classifier against local test images first, wire to his endpoint once it exists (Day 3) |
| **Nizar** | Confirmation of whether the HYCOM cache re-fetch (A4.2) also unblocks B1's plume-forcing placeholder | No — B1's own training/serving work doesn't depend on this; only the dashboard's forcing caveat text does (Day 2) |
| **Abd** | Real plume-mask count and schema confirmation for B1 | Yes, partly — architecture work proceeds either way; the dashboard's "X of Y masks" copy waits on this number (Day 2) |
