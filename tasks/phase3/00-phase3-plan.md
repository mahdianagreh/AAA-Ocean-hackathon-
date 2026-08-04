# Phase 3 — make it true, then make it undeniable

**4 → 13 August 2026. Nine days.** Vertical slice **6 August, two days away.**

Read this, then your own file. Numbers here were measured on 4 Aug against the running
stack, not estimated.

---

## Name it honestly: this is not a fresh phase

Phase 2 built the pieces and they work individually. Phase 3 is **finishing the chain and
turning it into a product**. Budget accordingly — roughly half the window goes to gaps
that already exist, not to new work.

## The outcome, as one testable sentence

> On a clean clone, wifi off, `docker compose up` gives three working views over the real
> Oct 2016 event, where every number traces to a model version and **no term in the
> exposure formula is a stub**.

Today exactly one clause of that is true.

---

## Where the chain actually stands

| # | Stage | State | Owner |
|---|---|---|---|
| 1 | Rainfall | ✅ 27 years, 10,135 days, 675 storms | Karam |
| 2 | Runoff | ✅ 11,810 rows, LOCO AP 0.741 vs 0.200 baseline | Mahdi |
| 3 | **Sediment** | 🔴 **UNANCHORED, index = 0.0** | **Mahdi** |
| 4 | Plume | 🟡 code + render work, `plume_source: SYNTHETIC_STUB` | Abd |
| 5 | Exposure | 🟡 engine works, `formula_terms` stored, score = 0.0 | Pulga |
| 6 | Alert | 🟡 endpoint 200, zero stored runs | Pulga |

**The gap is in the middle, not at the ends.**

## One task gates five

Exposure is a product:

```
plume 0.60  ×  sediment 0.00  ×  duration 0.50  ×  sensitivity 1.00  ×  confidence 0.60  =  0.0
                     ↑
              this is the whole problem
```

The plume genuinely reaches 41 % of R-01 within 12–24 h and the card still reads
`minimal`. Until that term is non-zero: every reef zone reads minimal, the what-if
sliders change nothing visible, the dashboard shows zeros, and `/alerts` has nothing to
alert about.

`sediment_basis` states the fix itself: *"Anchor the proxy at training time on
AQ-2016-10-28 / AQ-C01 (~24,400 t)."* **One number.** Everyone else can work in parallel
because the shapes already exist — but nothing downstream is demonstrable until it lands.

---

## What is already green, and worth not breaking

| | |
|---|---|
| `docker compose up` | healthy in ~8 s, worker starts behind it |
| API | 8/8 GET endpoints 200, plus the two new render endpoints |
| Backend tests | **498 passing** |
| Frontend | builds, 14 tests, feature-complete, on fixtures with a visible `◐` |
| Supabase | 25 tables, matches the files exactly |
| Reef zones | real Allen Coral Atlas, 1.235 km² |
| Prediction imagery | real satellite + real plume, **verified with the network cut** |

## Data still arriving, unattended

| | progress | note |
|---|---|---|
| IMERG half-hourly | 33,920 / 97,200 granules | wettest-first; every day ≥1 mm lands early |
| ERA5-Land months | 108 / 240 | the long pole, pure Copernicus queue |

Both supervised, both resume across network changes, sleep and a new IP. Nothing
re-downloads. **Do not wait for 100 %** — rebuild from whatever is on disk.

---

## What we are deliberately NOT doing

Nine days. Three things working beats seven half-working.

| Cut | Why |
|---|---|
| **True live mode** | Needs a network call on stage, which contradicts DoD "wifi off". Live means *latest cached forecast*. |
| **Backtests as a live endpoint** | Static results panel. It is a finding, not a feature. |
| **Scenario sliders before sediment lands** | A slider that moves a placeholder invites "what is that based on?" |
| **AI-generated imagery in the product** | Hero slide only, labelled. The real render replaced it — see `docs/plume_imagery_decision.md`. |
| **Chasing model score** | Run-to-run variance is ±0.017 AP. Anything under ~0.03 is noise on five folds. |

## Definition of done — Phase 3

1. **No stub term in the exposure formula.**
2. `docker compose up` → three views, clean clone, **wifi off**.
3. Every number on screen traces to a `model_version`.
4. `/alerts` returns real stored runs.
5. Demo rehearsed end to end **at least twice**.
6. **Credentials rotated.**

## Two risks worth saying out loud

**Mahdi is a single point of failure** on the gating task. If sediment has not moved by
end of 5 Aug, Karam takes it.

**Green tests have already coexisted with a dead product.** The suite was 482-green while
`docker compose up` started nothing, because the tests imported the app a different way
than the container does. The only test that counts now is the demo running from a clean
clone with the wifi off.

---

## Files

| | |
|---|---|
| [`01-karam.md`](01-karam.md) | integration, sweeps, rehearsal, credentials |
| [`02-mahdi.md`](02-mahdi.md) | **sediment anchoring — the gate** |
| [`03-nizar.md`](03-nizar.md) | cached forecast, persistence, currents |
| [`04-pulga.md`](04-pulga.md) | alerts, explain/ask, seam vocabularies |
| [`05-abd.md`](05-abd.md) | the real particle engine |
| [`06-ali.md`](06-ali.md) | fixtures → live, three views, plume map |
