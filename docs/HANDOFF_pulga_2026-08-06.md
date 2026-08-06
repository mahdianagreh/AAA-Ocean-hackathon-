# Handoff to Pulga — 6 August 2026

Mahdi. `feature_attributions` confirmed against a real feature row, per Phase 4 task
1. Short version: it works, and there is one sharp edge you need before wiring
`/explain`'s `shap_drivers` to it.

---

## 1 · Confirmed real, on a real feature row

`predict_one(da.training_row("AQ-2016-10-28", "AQ-C01"))` returns:

```
feature_attributions_status: None
runoff_probability: 0.723
feature_attributions:
  rain_self_percentile   shap +0.996   value 0.989
  rain_over_p90          shap +0.774   value 1.019
  precip_prior_1d_mm     shap +0.602   value 9.58
  precip_prior_3d_mm     shap -0.513   value 11.46
```

That is a coherent story for the anchor storm: it was near the top of AQ-C01's own
wet-day distribution (`rain_self_percentile` 0.989), well above its 90th-percentile
threshold, with heavy rain the day before and a wetter-than-usual prior 3 days. This is
what a real explanation looks like — safe to wire.

## 2 · `feature_attributions_status` — the one-sentence definition

- **`None`** — TreeSHAP ran successfully. Trust the four `feature_attributions` entries.
- **A string** — TreeSHAP raised an exception (most likely: `shap` not installed in this
  environment). `feature_attributions` is `[]` in this case, **not** four entries at
  `shap: 0.0`. Render "drivers unavailable," never a chart of zeros — a zero-SHAP bar
  chart reads as "the model says none of these matter," which is the opposite of what a
  gap means. Source: `backend/src/models/runoff_model.py`, the comment above
  `shap_unavailable`.

## 3 · The sharp edge — `status: None` does not mean "meaningful"

This is the part the audit couldn't see from outside, and it is real. I tested
`predict_one({"catchment_id": cid, "rainfall_mm_3h": 42.7})` — a minimal request, no
`da.training_row()` — for three different catchments:

```
AQ-C01  p=0.0132  temp_c -1.810, wind_direction_deg -1.098, rain_self_percentile +0.782, rain_over_p90 +0.761
AQ-C03  p=0.0132  temp_c -1.810, wind_direction_deg -1.098, rain_self_percentile +0.782, rain_over_p90 +0.761
AQ-C05  p=0.0132  temp_c -1.810, wind_direction_deg -1.098, rain_self_percentile +0.782, rain_over_p90 +0.761
```

Identical probability, identical drivers, regardless of catchment. `rainfall_mm_3h`
does not match any of the 20 real feature names (`precipitation_mm_day`, etc.), so it
never reaches the model — every field is NaN, and TreeSHAP still runs cleanly on an
all-NaN row and returns a value. **`feature_attributions_status` is `None` in this case
too** — SHAP did not fail, so the status field cannot tell you this happened. The
output looks exactly as "real" as the anchor-storm example above; it is not.

**The rule, concretely: only call `predict_one()` with a full feature row from
`da.training_row(event_id, catchment_id)` when you want attributions a user should see.
Never wire `/explain`'s driver chart to a request built from a handful of scenario
fields (`rainfall_mm_3h`, `antecedent_index`) — it will return a confident-looking,
completely fixed set of "drivers" that do not depend on the scenario at all.** If
`/explain` needs to support live what-if sliders later, that is a separate design
question (the scenario endpoint would need its own honest attribution story, or none);
it is not solved by treating today's `feature_attributions` as if it already covers
that case.

## 4 · The exact shape, for `shap_drivers`

```json
"feature_attributions": [
  {"feature": "rain_self_percentile", "shap": 0.99564, "value": 0.9894157493649449},
  {"feature": "rain_over_p90", "shap": 0.77415, "value": 1.0190859284850926},
  {"feature": "precip_prior_1d_mm", "shap": 0.60242, "value": 9.576631823146164},
  {"feature": "precip_prior_3d_mm", "shap": -0.51281, "value": 11.461350847038071}
]
```

Up to 4 entries (`TOP_DRIVERS` in `runoff_model.py`), sorted by `|shap|` descending.
`value` is `None` when that specific feature was missing from the request (carried
through as a gap, never zero-filled) — on a real `training_row()` row this should not
happen for any of the 20 canonical features.
