# Phase 6 — Mahdi's rows that did not pass

Summary of every row Mahdi tested (`00-master-test-matrix.md`) that came back
**FAIL** or **BLOCKED-NOT-BUILT**, in whole or in part. PASS rows are omitted
even where a secondary finding was noted — see the matrix for those. Nothing
listed here has been fixed, built, or wired — Phase 6's rule is to record and
stop.

| ID | Feature | Verdict | Evidence |
|---|---|---|---|
| b1 | Automated Plume Segmentation Model | **BLOCKED-NOT-BUILT** | `evidence/b1/no_segmentation_model.txt` |
| b2 | Learned Transmission-Loss Model | **BLOCKED-NOT-BUILT** (learned-model half only) | `evidence/b2/runoff_predict_basis.json`, `evidence/b2/override_check.txt` |
| b3 | Cross-Site Transfer Learning | **NOT TESTED** — skipped by explicit user instruction | — |
| b9 | Culvert/Drainage-Conflict Detector | **BLOCKED-NOT-BUILT** | `evidence/b9/culvert_crosscheck_rerun.txt`, `evidence/b9/data_dictionary_27_vs_46.txt` |
| p4-04 | Top Weather Drivers Explainer | **FAIL** (Pulga's wiring half only — Mahdi's driver-generation half is real) | `evidence/p4-04/runoff_predict_real_drivers.json`, `evidence/p4-04/explain_with_unrenamed_key_field_500.json`, `evidence/p4-04/explain_with_real_driver_names.json` |

---

## b1 — Automated Plume Segmentation Model

**Why it didn't pass:** there is no automated segmentation model to run. The
only related file, `backend/src/models/plume_segmentation.py`, is a
spectral-anomaly detector whose own docstring says it is "Deliberately not a
segmentation model — the Aqaba-specific labeled set is far too small for that
to mean anything." It is not wired into any API endpoint (`grep -n segment
backend/src/api/main.py` returns nothing), and has no human-review flag field
(`human_reviewed`/`agreement_score`) that the task's spec calls for.

**What is blocking it:**
1. No trained segmenter exists, and none can be trained — the labeled set is
   too small by the module's own admission.
2. There is no real input to run one against even if it existed: Phase 5
   established that no satellite pass ever captured the anchor event's plume
   (it dispersed ~31 hours before the first usable Sentinel-2/Landsat-8
   pass) — a physical impossibility, not a missing download.
3. `tasks/mahdis-features-handoff/HANDOFF_abd_b1_plume_masks.md` (the ask to
   Abd for plume masks) has never received a RESPONSE file, unlike the B2 and
   B3 handoffs to Karam. It is still open.

## b2 — Learned Transmission-Loss Model (learned-model half)

**Why it didn't pass (learned-model half):** `transmission_loss_basis` is
correctly, honestly `"negev_proxy"` on every call (confirmed live, default
and overridden) — that half is a genuine PASS. But no `"learned"` code path
exists anywhere (`grep -rn '"learned"'` across `backend/src` shows it only in
comments/type unions, never assigned).

**What is blocking it:** nothing is blocking it — this is a closed, tested
decision, not a gap. `scripts/31_test_learned_transmission_loss.py` (8 Aug)
built a regression model against real data (Cataldo et al. 2010, 12 systems,
58 usable storms) under leave-one-system-out CV, and it scored worse than
predicting the mean for every feature combination tried. Transmission loss is
dominated by storm-to-storm dynamics that dataset doesn't capture, not by
static catchment characteristics that a model could learn. Building one
anyway would mean shipping a model already shown not to work.

## b3 — Cross-Site Transfer Learning

**Not tested** — the user explicitly said "no need for the b3" and it was
skipped this phase. Separately, `tasks/mahdis-features-handoff/README.md`
already records this as closed/out-of-scope (Aqaba-only this phase, per
Karam's response), so a BLOCKED verdict would likely have followed if tested.

## b9 — Culvert/Drainage-Conflict Detector

**Why it didn't pass:** the feature asked for is an automated detector; what
exists is `scripts/12_culvert_crosscheck.py`, a manual script that still runs
correctly and still produces a real 5-outlet verdict table (rerun live,
confirmed identical to Phase 4/5's results). No separate "B9 detector" file
exists anywhere — this matches Phase 7's own independent "Absent" verdict for
this row.

**What is blocking it:**
1. No automated detector was ever built — only the manual script, per
   `tasks/mahdis-features-handoff/README.md`'s own note: "B9 has no entry
   because it has no data gap: it formalizes a manual check... that already
   runs on data already on disk."
2. A separate, real documentation gap surfaced during this rerun: the manual
   script now reports **46** mapped culverts, not the **27** quoted in
   `tasks/phase4/02-mahdi.md`, `tasks/mahdis-features-handoff/README.md`, and
   `p4-D`'s task description. This is not a new bug — `docs/data_dictionary.md`
   line 1210 already documents a 2 Aug 2026 AOI correction that raised the
   count — but the correction never propagated into the task files that still
   quote 27, and nothing currently re-derives the 27→46 change automatically.

## p4-04 — Top Weather Drivers Explainer (Pulga's wiring half)

**Why it didn't pass:** Mahdi's half — real weather-driver features and
contributions from `predict_one()` — is confirmed real and live
(`evidence/p4-04/runoff_predict_real_drivers.json`). But nothing threads that
output into `/explain`'s `shap_drivers` field: `grep -n shap_drivers
backend/src/api/main.py` shows exactly one use, a straight pass-through of
whatever the caller supplies. Feeding the real driver list in manually still
fails downstream — the four real driver names (`rain_self_percentile`,
`rain_over_p90`, `precip_prior_1d_mm`, `precip_prior_3d_mm`) aren't in
`DRIVER_PHRASE`'s vocabulary, so the generated sentence has no verb and reads
as a bare list, not English.

**What is blocking it:**
1. The wiring step from `tasks/phase4/04-pulga.md §3` ("thread real driver
   output from `predict_one()` into the `shap_drivers` field the explain
   route already accepts") was never done — this is Pulga's piece, not
   Mahdi's.
2. Even once wired, `DRIVER_PHRASE`'s vocabulary needs the four real feature
   names added, or the explainer falls back to a generic
   `feature.replace("_", " ")` phrasing with no grammatical framing.
3. `tests/test_explain_fidelity.py` (10 passing tests) only ever exercises
   hand-typed fixture names that already match `DRIVER_PHRASE` — it has never
   caught this gap because it never runs against the model's actual current
   driver vocabulary.

---

## Rows that passed, for completeness

`core-A`, `core-B`, p4-09 (claim/data, not wired to a live endpoint), `p4-C`,
`p4-D` (backend regression), `p4-H` (core claim; one flaky assertion on cold
start, unrelated to the offline claim itself), and `p4-J` all recorded PASS —
see `00-master-test-matrix.md` for full notes and evidence on each, including
secondary findings noted in passing (a stale code comment in
`sediment_proxy.py` for p4-C; the same 27-vs-46 staleness carried into p4-D).
