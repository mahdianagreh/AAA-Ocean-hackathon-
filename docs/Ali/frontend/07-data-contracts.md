# 07 · Data Contracts

**Status:** locked before code · **Owner:** Ali, with Pulga · **Phase:** 0–1

The frontend is on the critical path from Day 1 and the API does not exist yet — `backend/` holds
ingestion and processing only. Everything below is built against **fixtures first**, with the real
endpoints swapped in behind an unchanged type boundary.

Endpoint list from [`04-pulga.md`](../../../tasks/phase2/04-pulga.md).

---

## 1 · The seven asks — raise on Day 1

The dependency table in [`06-ali.md`](../../../tasks/phase2/06-ali.md) says *what* arrives and *when*.
It does not say what shape it takes. Each item below is cheap to agree now and expensive to discover
on Day 6.

| # | Ask | To | Why it cannot wait |
|---|---|---|---|
| 1 | **Expose `kernel_density_contours` through `/plume/simulate` as GeoJSON** — and carry its relative-density caveat in the payload | Abd | Mostly already built (see §4). The remaining ask is that the API serves the contours rather than a raster: `observed_plume_probability.tif` is **4.2 MB**, and four timesteps × scenario reruns is tens of MB per interaction. |
| 2 | **Pre-downsampled hyetograph** at display resolution | Pulga / Nizar | `catchment_rainfall` is ~2.3 M rows. The browser must never see the raw series. |
| 3 | **Figure delivery decided** — API static mount vs frontend bundle, and who generates thumbnails | Pulga | 27 MB of PNGs; `overview_01` alone is 5.4 MB. The offline pack has to carry them either way. |
| 4 | **`/ask` citations as a structured array**, never prose | Pulga | "An uncited answer must not render as an answer" has to be structurally impossible, not a convention. |
| 5 | **SHAP drivers as ordered objects** with signed contribution and a stable key | Mahdi | Pre-rendered English strings cannot be translated at render time. |
| 6 | **Confidence as its components** — exceedance fraction, member count, threshold | Nizar / Mahdi | Same reason. The UI composes the sentence in both languages. |
| 7 | **Units never baked into value strings**; all geometry EPSG:4326 | All | RTL reorders `2.18 g/L` if it arrives as one string. See [`06-bilingual-rtl.md`](06-bilingual-rtl.md) §5. |

---

## 2 · Cross-cutting rules

**Every numeric field is `{ value, unit }` or a bare number with the unit in the type.** Never a
formatted string. The UI owns formatting because the UI knows the language.

**Every derived value carries its provenance.** Carry-over rule 5 says a reported number, a converted
number and a computed number are three different things. The type system enforces it:

```ts
type Provenance = "measured" | "reported" | "converted" | "modelled";

interface Value {
  value: number;
  unit: string;
  provenance: Provenance;
  uncertainty?: { lower: number; upper: number } | { sigma: number };
}
```

`provenance` drives the **form** rule from [`01-design-language.md`](01-design-language.md) §4 —
solid stroke for measured, dashed for modelled, hatched for an envelope. A `Value` without
`provenance` fails type-check, so an unlabelled number cannot reach the screen.

**Missing is `null`, never `0`.** A gap renders as a gap.

---

## 3 · Endpoints

| Method | Path | Feeds |
|---|---|---|
| `GET` | `/api/v1/health` | Connection indicator, offline detection |
| `GET` | `/api/v1/data-sources` | Provenance panel — the Data Sources table |
| `GET` | `/api/v1/catchments` · `/{id}` | Map layer, catchment selection |
| `GET` | `/api/v1/reef-zones` | Map layer, exposure colouring |
| `GET` | `/api/v1/events` · `/{id}` | Historical mode event selector |
| `POST` | `/api/v1/runoff/predict` | Risk cards, catchment colouring |
| `POST` | `/api/v1/plume/simulate` | The plume layer, per timestep |
| `POST` | `/api/v1/exposure/calculate` | Reef zone exposure scores |
| `POST` | `/api/v1/backtests/run` · `GET /{run_id}` | Validation panel |
| `GET` | `/api/v1/alerts` | Alert list, Scene 8 |
| `POST` | `/api/v1/explain` | SHAP drivers on the risk card |
| `POST` | `/api/v1/ask` | Assistant |

---

## 4 · The shapes that carry design weight

Four responses drive rules that cannot be retrofitted. The rest are ordinary.

### Plume — ask #1

> **The contour levels are NOT probabilities.** `particle_engine.kernel_density_contours` peak-normalises
> the density before contouring, and its own docstring is explicit: *"This is a relative density, not a
> calibrated arrival probability… Never present it as 'probability this location floods' without that
> caveat."* The satellite path carries the same warning on `plume_segmentation.anomaly_to_probability`.
>
> **The UI must never label a contour as a percentage chance of impact.** A `0.50` band means *half the
> peak density of this cloud*, which is a statement about this simulation's own shape — not about the
> Gulf. Calling it "50% probability" would be precisely the overclaim carry-over rule 7 forbids, and it
> is the first thing a judge would press on.

