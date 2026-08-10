# Phase 8 — Karam's report (Pages 8, 9, 12)

**Role:** content accuracy on Provenance (8), Site Scoring content (9), Data Explorer
(12). Ali implements the UI. This report hands Ali the verified facts and flags
anything that must not be styled over. **One code change was authorized (fix
`CRITERION_LABELS` if drifted) — it is NOT needed; the labels have not drifted.**

Method: read against the sources of truth — `docs/qa_screenshots/MANIFEST.md`,
`frontend/public/fixtures/provenance.json`, `docs/Ali/research/01-signature.md`,
`backend/src/models/site_scoring.py`, and `ARTIFACTS` in `data_access.py`.

---

## PAGE 8 — Provenance

### Filter categories — confirmed, with one silent loss to fix

The gallery filter chips are the figure `source` values, which are the **MANIFEST.md
section headings** carried per figure in `provenance.json`. The manifest has **six**
headings; the gallery fixture carries only **four**:

| MANIFEST.md heading | in gallery? | figures | verdict |
|---|---|---|---|
| Cross-cutting | ✅ | 1 | `overview_01` is deliberately **excluded** (stated reason: its catchments are a local 5-band test fixture, not the real delineation). Honest. `overview_02` shown. |
| Frontend | ❌ **missing** | 1 (`map_01_borders_and_label_hygiene.png`) | **Silent loss — must fix.** See below. |
| Land chain | ✅ | 25 | fine |
| Marine chain | ✅ | 11 | fine |
| Phase 2 backend | ✅ | 5 | fine |
| Produced by another workstream | ❌ absent | 3 (`currents_01`, `plume_index…`, `plume_manual_qc…`) | Deliberately `omitted_from_manifest` — uncaptioned by Pulga's QA scripts. Acceptable as a stated omission, but they never appear in the gallery. |

**The one real defect: `map_01` (the whole "Frontend" section) is not in the gallery.**
`provenance.json` records `manifest_count: 43`, but the current `MANIFEST.md` header
says **44 figures** and `map_01` carries a full caption + a `2026-08-09 07:47 UTC`
timestamp. The committed fixture is **one regeneration behind the manifest** — it
predates the 9 Aug frontend map figure. So the redesign will ship a gallery that
silently omits the one figure documenting the frontend map fix.

- **Recommended fix (for whoever owns the fixture, not styled around):** regenerate
  `provenance.json` from the current manifest so `map_01` (source **"Frontend"**)
  appears. ⚠️ Phase 7 explicitly warned that regenerating fixtures pulls in unrelated
  doc drift — so own that diff deliberately; do not blanket-regenerate. If it is not
  regenerated this phase, the gallery must not claim to be the full figure set.
- **Which chips are user-facing:** Cross-cutting, Frontend, Land chain, Marine chain
  are legitimate visitor filters. **"Phase 2 backend"** is an internal-provenance
  category — keep it (the figures are real) but it reads as jargon to a visitor;
  a plain-language chip label like **"Exposure engine (backend)"** is better. There is
  no "Produced by another workstream" chip because those figures aren't in the gallery.

### "Processing chain" — section-inferred, NOT a per-figure field

The modal's metadata row labels `shown.source` as **"Processing chain."** That `source`
is the **manifest section heading** the figure sits under (`Land chain`, `Marine chain`,
…), not a per-image processing lineage recorded per figure. It is honest as a *section*,
misleading as a *chain*.

- **For Ali:** relabel that metadata item **"Section"** (or "Provenance section"), not
  "Processing chain." Same value, honest name. No fabricated per-image chain.

### Caption integrity through the split — holds

Ali splits each caption into a bold summary (first sentence) + supporting detail. Both
halves render (`capSummary` as the dialog title, `capDetail` as the paragraph below), so
**no caption text is stripped** — it is only reflowed. Confirmed the qualifier that
makes a caption true survives:
- The 6 test-fixture figures (`soilgrids_07/09`, `urban_01/02`, `worldcover_04/05`)
  carry "CATCHMENTS ARE A LOCAL TEST FIXTURE… 5 latitude bands" at the **end** of the
  caption → lands in `capDetail`, still shown. **Do not change the split to drop the
  tail**, or those become mis-captioned (a summary "Stacked composition per catchment"
  with the fixture disclaimer gone would read as a real deliverable).
