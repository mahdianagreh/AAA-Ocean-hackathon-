# 18 · Technical — Risk register

**Part D. Scientific and engineering risks, scored, with the ones the project has not yet
written down flagged.**

> **The short version.** **Re-ranked 2026-08-02, and the list got shorter and harder** — the two
> engineering risks that used to top it have been fixed.
>
> **The three that matter now:**
>
> 1. **Nothing is validated yet.** The imagery route is closed (§1.5), so the only path runs through
>    the transport engine against the mooring record — **and that engine does not exist.**
> 2. **Team dissolution after 13 August.** Costs nothing to mitigate; determines whether any of the
>    rest matters.
> 3. **Credentials are still in git history.** `.env` is untracked, but `git show 1819b3e:.env`
>    still returns it. **Rotation is the only real fix, and it has not happened.**
>
> **Still unmodelled:** transmission loss — **20–85%** of a Negev flood can never reach the sea.
>
> **Fixed since the first pass:** the too-small download box (now `RETIRED_BOX`, guarded by three
> tests) and the merge of Mahdi's branch. **Still open and cheapest:** the dependency manifest.

The concept doc §25 already has a risk table. This one **extends** it with risks discovered
during this research pass and during the code audit, and re-scores the existing ones against
the measured build state.

Scoring: **P** = probability, **I** = impact if it lands. **[judgement]** throughout.

---

## 1 · Risks the project has NOT yet documented

These are the additions. Each one is either absent from
[`docs/pitch_limitations.md`](../pitch_limitations.md) and concept doc §24–25, or present
but under-weighted.

### R1 · Transmission loss — the biggest unmodelled scientific gap

| P | I |
|---|---|
| **High** | **High** |

**The problem.** In arid channels, a large fraction of flood water infiltrates the wadi bed
and never reaches the sea. Kalman et al. (2025) cite measured transmission-loss rates of
**13.2% in an Australian desert stream, up to 98% in parts of Saudi Arabia, and 20–85% in
Nahal Zin in Israel's Negev** **[sourced, verified verbatim]**.

**Why it matters.** The pipeline derives rainfall over a catchment and treats it as a runoff
driver. **Between roughly a fifth and nearly all of that water may never arrive.** The
Negev range — the closest available proxy to Aqaba — spans 20–85%, which is a factor of four.

**Status:** not modelled, not mentioned in `pitch_limitations.md`, not in concept doc §24.

**Mitigation.** It cannot be fixed with better data in two weeks. It can be *stated*, and the
runoff model can be framed as producing **relative ranking between catchments** rather than
absolute runoff volume — which is already how the sediment proxy is framed (§10.4). Add it to
the limitations page.

### R2 · The download box was smaller than the catchment — **now fixed at the contract level**

| P | I | Status |
|---|---|---|
| ~~Certain~~ | ~~High~~ | ✅ **Contract resolved 2026-08-02** — data re-run still outstanding |

**What the risk was.** Mahdi's delineation gives **AQ-C01 (Wadi Yutum) = 4,453 km² ±4%
(range 4,349–4,690)** ([`tasks/mahdi.md`](../../tasks/mahdi.md)) **[sourced]**, and the catchment
layer extends to **35.90°E / 30.03°N**. The old `DOWNLOAD_BBOX` (34.80–35.15 E, 29.25–29.70 N)
covered roughly **1,700 km²** **[derived]** — so **the generating catchment was ~2.6× the entire
area rainfall was downloaded for.**

This was the documented cause of the October 2016 ordering anomaly — the derived rainfall peak
falling *after* the flood arrival, which is physically backwards
([`docs/pipeline_capability_report.md`](../pipeline_capability_report.md) §4.7). Kalman et al.
explicitly name **Wadi Yutum** as one of the two generating catchments
**[sourced, verified verbatim]**.

**What has changed [sourced, measured 2026-08-02].** `backend/src/config/spatial.py` now defines
a two-AOI contract, and the offending box is named in the source as `RETIRED_BOX`:

| Constant | Extent (W, S, E, N) | Area **[derived]** |
|---|---|---|
| `TERRAIN_AOI` | 34.75, 29.15, 35.94, 30.30 | **~14,700 km²** |
| `MARINE_AOI` | 34.80, 29.25, 35.05, 29.60 | ~940 km² |
| `RETIRED_BOX` | 34.80, 29.25, 35.15, 29.70 | ~1,700 km² — **no longer the contract** |

