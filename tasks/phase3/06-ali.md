# Ali — Phase 3

Read [`00-phase3-plan.md`](00-phase3-plan.md) first.

> **Update, 5 Aug — done for you, while you were away from this repo:** items 3
> (plume-prediction image) and half of 4/§5 (exposure + alerts on screen) below.
> Two commits on `main`: `66e39d1` (a CORS fix you'd have hit the moment you tried
> this yourself — the fixed `allow_origins` list didn't cover a non-5173 dev port)
> and `2eb7a47` (the actual wiring). **Pull before you touch `SideRail.tsx`,
> `RiskCard.tsx` or `api/types.ts`** — all three changed.
>
> What landed: `src/api/live.ts` + `useLiveExposure` (a hook separate from
> `useEventData` on purpose — no fixture fallback exists for these three, so a
> slow/down API must not block the rest of the page), the reef-zone rows in
> `SideRail` now show the real exposure band, a new Alerts section, and
> `PlumeMapPanel.tsx` rendering `GET /api/v1/plume/map` with a frame stepper and
> the `plume_source` badge. `fixtures` → `http` for
> `catchments`/`outlets`/`reefZones` in `client.ts`/`http.ts` is **still
> untouched** — I stayed out of that one deliberately, since it's the thing you'd
> most plausibly be mid-edit on. Verified live (API up and down, both languages,
> both themes) before pushing, not just typechecked — see the commit messages for
> what that caught.

**You are much further along than the plan assumed.** I installed and ran your app on
4 Aug: typecheck clean, build in 522 ms, 14 tests passing, serves 200. Every feature on the
Phase 2 list exists — map, time slider, mode switch, layer toggles, legend, risk cards,
driver bars, confidence meter, hyetograph, validation/provenance/limitations panels,
assistant, scenario drawer, bilingual with RTL.

Two calls of yours I want to name because they were right and I got them wrong:

- **Your basemap export had to be committed** — the compose build context is `./frontend`,
  so nothing under `data/` is reachable at image-build time, and DoD item 9 needs the layers
  *in the image*. I had written a parallel exporter of my own; I deleted it
  and closed OPEN-ISSUES #22. Yours is also bilingual — `places.geojson` carries
  `name_ar`/`name_en` — which mine was not.
- **The `◐` / `●` fixture indicator.** The UI saying which data it is showing is exactly
  the right instinct for this project.

So this phase is not about building features. It is about which ones become **true**.

---

## 1 · Flip `fixtures` → `http` — 🟠 start here

One config change, then fix what breaks. Everything you need answers 200 today:

```
GET /api/v1/health · catchments · outlets · reef-zones · events · data-sources · alerts · models
```

- [ ] Switch `DATA_SOURCE` and work through the failures.
- [ ] **Keep the `◐`/`●` indicator.** Panels that stay on fixtures are fine — provenance,
      limitations and validation are *documents*, not computations, and nobody expects them
      live. The marker means you are not pretending.
- [ ] `/alerts` is 200-but-empty until Pulga seeds a run. Render "no runs yet" rather than a
      spinner or a crash.

**Watch out — health is at `/health`, not `/api/v1/health`.** Both now exist: the
unversioned one is the Docker HEALTHCHECK target and is deployment contract. Use
`/api/v1/health` for the dashboard — it is the artifact-aware one.

---

## 2 · The three views: dashboard · historical · live

- [ ] **Historical** — Oct 2016, end to end. This is the one that can be fully true, so it
      is the one the demo leads with.
- [ ] **Dashboard** — the summary before the detail. Per-catchment risk, per-zone exposure,
      what is currently elevated.
- [ ] **Live** — **means "latest cached forecast", not a network call.** DoD item 9 is
      "works with wifi off"; a live mode that fetches on stage can fail on conference wifi.
      Nizar is providing a cached snapshot. Same screen, same story, cannot fail.

---

## 3 · Drop in the prediction image — new, ready today

This is the "show me where the mud goes" picture, and it is **real**: real Esri satellite
imagery, the plume the model actually predicted, real Allen Coral Atlas reef outlines.
Verified working **with the network cut** — I ran the container on an isolated Docker
network where it cannot resolve the tile server and it still returned a real basemap.

```
GET /api/v1/plume/map/frames?event_id=AQ-2016-10-28&outlet_id=AQ-O01
  -> { frame_count, frames: [ { t_hours, url } ], basemap_present, plume_source }

GET /api/v1/plume/map?…&upto_hours=12   -> image/png
```

- [ ] `<img>` src, straight in. Step `upto_hours` through the frames for an animation —
      **all frames share one extent**, so the plume grows instead of the view rescaling.
- [ ] Read `/frames` rather than guessing timesteps; it returns only what the simulation
      produced.
- [ ] Surface `X-ReefShield-Plume-Source`. It says `stub` today and flips to
      `particle-engine` by itself when Abd lands. **Show that state** — a stub labelled as a
      stub is honest; a stub shown as a forecast is not.

The image carries its own provenance footer burned in, so it stays self-describing if
someone screenshots it into a slide. `X-ReefShield-Generated-Imagery: none`.

---

## 4 · Wire the what-if to the real engine

Every term in the exposure formula is already a parameter, and `formula_terms` comes back
with the run — so the drawer can show *why* a score moved, not just that it did.

- [ ] `ScenarioDrawer` → `POST /api/v1/exposure/calculate`.
- [ ] **Hold this until Mahdi's sediment anchor lands.** The sediment term is 0.0 today, so
      every slider produces 0.0 and the feature looks broken. Build the wiring, demo it
      after.

---

## 5 · Things that must not render as more certain than they are

- **The plume is a probability field, never a line.** The best free ocean model is ~9 km
  across a gulf 15–25 km wide — two or three cells span the whole basin, and our own release
  point sits on a cell the model masks as land. Contours with confidence stated, always.
- **`observed_plume_PROVISIONAL`** — the filename does not travel to the viewer. If it
  reaches the screen, the UI labels it.
- **The satellite validation is a null result and it is a *strength*.** Plume dispersed
  ~31 h after arrival; only usable passes are +104 h and +128 h. Two sensors, no plume. The
  replacement is stronger — the Kalman mooring 250 m off the Kinnet Canal, 5-minute
  sampling, turbidity **2.18 g/L**, salinity **−1.75 ‰ (19σ)**, elevated ~31 h. Frame it as
  "we looked, it could not be seen, so we measured instead".
- **`sensitivity_weight` is 1.0 everywhere**, labelled
  `PLACEHOLDER_PENDING_MARINE_SCIENTIST`. If exposure looks habitat-weighted, it is not.
- **`predicted_runoff_m3` is `None`** — occurrence, not volume. Render as a gap, never `0`.
- **`depth_median_m` can be `NaN`** — R-02 has no water cell under a 5 m reef strip at 50 m
  bathymetry. "Not measurable at this resolution", never `0`.

**Small zones are unclickable.** R-03 is 0.01 km² and R-02 is 0.04 km², now narrow irregular
strips rather than tidy boxes. Give them a minimum hit area or switch to centroid markers
below a zoom threshold.

---

## 6 · The offline basemap is yours

Both your item 9 and Mahdi's item 6 need wifi off. Tiles are the classic failure — the map
goes grey. You already committed `frontend/public/basemap/`, which is most of the answer.

- [ ] Confirm it end to end: **clean clone, wifi off, `docker compose --profile frontend up`.**
- [ ] The prediction image is safe — the backend bakes its own basemap and needs no network.

---

## Definition of done

1. Live against the API, with the `◐`/`●` state honest.
2. Three views: dashboard, historical, live-from-cache.
3. Prediction image with the timestep animation and its plume-source state shown.
4. What-if wired to `/exposure/calculate`.
5. Every caveat in §5 visible where the number is.
6. **Wifi off, clean clone, working.** Twice.
7. Arabic checked on a real screen, not at the end.

## What you depend on

| From | What | Blocked? |
|---|---|---|
| **Pulga** | seeded `/alerts`, `/explain`, `/ask` | No — the other 8 endpoints are live now |
| **Mahdi** | non-zero sediment | Only the *what-if demo*. Wire it now |
| **Abd** | real plume | No — the map endpoint works and self-labels |
| **Nizar** | cached forecast snapshot | For live mode only |
