# Abd — Satellite Imagery & Plume Detection

**Project:** ReefShield Aqaba
**Workstream:** B (Remote Sensing)
**Feeds:** Component E (satellite plume detection) → all validation and backtesting
**Window:** Day 5 imagery audit, Day 6 plume mask

---

## Why your stream matters — read this first

**You own the project's gating risk.** The concept doc's Final Recommendation makes the entire idea conditional on a single question:

> Within the first two days, confirm that at least one historical event has suitable rainfall data and a sufficiently clear post-event Sentinel-2, HLS, or Landsat image for plume validation.

Your Day-5 audit **is** that gate. Everything else in the project can be built beautifully and still have no validation story if no usable scene exists.

Two consequences:
1. **Report the answer to the whole team the day you know it** — good or bad. A bad answer found on Day 5 means the team changes demo event. A bad answer found on Day 12 means there's no demo.
2. **Search before you download.** Audit many events cheaply in a browser first. Only pull pixels for the event you commit to.

---

## Before you start

- [ ] **AOI bounding box frozen** (Mahdi commits `data/aoi/aqaba_aoi.geojson`).
- [ ] **Get the event dates yourself on Day 1 — do not wait for Karam.** The two candidates are already named in the concept doc: **October 2016** and **February 2013**. Exact dates are in the literature, not in IMERG:
  - Ginat et al. 2025 — https://nhess.copernicus.org/articles/25/3201/2025/index.html
  - Katz et al. 2015 — https://www.sciencedirect.com/science/article/pii/S0012821X15001119

  Write them to `docs/event_dates.md`. **This is the single most important decoupling in the project** — it moves your gate from Day 5 to Day 2, so a bad answer leaves eleven days to react instead of nine. See [`00-contracts.md`](00-contracts.md) §4 P3.
- [ ] **Copernicus Data Space account** registered.
- [ ] **Google Earth Engine access** — the fast path for experimentation.
- [ ] **NASA Earthdata account** — needed for HLS and Landsat.
- [ ] **Outlet coordinates from Mahdi** (Day 4) — so you can check whether the observed plume actually emerges where the model says it should.

### Environment

```bash
pip install rasterio rioxarray xarray numpy geopandas earthengine-api
pip install pystac-client odc-stac   # if you go the STAC route
```

---

## 1. Sentinel-2 L2A — your primary imagery

**Role:** observed plume extraction, pre-event baseline composite, validation ground truth
**Resolution:** 10 m / 20 m / 60 m bands
**Registration:** Copernicus Data Space (+ Earth Engine as fast path)

**Links**
- https://documentation.dataspace.copernicus.eu/Data/SentinelMissions/Sentinel2.html
- https://browser.dataspace.copernicus.eu/
- https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2_SR_HARMONIZED

**Bands you need:** B2 (blue), B3 (green), B4 (red), B8 (NIR), B11, B12, plus **SCL** (scene classification, for cloud and water masking)

### The audit — do this before anything else

- [ ] For each candidate event from Karam, list every Sentinel-2 scene within **±10 days**.
- [ ] Open each one in the Copernicus Browser and **look at it**. This step is visual, not scripted.
- [ ] Score each scene on:
  - cloud % **over the AOI water specifically** (not the scene-level metadata figure — that includes land and is useless here)
  - sun glint severity
  - whether a plume is visible at all
  - days elapsed since the event
- [ ] Record every event × scene combination examined in `docs/event_audit.md`, including the ones that failed.

**The gate — acceptance criteria:** at least one event has a post-event scene **within ~5 days**, under **~20% cloud over the AOI water**, with a **visually distinguishable plume**.

If nothing passes: escalate to the team the same day. Options are then a different event, accepting a weaker Silver/Bronze-quality label (§12.4), or repositioning the demo around forecast capability rather than historical validation.

### Then, for the chosen event

- [ ] Pull the post-event scene.
- [ ] Pull **5–10 clear pre-event scenes** for the baseline composite.
- [ ] Verify the pre-event scenes are genuinely calm-water conditions, not other turbidity events.

**Deliverables**
- `data/raw/sentinel2/`
- `docs/event_audit.md` — the scored table

**Watch out:** revisit is ~5 days (2–3 with both S2A and S2B), but a flood plume can disperse in **24–72 hours**. There is real timing luck involved, and that's exactly why you audit several events rather than betting on one.

---

## 2. NASA HLS (Harmonized Landsat Sentinel-2)

**Role:** extra revisits to fill Sentinel-2 gaps
**Resolution:** 30 m
**Registration:** NASA Earthdata or Earth Engine

**Links**
- https://hls.gsfc.nasa.gov/
- https://hls.gsfc.nasa.gov/data-access-and-tools/
- https://developers.google.com/earth-engine/datasets/catalog/NASA_HLS_HLSS30_v002

**Tasks**
- [ ] Query HLSS30 and HLSL30 v2.0 over the same event windows.
- [ ] Fill any date where Sentinel-2 was cloudy but Landsat was not.
- [ ] Add the extra rows to `docs/event_audit.md`.

**Why this matters more than it looks:** HLS adds the Landsat overpasses to your effective revisit rate, roughly doubling your chance of catching the plume in its first 72 hours. This is often what turns a near-miss into a usable observation — don't treat it as optional.

