# Pulga — Phase 3

Read [`00-phase3-plan.md`](00-phase3-plan.md) first.

Your backend is in better shape than the task list suggests. As of 4 Aug, verified against
the running container: **all 8 GET endpoints answer 200**, `docker compose up` reaches
healthy in ~8 s, the exposure engine produces scores with `formula_terms` stored, and your
43 API contract tests run. Two new render endpoints sit alongside yours.

Three things are left, and one of them is small but blocks a whole screen.

---

## 1 · Seed a stored exposure run — 🟠 small, unblocks `/alerts`

`/api/v1/alerts` returns **200 with nothing in it**, because `exposure_runs.sqlite` has no
rows. Technically healthy, useless on screen, and it looks like a bug to anyone demoing it.

- [ ] Persist at least one run for `AQ-2016-10-28` so the alerts view has real content.
- [ ] Runs must be reconstructable: `formula_terms` **and** `model_versions` stored
      together. A score you cannot rebuild six hours later is a number nobody can defend.

**Watch out — the write path.** `./data` is mounted read-only on purpose and
`exposure.store` writes SQLite, which is why `/alerts` returned a bare 500 until 4 Aug. It
now writes to a named volume via `REEFSHIELD_EXPOSURE_DB=/app/var/exposure_runs.sqlite`.
Do not relax the read-only mount to make a write succeed.

**Watch out — the scores are all 0.0 right now** and that is not your bug. Mahdi's sediment
term is unanchored, and exposure is a product. Seed the run anyway: the shape is what Ali
needs, and the numbers fill in when the anchor lands.

---

## 2 · `/explain` and `/ask` — no LLM key required

Worth stating plainly because it changes the risk: your RAG is **extractive**. It composes
answers from retrieved excerpts and never paraphrases. Your own docstring has it right:

> *"An LLM asked to summarise retrieved text will paraphrase numbers."*

So the assistant **cannot hallucinate a figure**, works fully offline, and needs no key.
`generate_with_llm` is a hook that stays unconfigured. That is a selling point, not a
limitation — say it out loud on the slide.

- [ ] `/explain` returning grounded bilingual paragraphs that invent nothing.
- [ ] `/ask` returning cited answers, citations as a **structured array, never prose**
      (issue #13), in both languages.
- [ ] The corpus is 111 KB of chunks already. `docs/ali/*` is research and pitch material
      and stays **out** of it.

- [ ] Test it adversarially, not just happy-path. Ask it things the corpus cannot answer and
      confirm it refuses rather than reaches.

---

## 3 · Close the seam vocabularies — 🟠 cheap now, expensive on the 12th

I have fixed this exact class of bug **three times in three days**: `sediment_class` had
three spellings across three modules, the runoff model returned different keys than the API
read, and the API imported packages in a way only the tests could resolve. Each one
produced plausible output and no error.

One is still open:

- [ ] **`position_confidence` has two vocabularies** (issue #7). Same shape. Pick one, pin
      it with a test like `tests/test_sediment_class_vocabulary.py`, and make both sides use
      it.

Two smaller ones from the same family:

- [ ] `/api/v1/outlets` returns a **variable key set** (issue #8). A client cannot type
      against a shape that changes per row.
- [ ] Units never baked into value strings (issue #14) — `Value` wrapper with a unit field,
      so Ali never parses `"2.18 g/L"` out of a string.

**The rule worth adopting:** a value that crosses a module boundary is a contract, and it
earns the same discipline as `AQ-C01` or `R-03`.

---

## 4 · Keep the caveats travelling as data

This is already right and it is the thing that most distinguishes the API. `/catchments`
returns `position_confidence` and `caveat` per row, including the AQ-O04 harbour warning.
Keep it that way as you add endpoints.

Four caveats that must reach the screen, not a doc:

| | |
|---|---|
| `AQ-O04` | discharges into an **enclosed harbour basin**; 427 m outside the sea polygon |
| `sensitivity_weight` | **1.0 placeholder**, `PLACEHOLDER_PENDING_MARINE_SCIENTIST` |
| `predicted_runoff_m3` | **`None`** — Component A predicts occurrence, not volume. A gap, never a zero |
| `depth_median_m` | can be **`NaN`** (R-02 has no water cell under a 5 m reef strip at 50 m bathymetry) |

---

## Definition of done

1. `/alerts` returns real stored runs with `formula_terms` and `model_versions`.
2. `/explain` and `/ask` live, bilingual, citations structured, refusing rather than guessing.
3. `position_confidence` single vocabulary, pinned by a test.
4. Every caveat above travels in the payload.
5. Your contract tests still green after all of it.

## What you depend on

| From | What | Blocked? |
|---|---|---|
| **Mahdi** | anchored sediment | Only for the *numbers*. Seed the run now — the shape is what Ali needs |
| **Abd** | real plume contours | No — the stub has the right shape |
| **Nizar** | Postgres persistence | No — SQLite via the named volume works today |
