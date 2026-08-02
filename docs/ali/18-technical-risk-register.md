# 18 · Technical — Risk register

**Part D. Scientific and engineering risks, scored, with the ones the project has not yet
written down flagged.**

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

### R2 · The download box is smaller than the catchment

| P | I |
|---|---|
| **Certain — already true** | **High** |

Mahdi's delineation on branch `mahdi` gives **AQ-C01 (Wadi Yutum) = 4,453 km²**, and the
catchment layer extends to **35.90°E / 30.03°N**. The contract's `DOWNLOAD_BBOX`
(34.80–35.15 E, 29.25–29.70 N) covers roughly **1,700 km²** **[derived]**.

**The generating catchment is ~2.6× the entire area rainfall was downloaded for.**

This is the documented cause of the October 2016 ordering anomaly — the derived rainfall peak
falls *after* the flood arrival, which is physically backwards
([`docs/pipeline_capability_report.md`](../pipeline_capability_report.md) §4.7 lists it as
unresolved). This research confirms the hypothesis: Kalman et al. explicitly name **Wadi
Yutum** as one of the two catchments that generated the event **[sourced, verified verbatim]**.

**Mitigation.** Re-download IMERG over the expanded terrain AOI before making any
catchment-level rainfall claim. **Until then, no causal statement linking rainfall to the
flood is defensible.**

### R3 · The test suite has not been run

| P | I |
|---|---|
| **Certain** | Medium |

247 `def test_` functions exist; 272 passing tests are reported. **The suite cannot currently
be executed** — no venv exists and `xarray`, `geopandas`, `rasterio`, `earthaccess`,
`cdsapi`, `harmony` and `netCDF4` are all absent **[measured]**. There is no
`pyproject.toml` or `requirements.txt`.

**Mitigation.** One hour of work. Given that "reproducibility from a clean environment" is a
stated evaluation metric (concept doc §22.1), this is the cheapest credibility fix available.

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

| P | I |
|---|---|
| **Certain — already true** | High |

`.env` is tracked on `main` (commit `2f0a6d6`, "chore: add .env with team credentials")
containing Earthdata, CDS, Copernicus Marine and CDSE credentials. Already flagged in
[`docs/MASTER_TASK_SUMMARY.md`](../MASTER_TASK_SUMMARY.md) §20.7 as needing rotation.

**Mitigation.** Rotate all four; `git rm --cached .env`; history rewrite if the repo is ever
made public. **Note this is a commercial risk too** — a customer's security review will find
it in the git history.

---

## 2 · Existing risks, re-scored against the measured build state

| Concept doc risk (§25) | Original | Re-scored | Why changed |
|---|---|---|---|
| Main 2016 scene cloudy/unavailable | Med / High | **Med / Critical** | Now gates every *buyer* too, not just validation — see [`12-business-buyers-and-value.md`](12-business-buyers-and-value.md) §6 |
| Ocean currents too coarse | High / High | **High / High** — unchanged | Confirmed: gulf is **14–26 km** wide **[sourced]** vs ~9 km model resolution |
| Too few labelled runoff events | High / Med | **High / High** | Compounded by R2: the labels derived so far used the wrong rainfall area |
| Team overbuilds full physics | Med / High | **Low / High** | No simulation code exists at all — the opposite risk has materialised |
| Data downloads fail during demo | Med / High | **Med / High** — unchanged | `--offline-process-only` mode already exists and is proven **[sourced]** |
| Dashboard more important than science | Med / Med | **Low / Med** | No dashboard exists; science is ahead of presentation |
| Judges challenge novelty | Med / Med | **Low / Med** | [`08-prior-art.md`](08-prior-art.md) now answers this with a defensible claim |
| Judges challenge accuracy | High / Med | **High / Med** — unchanged | Answer is baselines + honest metrics, which requires R2 and the imagery gate resolved |

---

## 3 · The risks that actually matter, in order

**[judgement]** If only three things get attention:

1. **The imagery gate (Abd's audit).** Unanswered on day 4 despite the contract moving it to
   day 2. It gates validation, and validation gates every buyer conversation. If it fails,
   the honest response is to reposition around forecast capability — but that decision needs
   eleven days, not two.
2. **R2 — the download box.** Every catchment-level rainfall number produced so far is
   computed over an area that excludes most of the generating catchment. Merging `mahdi` and
   re-downloading is mechanical work that makes the difference between a defensible claim and
   an indefensible one.
3. **R5 — team dissolution.** Costs nothing to mitigate and determines whether any of the
   rest matters.

---

## 4 · What to put on the limitations slide

**[judgement]** The project's existing honesty discipline is its strongest asset — 
[`docs/pitch_limitations.md`](../pitch_limitations.md) is genuinely unusual for a hackathon.
Three additions:

- **Transmission loss (R1)** — "between 20% and 85% of a desert flood can infiltrate the wadi
  bed and never reach the sea; we model relative catchment ranking, not absolute volume."
- **Catchment vs download extent (R2)** — state it if unresolved by demo day, rather than
  presenting a rainfall-to-flood causal chain that the ordering contradicts.
- **The ~11 km IMERG cell vs convective storms** — already in the docs, but it belongs on the
  slide, not just in the repo.

**[judgement]** Adding a limitation you found yourself is worth more than removing one. The
pitch_limitations page already says this better than I can: *"we would rather show you the
limits of this data than have you discover them for us."*