- `reef_*` captions keep their "PROVISIONAL vs final" / ACA-geometry qualifiers in the
  detail. Intact.

### "Generated date" per figure — real; 6 predate 3 Aug, none at retired-bbox risk

Every figure has a real `generated` timestamp. Six predate **3 Aug 2026**
(`2026-07-31`): the six test-fixture figures above. These are **not** real-AOI
deliverables — their own captions state the geometry is a 5-band local fixture — so the
retired-bounding-box concern (`(34.80,29.25,35.15,29.70)` cutting Wadi Yutum) does not
apply; they never claimed to cover the real AOI. No mis-caption. Nothing to flag beyond
keeping the fixture disclaimer visible (above).

---

## PAGE 9 — Site Scoring (content)

### C1–C6 labels vs the `01-signature.md` rubric — exact match, no drift

| key | `CRITERION_LABELS` (backend) | rubric heading (`01-signature.md`) | matches? |
|---|---|---|---|
| C1 | Ephemeral, not perennial, drainage | C1 · Ephemeral, not perennial, drainage | ✅ exact |
| C2 | Rare but high-intensity rainfall | C2 · Rare but high-intensity rainfall | ✅ exact |
| C3 | Reef or seagrass within a few kilometres | C3 · Reef or seagrass within a few kilometres of the outlet | ✅ faithful (drops the location tail "of the outlet"; **keeps "or seagrass"** — the part that defines what C3 measures) |
| C4 | Narrow shelf or restricted-flushing basin | C4 · Narrow shelf or restricted-flushing basin | ✅ exact |
| C5 | Development at the outlet | C5 · Development at the outlet | ✅ exact |
| C6 | Data-poor and unmonitored | C6 · Data-poor and unmonitored | ✅ exact |

**No correction pushed into `CRITERION_LABELS`** — it already matches the rubric. The
authorized "fix if drifted" change is deliberately not made.

**Fork watch:** the page actually renders the **i18n key** `sites.criterion.C*`
(`frontend/src/i18n/locales/en/tools.json`), while the backend's `CRITERION_LABELS` is
used only in the `/explain`-style narrative string (`site_scoring.py:232`). Two label
sources — exactly the fork the task warned about. **They currently agree** (both match
the rubric). Keep them in sync; if one ever changes, change both.

### Short forms — approved

C3's full label wraps on a scorecard row. An acceptable short form is **"Reef/seagrass
within a few km"** — it must keep "seagrass"; **"Reef within a few km" is not allowed**
(narrows the criterion). If no faithful short form fits, the row wraps. All others are
short enough as-is.

### Arabic labels — present, at parity, approved

`sites.criterion.C1–C6` exist in `ar/tools.json` at exact key parity with EN, and are
faithful domain terms (not machine-flattened):

| key | AR | back-check |
|---|---|---|
| C1 | تصريف عرضي لا دائم | "ephemeral, not permanent drainage" ✅ |
| C2 | أمطار نادرة لكن عالية الشدة | "rare but high-intensity rainfall" ✅ |
| C3 | شعاب أو أعشاب بحرية على بُعد كيلومترات قليلة | keeps "or seagrass" (أعشاب بحرية) ✅ |
| C4 | رفّ ضيّق أو حوض محدود التدفّق | "narrow shelf or restricted-flow basin" ✅ |
| C5 | تطوير عمراني عند المصبّ | "urban development at the outlet" ✅ |
| C6 | فقير البيانات وغير مرصود | "data-poor and unmonitored" ✅ |

### Score scale — dots are honest (integer 0/1/2), and every score is partial (5 of 6)

Every scorer returns exactly **0.0 / 1.0 / 2.0** (`site_scoring.py:84,122,149,166,183`) —
never fractional. So a **filled-dots-out-of-2 indicator is correct**; a bar is not
needed. **Tell Ali: dots, 2 max.**