**Watch out:** 30 m means plume *edges* are coarser than Sentinel-2's 10 m. Fine for area and centroid metrics, weaker for detailed shape comparison.

---

## 3. Landsat 8/9 Level-2 — backup scenes

**Role:** the only optical option for the February 2013 event
**Registration:** NASA Earthdata

**Link**
- https://search.earthdata.nasa.gov/

**Tasks**
- [ ] Check native Landsat 8 L2 coverage for the Feb 2013 event window.
- [ ] Deliver a clear verdict: **is Feb 2013 validatable at all?**

**Flag this early.** Sentinel-2A launched in 2015, so the Feb 2013 event has **no Sentinel-2 coverage whatsoever** — only Landsat 8 (launched Feb 2013, so even that is marginal and early-mission). The team currently treats Feb 2013 as the backup event; if Landsat can't validate it, **there is effectively no backup** and Oct 2016 has to work. That's important information for everyone's risk planning, and it's better known on Day 5 than Day 12.

---

## 4. Copernicus Marine ocean-colour guidance — method reference

**Role:** how to derive turbidity / suspended matter from Sentinel-2 high-resolution products
**Registration:** none

**Link**
- https://help.marine.copernicus.eu/en/articles/5194057-introduction-to-ocean-colour-sentinel-2-high-resolution-products

**Tasks**
- [ ] Read the guidance and shortlist candidate spectral approaches.
- [ ] Implement and compare on the demo scene:
  - NDSSI (Normalized Difference Suspended Sediment Index)
  - NSMI (Normalized Suspended Material Index)
  - red/green band ratios
  - a plain multi-date reflectance anomaly against the baseline composite
- [ ] Pick **one** primary index, document why, include a side-by-side figure.

### Your pipeline order (from §10.5)

```text
1. Build a cloud-free pre-event baseline composite
2. Apply the water mask
3. Calculate spectral features
4. Detect the post-event anomaly
5. Remove glint, cloud, and land-edge artifacts
6. Convert anomaly → plume-probability raster
7. Manually review the final mask for the demo event
```

**Deliverables**
- `notebooks/03_plume_extraction.ipynb`
- `backend/src/models/plume_segmentation.py`
- observed plume mask as **both** raster probability and vector polygon

**Watch out — resist the deep-learning instinct.** The concept doc (§10.5) is explicit: do **not** start with a U-Net. The Aqaba-specific labeled set will be tiny, and a spectral anomaly + manual QC approach is what can actually be validated and explained in two weeks. A U-Net trained on a handful of masks would look sophisticated and mean nothing. Segmentation models are a Phase 2 item once enough labeled plumes exist.

**Step 5 is where the real work is.** Sun glint on water and the land-water edge both produce bright anomalies that look exactly like sediment. Budget most of your time here, not on index selection. Manual QC of the final mask isn't a shortcut — the doc treats it as the method.

---

## Definition of done

1. **`docs/event_audit.md`** — every candidate event × scene scored, including failures, with a clear **go / no-go** on the demo event.
2. **Cloud-free pre-event baseline composite** for the chosen event.
3. **Manually QC'd observed plume mask**, as raster probability *and* vector polygon.
4. **Documented choice of spectral index** with a comparison figure.
5. **Verdict on Feb 2013 validatability.**
6. **Every scene ID and product version** in `docs/data_dictionary.md` — the backtest is only reproducible if the exact scenes are recorded.

**Target files**
```text
data/raw/sentinel2/
data/raw/hls/
data/processed/plume/baseline_composite.tif
data/processed/plume/observed_plume_probability.tif
data/processed/vectors/observed_plume.gpkg
docs/event_audit.md
notebooks/03_plume_extraction.ipynb
backend/src/models/plume_segmentation.py
```

**Label quality levels** (§12.4) — grade your mask honestly:
- **Gold:** clear plume, low cloud, known event time, reliable baseline
- **Silver:** partial cloud or moderate glint, uncertain edges, approximate timing
- **Bronze:** weak signal, uncertain outlet — exploration only, never final evaluation

---

## Handoffs — non-blocking

| Teammate | What they get from you | Are they blocked? |
|---|---|---|
| **Everyone** | the go/no-go on the demo event | **This one is real** — but now answered Day 2, not Day 5 |
| **Nizar** | observed plume mask, the calibration target | **No** — he built the parameter search against a synthetic mask; yours is a file swap |
| **Backtest** | observed mask for IoU / Dice / centroid metrics | Metric code is written and tested early against synthetic masks |

**Your go/no-go is the one genuine dependency left in the project**, which is exactly why it moved to Day 2. Announce it the moment you know — a bad answer with eleven days left is a manageable problem.

## What you depend on

| From | What | Blocked? |
|---|---|---|
| **Karam** | event dates | **No** — you took them from the papers yourself on Day 1 |
| **Mahdi** | outlet coordinates | **No** — provisional ones from Day 1; and the audit doesn't need them at all |
| **Pulga** | water mask | **No** — derive your own from Sentinel-2's SCL band |
| **Contract** | the padded download box | Available Day 1 |

**Start Day 1.** Register the accounts, read the two papers for the dates, and open the Copernicus Browser. The audit is your only priority until the gate is answered.