`TERRAIN_AOI` extends to 35.94°E / 30.30°N, so it **contains the full catchment extent**
(35.90°E / 30.03°N) with margin. And it is **guarded, not merely documented** —
`tests/test_spatial_contract.py` includes `test_terrain_reaches_the_full_wadi_yutum_catchment`,
`test_retired_box_is_not_the_contract` and `test_no_source_file_reintroduces_the_retired_box`.

**[judgement]** This is the right fix, done the right way: the mistake became a regression test.

**What remains.** The contract is correct; **the data has not necessarily been re-derived over
it.** Until catchment rainfall is re-run over `TERRAIN_AOI` and the ordering anomaly is shown to
invert, **no causal statement linking rainfall to the flood is defensible** — the constraint is
now a pipeline-run task, not a design flaw. See [`16-build-state.md`](16-build-state.md)
§7 action 1.

### R3 · The test suite has not been run

| P | I | Status |
|---|---|---|
| **Certain** | Medium | ⚠️ **Unchanged — re-confirmed 2026-08-02** |

**258** `def test_` functions now exist across 8 files (up from 247 across 7); **272** passing
tests are reported. **The suite still cannot be executed** — no venv exists and `geopandas`
(re-checked directly), `xarray`, `rasterio`, `earthaccess`, `cdsapi`, `harmony` and `netCDF4`
are all absent **[measured]**. There is still no `pyproject.toml` or `requirements.txt`.

**Mitigation.** One hour of work. Given that "reproducibility from a clean environment" is a
stated evaluation metric (concept doc §22.1), this is the cheapest credibility fix available —
**and it is now the oldest unaddressed item in this register.**

### R4 · Naturally turbid water breaks plume detection elsewhere

| P | I |
|---|---|
| Medium | Medium (High for expansion) |

Oman's corals face **relatively high background turbidity from high ocean phytoplankton
productivity** **[sourced]**. The spectral anomaly method assumes a clear-water baseline.

**Mitigation.** Not an Aqaba risk. Flag it as a known porting cost for the Gulf of Oman.

### R5 · Team dissolution after 13 August

| P | I |
|---|---|
| **High** | **Critical** |

Not a technical risk in the usual sense, but it is the most probable reason this becomes
nothing. Five workstreams, five owners, an academic calendar, and no stated arrangement for
who owns the repository, the relationships, or the ABOFA follow-up.

**Mitigation.** One conversation before the hackathon ends. Costs nothing.

### R6 · Committed credentials

| P | I | Status |
|---|---|---|
| **Certain — already true** | High | ⚠️ **Partly addressed** — untracked, but still in history |

`.env` was tracked on `main` (commit `2f0a6d6`, "chore: add .env with team credentials")
containing Earthdata, CDS, Copernicus Marine and CDSE credentials. Already flagged in
[`docs/MASTER_TASK_SUMMARY.md`](../MASTER_TASK_SUMMARY.md) §20.7 as needing rotation.

**What has changed [measured 2026-08-02].** `.env` has been **deleted from tracking** and
replaced by [`backend/.env.example`](../../backend/.env.example); it is now gitignored.

**What has not changed — and this is the part that matters.** **The credentials are still
recoverable from git history** (`git show 1819b3e:.env`). Removing a file from the tip does not
remove it from the repository. So the exposure is unchanged for anyone who can clone.

**Mitigation, still outstanding.** **Rotate all four credentials** — this is the only step that
actually closes the risk, and it has not been done. History rewrite before the repo is ever made
public. **This remains a commercial risk** — a customer's security review will find it in the
history, and "we removed the file" is not an answer.

---

## 2 · Existing risks, re-scored against the measured build state

