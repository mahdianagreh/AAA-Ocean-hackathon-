# 04 · Component Inventory

**Status:** scaffold — filled during Phase 2–4 · **Owner:** Ali

Every component is listed with **all** of its states. A component whose empty, error and stale states
were never designed will improvise them on stage.

**Every component lands on `/specimen` the day it is written**, rendered in both themes × both
directions. A primitive that is not on the specimen route has not been checked.

---

## Required states

Default · hover · focus-visible · active · disabled · **loading** · **empty** · **error** ·
**stale** (data older than its refresh interval — a real state in Forecast mode, not a hypothetical).

## Primitives — Radix behaviour, our styling

| Component | Radix base | Notes |
|---|---|---|
| `ModeSwitch` | Toggle Group | Three modes; keyboard arrows; preserves time cursor |
| `TimeSlider` | Slider | **Bespoke.** Track keeps left = earlier in RTL, matching the chart |
| `LayerToggle` | Checkbox | Groups by layer family |
| `ScenarioControl` | Slider / Select | Six of them, incl. transmission loss |
| `LangToggle` | Toggle | Sets `lang` + `dir` on `<html>` |
| `Popover`, `Dialog`, `Tooltip` | — | Verify each under `dir="rtl"` |

## Domain components

| Component | Feeds scene | Notes |
|---|---|---|
| `RiskCard` | 3, 8 | Score band, SHAP drivers, confidence, recommended action, caveat |
| `ConfidenceMeter` | 3, 8 | Composed from components, never a pre-formatted sentence |
| `DriverBars` | 3 | Signed SHAP contributions, translated from stable keys |
| `Hyetograph` | 3 | Time cursor synced to the slider |
| `MooringChart` | 6 | Salinity + turbidity, **solid** = measured |
| `ValidationPanel` | 6 | Modelled vs measured, plus the satellite null result |
| `ProvenancePanel` | — | 43 figures from `manifest.json` + the Data Sources table |
| `LimitationsPage` | — | From `pitch_limitations.md` and `forcing_limitations.md` |
| `Assistant` | — | Cited answers only; `no_sourced_answer` is a distinct render |
| `AlertCard` | 8 | The §15.4 alert, with confidence and caveat |
| `Legend` | 4, 5 | Must not imply reef zones differ in sensitivity |
| `ValueWithUnit` | everywhere | Bidi-isolated, mono, tabular. **The only way a number reaches the screen.** |
| `ProvenanceMark` | everywhere | Solid / dashed / hatched per `provenance` |

## Scene → component coverage

Tracked against [`00-master-plan.md`](00-master-plan.md). A scene with no component by the end of
Phase 4 is a schedule alarm.

- [ ] 1 problem · [ ] 2 storm · [ ] 3 land · [ ] 4 marine
- [ ] 5 exposure · [ ] 6 validation · [ ] 7 what-if · [ ] 8 recommendation