Critically, **C6 (`score_c6_data_poor`) always returns `insufficient_data`, for every
coordinate on earth including Aqaba** (`site_scoring.py:192`). So a complete run is
**always "5 of 6 criteria scored", max 10 not 12.** The plan's "partial vs complete
score" note is not cosmetic — it is the normal case. The overall-score visual must not
imply /12 when C6 is structurally unscored, and the raw `C1`…`C6` keys stay as small
secondary detail (they are how the team and the rubric refer to the criteria).

---

## PAGE 12 — Data Explorer

### Inventory — 4 categories, all LIVE, nothing stale, nothing invented

| category chip | fetcher → endpoint | backing artifact (`data_access.ARTIFACTS`) | status |
|---|---|---|---|
| Reef zones | `fetchReefZonesLive` → `/api/v1/reef-zones` | `reef_zones` (final ACA `reef_zones.gpkg`) | **live** |
| Events | `fetchEvents` → `/api/v1/events` | `event_catalogue` | **live** |
| Dive sites | `fetchDiveSites` → `/api/v1/dive-sites` | `osm_aqaba` / `places.geojson` | **live** |
| Data sources | `fetchDataSources` → `/api/v1/data-sources` | `data_dictionary` | **live** |

No category maps to a missing artifact; nothing **stale**, nothing that **never
existed**. The four columns per category are all real response fields.

Checks from my task file:
- **Provenance ledger present as a first-class category.** The "Data sources" chip *is*
  `data_dictionary.md` served live (product, version, resolution, access date, licence,
  limitations) — satisfies "every exposed field has a provenance row" for the ledger
  itself. ✅
- **PROVISIONAL not surfaced.** Reef zones read the **final** `reef_zones.gpkg` via the
  live endpoint, never `reef_zones_PROVISIONAL`. The suffix is not dropped because the
  provisional artifact is not exposed here at all. ✅
- **Nulls render as gaps.** Every numeric cell uses `ValueWithUnit`, and every text cell
  falls back to `<ValueWithUnit value={null} />` — no `0`-coercion, no blank. ✅
- **No `[object Object]` risk.** Every cell renders a scalar (string via `IdText`/`span`
  or a number via `ValueWithUnit`); the dive-site `caveats[]` array is rendered through
  `CaveatList`, deduped, not stringified. ✅

### One flag before Ali styles it — source-vs-derived labelling

In `renderTable`, `rank` and `max_daily_mm` (Events) are rendered
`provenance="measured"`. Both are **derived**, not measured: `rank` is a computed
ordering and `max_daily_mm` is an IMERG-derived daily aggregate. Marking them "measured"
flattens the source-vs-derived distinction the project treats as load-bearing. This is
the exact place an explorer flattens provenance. **Flagged, not fixed** (Phase 8 adds no
data and I own content, not the JSX) — recommend `provenance="modelled"` (or "converted"
for the aggregate) when Ali touches this table. Same note applies to any depth/area cell
that is interpolated rather than directly measured.

---

## Suggestions (noticed, deliberately not acted on this phase)

1. **Regenerate `provenance.json` deliberately** so the Frontend section (`map_01`)
   stops being silently absent — owning the diff, per the Phase 7 fixture-drift warning.
   Ideally the gallery loader should *assert* `manifest_count == on_disk_count − excluded
   − omitted` and surface a visible "N figures not shown" line instead of silently
   dropping any.
2. **Collapse the two criterion-label sources** (backend `CRITERION_LABELS` and frontend
   `sites.criterion.*`) to one — e.g. serve the label in the API response — so they
   cannot fork. They agree today; nothing structural keeps them agreeing.
3. **Provenance honesty in Data Explorer** (the rank/max_daily_mm "measured" note above)
   — a small correctness pass worth doing when the table is next edited.
4. The overall Site Scoring score should probably be presented as **/10 (5 scored
   criteria)** with C6 shown as a permanently-greyed "not scored anywhere" row, rather
   than a donut implying /12 — makes the structural partiality legible at a glance.