| Concept doc risk (§25) | Original | Re-scored | Why changed |
|---|---|---|---|
| Main 2016 scene cloudy/unavailable | Med / High | ⬛ **Materialised — Certain / Critical** | **This risk has landed.** [`docs/event_audit.md`](../event_audit.md) §3 returns NO-GO: the scene is *clear*, but the plume had already dispersed. Worse than the risk as written, because no better scene exists. See §1.5 |
| Ocean currents too coarse | High / High | **High / High** — unchanged | Confirmed: gulf is **14–26 km** wide **[sourced]** vs ~9 km model resolution |
| Too few labelled runoff events | High / Med | **High / High** | Compounded by the imagery null: there may be **no** satellite-labelled event for this coast |
| Team overbuilds full physics | Med / High | **Low / High** | Forecast/current *ingestion* now exists; the simulation engine still does not. Opposite risk still materialised |
| Data downloads fail during demo | Med / High | **Med / High** — unchanged | `--offline-process-only` mode already exists and is proven **[sourced]** |
| Dashboard more important than science | Med / Med | **Low / Med** | No dashboard exists; science is ahead of presentation |
| Judges challenge novelty | Med / Med | **Low / Med** | [`08-prior-art.md`](08-prior-art.md) now answers this with a defensible claim |
| Judges challenge accuracy | High / Med | **High / High** | Raised: R2's contract is fixed but the data re-run is outstanding, **and the satellite validation route is closed**. The honest answer is now the mooring record, which nothing has yet been validated against |

### 1.5 · The gate has resolved, negatively

**[sourced]** The single most important change since the first audit.
[`docs/event_audit.md`](../event_audit.md) §3 records **NO-GO for image-based validation of
October 2016**. The candidate scene (2016-11-02, +5 days) clears cloud and timing but fails the
visual-plume criterion — confirmed by **Sentinel-2 and Landsat 8 independently** — because the
mooring record shows the plume had **dispersed 2.5–3.5 days before either pass**. A **genuine
physical null**, not a data-quality problem, so Silver/Bronze partial labels do not apply.
February 2013 is strictly worse (no Sentinel-2 pre-launch, no Landsat 8 pre-commissioning, only
degraded Landsat 7).

**The pivot [sourced]:** validate against the Kalman et al. mooring record — salinity **−1.75 ‰**,
turbidity peak **2.18 g/L**, 250 m offshore at 13 m depth, onset 09:50 Oct 28, cleared ~17:15
Oct 29.

**[judgement]** Two consequences for this register. First, the top-ranked risk is no longer a
risk — it is a fact to design around. Second, **a new risk replaces it: nothing has been
validated against the mooring record yet**, and that requires the transport engine, which does
not exist. The project has traded an uncertain gate for a concrete dependency.

---

## 3 · The risks that actually matter, in order

**[judgement]** Re-ranked 2026-08-02. The previous top two are closed or resolved; **the list is
now shorter and harder.**

1. **Validate something against the mooring record.** The imagery gate resolved negatively
   (§1.5), so the *only* remaining route to a validated claim runs through the transport engine
   against measured salinity and turbidity. **That engine does not exist**, and it is now the
   critical path for the pitch, the buyers, and the accuracy question. This replaces the old #1.
2. **R5 — team dissolution.** Unchanged, and now relatively more important: it costs nothing to
   mitigate and determines whether any of the rest matters. **Promoted from #3 to #2 by
   default** — the two engineering risks above it got fixed.
3. **R6 — rotate the credentials.** Promoted, because it is the one item where the *appearance*
   of a fix has been mistaken for a fix. The file is untracked; the secrets are still in history
   and still valid.

**Closed since the first pass:** merging `mahdi` (done), the AOI contract (done, with a guard
test), and the imagery gate (answered — negatively). **Still open and cheapest:** R3, the
dependency manifest.

---

## 4 · What to put on the limitations slide

**[judgement]** The project's existing honesty discipline is its strongest asset — 
[`docs/pitch_limitations.md`](../pitch_limitations.md) is genuinely unusual for a hackathon.
Three additions:

- **Transmission loss (R1)** — "between 20% and 85% of a desert flood can infiltrate the wadi
  bed and never reach the sea; we model relative catchment ranking, not absolute volume."
- **No satellite validation for this event (§1.5)** — "the plume dispersed before any accessible
  satellite passed over. We found that ourselves and validate against the published in-situ
  mooring record instead." **This replaces the old R2 line** — the AOI contract is fixed, so the
  honest caveat is now about the validation target, not the bounding box. If the rainfall re-run
  over `TERRAIN_AOI` has not happened by demo day, say that too.
- **The ~11 km IMERG cell vs convective storms** — already in the docs, but it belongs on the
  slide, not just in the repo.
- **AQ-C01's area carries ±4%** (4,349–4,690 km²) — anything reported as a per-catchment *total*
  rather than a *mean* inherits that ([`tasks/mahdi.md`](../../tasks/mahdi.md)).

**[judgement]** Adding a limitation you found yourself is worth more than removing one. The
pitch_limitations page already says this better than I can: *"we would rather show you the
limits of this data than have you discover them for us."*
