# 08 · Map Rendering

**Status:** scaffold — filled during Phase 1–2 · **Owner:** Ali

**There is no map or geospatial skill in the 202-skill registry.** These are our own rules.

---

## Basemap

Custom MapLibre vector style, with a cached satellite layer as an optional toggle. Both tile sets go
into the offline pack — DoD item 9 is "works with wifi off", and tiles are the biggest risk to it.

- [ ] Style JSON authored against the design tokens, not a borrowed theme
- [ ] Isobaths rendered as the signature hairline, shared with the UI chrome
- [ ] Label field switches `name` / `name:ar` with the language, falling back when `name:ar` is absent
- [ ] Tile pack sized and cached; measure before Phase 5

## The plume — the rule that is not negotiable

> **A contoured field with its caveats stated. Never a single trajectory line — and never labelled
> as a probability.** The levels are peak-normalised relative density; see
> [`07-data-contracts.md`](07-data-contracts.md) §4.

The best free ocean model is ~9 km across a gulf 15–25 km wide, and our own release point sits on a
cell the model masks as land. `forcing_caveat` travels with the geometry rather than living in a
footer. See [`forcing_limitations.md`](../../forcing_limitations.md).

- [ ] Contours from the API as GeoJSON `MultiPolygon` per density level per timestep (ask #1)
- [ ] Legend reads *relative density*, never a percentage chance of impact
- [ ] An empty level is "no cell reached this density", rendered distinctly from "no data"
- [ ] Fallback if delivered as raster: contour client-side and accept the cost
- [ ] The ~9 km model grid as an optional overlay — the honesty device

## Layers

Stack and z-order in [`03-information-architecture.md`](03-information-architecture.md) §4.

- [ ] Hazard fills carry a 1 px stroke at the next band up — a fill alone is not a boundary
- [ ] `AQ-O04` renders with its enclosed-harbour caveat attached
- [ ] Reef legend must not imply zones differ in sensitivity (`sensitivity_weight = 1.0` everywhere)
- [ ] Missing data renders as hatch, never as a zero-valued fill

## Deck.gl

Default answer is **no**. It ships only if animated particles measurably communicate something the
contours cannot, and only if the time-scrub still holds 60fps with it on.

## Accessibility

- [ ] Keyboard pan and zoom
- [ ] **The map is never the only path to a fact** — everything it encodes is reachable as text
- [ ] Attribution control always visible: OSM, MapLibre, GMRT, Allen Coral Atlas

## Verification

- [ ] Arabic labels render with the network disabled (Phase 1 gate)
- [ ] Full time-scrub holds 60fps with every layer live
- [ ] Map renders from the offline pack with no network calls in the Network panel
