# Karam — Phase 3

Integration lead. Read [`00-phase3-plan.md`](00-phase3-plan.md) first.

The rainfall pipeline is finished and it is not what this phase needs from me. Phase 2
item 7 closed on 3 Aug; the only Phase 2 item still open is the vertical slice, which is
**item 8 and it is due in two days.**

My job now is the seams and the rehearsal. I have caught **six seam faults in three days**
and every one produced plausible output with no error:

| | what it did |
|---|---|
| `sediment_class` | three spellings across three modules; the only value the schema allowed crashed the particle engine |
| runoff model keys | API read 3 keys the model does not return; a real prediction rendered as "0 m³" |
| API imports | resolved only under the test layout, so 482 tests were green while `docker compose up` started nothing |
| reef zones in Supabase | loader pinned to the provisional file, so the DB served superseded geometry |
| duplicate events in Supabase | 16 storm-days I had merged away, dragging 80 duplicate feature rows |
| catalogue merge floor | tied to the wet-day threshold, so lowering `--top-n` reintroduced train/test leakage |

That is the pattern this project keeps hitting, and it is the thing I am for.

---

## 1 · Finish the sweeps, rebuild the matrix

Both running under supervisors as of 4 Aug — 33,920 / 97,200 granules and 108 / 240 months.
Resume across network changes, sleep and a new IP; nothing re-downloads.

- [ ] **Do not wait for 100 %.** IMERG runs wettest-first, so every day above 1 mm lands
      early. Rebuild from whatever is on disk, then again when it finishes.
- [ ] `extract_event_antecedents.py` → `build_feature_matrix.py` → tell Mahdi.
- [ ] `rain_3h_mm` into the matrix. That is his Request 2 and he called it correctly: the
      model currently cannot distinguish 6 mm in an hour from 6 mm over twelve, which in a
      hyper-arid catchment is the whole difference.

**Watch out.** The IMERG sweep exits 0 after a total network failure — on 4 Aug a one-second
DNS blip failed all 675 events and it logged **"STAGE 2 DONE"**. The supervisor now judges
completion from granules on disk, never the exit status. Do not trust that log line.

---

## 2 · Rotate the credentials — 🔴 overdue

`docs/data_access_setup.md` is explicit: *"If a credential is exposed even once, rotate it
at the provider immediately."* Three have been, and OPEN-ISSUES #20 says they remain
recoverable from git history.

- [ ] Earthdata password
- [ ] CDS API token
- [ ] Supabase database password
- [ ] Re-check after: both sweeps and the DB loaders read from `.env`, so rotating mid-sweep
      breaks a running download. **Rotate when the sweeps finish**, not during.

This is the item most likely to be skipped because nothing visibly breaks. Do it anyway.

---

## 3 · The seams — the part that fails silently

- [ ] **`position_confidence` has two vocabularies** (issue #7). Same shape as the three I
      have already fixed. Pin it with a test the way
      `tests/test_sediment_class_vocabulary.py` does.
- [ ] Sweep the remaining OPEN-ISSUES for the same family: variable key sets (#8), units
      baked into strings (#14), SHAP drivers as unstable keys (#3), confidence as a sentence
      rather than components (#4).
- [ ] **Adopt the rule and write it down:** a value that crosses a module boundary is a
      contract and earns the same discipline as `AQ-C01` or `R-03`.

## 4 · Verify the DB keeps matching the files

- [ ] After everyone's reloads, re-run the check I did on 4 Aug: events, feature rows and
      reef zones must match the parquet/gpkg exactly, zero orphaned foreign keys. If they
      diverge, the API and the model are reading two different truths and nothing announces
      it.

---

## 5 · The rehearsal — this is the deliverable, not a formality

Green tests have already coexisted with a dead product. On 4 Aug the suite was 482-green
while nothing in the compose stack would start, because the tests import the app a
different way than the container does. **The only test that counts now is the demo running
from a clean clone with the wifi off.**

- [ ] Clean clone → `docker compose up` → wifi off → walk the whole story. **Twice**, before
      the 12th.
- [ ] Time it. If the story is 5 minutes, the judges see maybe three screens — know which
      three.
- [ ] Confirm nothing in the demo path reaches the network. Currently offline-safe: the plume
      renderer bakes its own basemap (verified on an isolated Docker network), Ali committed
      his map layers, the RAG is extractive and needs no key. The last reach is forecast
      ingestion — Nizar's cached snapshot closes it.
- [ ] **`data/` is a bind mount and it is git-ignored.** Decide with Mahdi before the 12th:
      bake the demo subset into the image, or ship a documented volume. A fresh clone on a
      judge's laptop has no data at all.

## 6 · The narrative — mine to hold, because it is the integration story

The strongest material is the honest material, and it is easy to lose under features:

- **The satellite could not see the plume, so we said so and measured instead.** Dispersed
  ~31 h after arrival; only usable passes +104 h and +128 h. Replaced by the Kalman mooring
  at 5-minute sampling — turbidity 2.18 g/L, salinity −1.75 ‰ (19σ).
- **The baseline was broken and we fixed it against ourselves.** Textbook SCS put the runoff
  threshold above Aqaba's maximum daily rainfall in 27 years, so "we beat the baseline by
  +0.75" was comparing against a constant zero. Corrected, the baseline scores 0.200 and the
  model 0.741.
- **Random CV 0.514 vs LOCO 0.521.** We looked for the leak we warned ourselves about and
  reported both numbers.
- **The assistant cannot invent a number** — it retrieves and quotes rather than generating.
- **Nothing in the product is generated imagery.** The prediction picture is a real satellite
  photo with the model's own output drawn on it, and the first render put the plume over the
  airport, which is how we found the plume was still a stub.

- [ ] Take one hard question at yourself for each: *"is that really true?"* Anything that
      does not survive it comes off the slide.

---

## Definition of done

1. Sweeps finished, `rain_3h_mm` in the matrix, Mahdi told.
2. **Credentials rotated.**
3. `position_confidence` unified and pinned; the seam rule written down.
4. DB verified against the files, zero orphans.
5. **Demo rehearsed twice from a clean clone with wifi off**, timed.
6. Narrative written, every claim survives one hard question.

## The two risks I own naming

**Mahdi is a single point of failure** on the sediment anchor, which gates five things. If it
has not moved by end of **5 Aug**, I take it.

**We are two days from the vertical slice** and this plan is really "finish Phase 2 +
productise". Say that to the team rather than letting anyone budget nine clean days for new
work.