```ts
interface PlumeTimestep {
  t_offset_hours: number;                  // +3, +6, +12, +24
  levels: Array<{
    /** Peak-normalised relative density, NOT calibrated probability.
     *  Engine defaults are 0.10 | 0.25 | 0.50 | 0.75. */
    relative_density: number;
    /** Empty means no cell reached this density. Distinct from "no data" —
     *  the engine returns [] deliberately and the UI must not draw zero
     *  polygons as though the plume were absent. */
    geometry: GeoJSON.MultiPolygon | null; // EPSG:4326
  }>;
  confidence: ConfidenceComponents;
  density_caveat: string;                  // the relative-density warning, verbatim
  forcing_caveat: string;                  // from docs/forcing_limitations.md
}
```

The field is named `relative_density`, not `probability`, so the wrong label cannot be applied by
accident. Both caveats are **required, not optional** — the ~9 km model across a 15–25 km gulf means
they travel with the geometry rather than living in a footer someone can forget to render.

Contours, never a trajectory. Legend copy must read *relative density*, and the calibrated number the
UI *is* allowed to state as a probability is the GEFS exceedance figure below — which is derived from
ensemble members and genuinely is one.

### Confidence — ask #6

```ts
interface ConfidenceComponents {
  members_exceeding: number;            // 22
  members_total: number;                // 30
  threshold_label: string;              // "99th-percentile 3-hour rainfall"
  threshold_value: Value;
}
```

Components, not a sentence. The UI composes *"22 of 30 members exceed…"* in the active language.
A pre-formatted English string is untranslatable at render time.

### SHAP drivers — ask #5

```ts
interface Driver {
  key: string;                          // stable i18n key, e.g. "antecedent_soil_moisture"
  contribution: number;                 // signed
  value: Value;
}
```

`key` is stable and translated client-side. A human-readable English label from the API cannot become
Arabic on screen.

### Assistant — ask #4

```ts
type AskResponse =
  | { status: "answered"; text: string; citations: [Citation, ...Citation[]] }
  | { status: "no_sourced_answer"; searched: string[] };

interface Citation { file: string; section: string; excerpt?: string; }
```

**The union is the enforcement.** `citations` is a non-empty tuple on the answered branch, so an
uncited answer is unrepresentable rather than merely discouraged. `no_sourced_answer` is a distinct
render — it shows what *was* searched, which is more useful and more honest than a hedge.

The corpus is the technical and operational documentation only. **`docs/Ali/research/*` is not in it.**

---

## 5 · Fixtures and the swap

`frontend/src/api/` holds one client interface with two implementations — `fixtures` and `http` —
selected by env var. Components never know which is live.

**Fixtures are built from real repo artefacts, not invented.** Geometry from
`data/processed/vectors/*.gpkg`; event values from the event contract in
[`00-phase2-plan.md`](../../../tasks/phase2/00-phase2-plan.md) (salinity 38.75 ‰, −1.75 ‰ at 19σ;
turbidity peak 2.18 g/L; ~31 h elevated); the Data Sources table from
[`data_dictionary.md`](../../data_dictionary.md); the 34 figures from
[`qa_screenshots/manifest.json`](../../qa_screenshots/MANIFEST.md). Invented fixtures produce a UI
that fits numbers which never arrive.

**Swap order** — as each lands, delete the fixture and keep the type:

| Day | Arrives | From |
|---|---|---|
| 3 | Typed endpoints, stubs acceptable | Pulga |
| 3 | Stable read schema | Nizar |
| 4 | 34 figures + captions | already in the repo |
| 5 | Risk fields + driver list | Mahdi |
| 6 | Plume layers per timestep | Abd |

**Contract tests run against both implementations.** A fixture that stops matching the live response
fails CI rather than surfacing as a blank panel during rehearsal.

---

## 6 · Known data facts the UI must respect

Verified in the repo, not assumed:

- **Reef `sensitivity_weight = 1.0` everywhere.** Exposure varies only through the hazard term. The
  legend must not imply zones differ in sensitivity.
- **`AQ-O04` discharges into an enclosed harbour basin.** Its caveat travels with it wherever it is
  selectable.
- **`AQ-O01` carries 96% of the discharge.** It is the demo path.
- **`overview_01_master_all_layers.png` is excluded from the provenance panel.** Its own burned-in
  caption reads *"CATCHMENTS ARE A LOCAL TEST FIXTURE… 5 latitude bands, not a watershed
  delineation."* Best-looking figure, wrong catchments.
- **`manifest.json` lists 34 figures; 36 PNGs exist.** The two extras are Abd's later plume figures.
  Driving the panel off the manifest is correct and silently omits them — a decision, not an accident.
- **Satellite validation is a null result.** Concept §15.3 Scene 6 says "reveal the satellite plume";
  that is superseded. The mooring time series is the validation target.
