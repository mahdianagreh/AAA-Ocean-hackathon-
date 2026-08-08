# Phase 7 — Ali

**Owns:** the design system, the shell, routing, i18n, accessibility, offline mode,
the marketing pages — and final visual review of everyone else's screens.
**Pages:** `/`, `/login`, `/signup`, `/limitations`, `/account`, 404, plus the chrome
every other page sits inside.
**Rows:** `p4-13`, `p4-18`, `p4-19`, `p4-H` (with Mahdi), and the **cross-cutting
gates on all 44**.

Read [`00-phase7-plan.md`](00-phase7-plan.md) and
[`00-design-system.md`](00-design-system.md) first — you are the custodian of the
second one.

**Your role changed this phase.** In Phases 4–6 you owned the frontend half of every
row, which made you the bottleneck and left 30 rows untested. Now each person builds
the screen for their own domain, and you own the system they build inside plus the
right to reject anything that breaks it.

---

## The brand you are enforcing

```
grounds   bg-canvas  bg-surface  bg-surface-2   borders  border-hairline
ink       text-ink   text-ink-2  text-ink-3     accent   text-accent
hazard    BAND_CLASS from src/api/types.ts
brand     brand-gradient utility · var(--brand-navy) · var(--brand-aqua) · var(--brand-foam)
```

Deep Navy `#0A1F4D` · Ocean Blue `#0D3D7A` · Marine Teal `#007A99` · Aqua `#00B7C3`
· Foam White `#E6F7FA` · Dark `#09111F` · Slate `#46566D` · Border `#DCE5EC` ·
Surface `#F4F7FA`. Montserrat 400/600/700 (Latin only — Arabic is IBM Plex Sans
Arabic because Montserrat has no Arabic coverage). Radii 2/8/12/16/20. Shadows
sm/md/lg keyed to `rgb(10 31 77)`. 8-point grid.

---

## Cross-cutting gates — you hold these for the whole team

Run these before every merge. A red gate blocks the merge, whoever wrote the code.

```bash
cd frontend && npm run qa          # tsc + oxlint + stylelint + vitest
npx playwright test                # 7 suites + the rebrand smoke walk
python3 scripts/qa_frontend_tokens.py   # hex literals, token coverage
python3 scripts/qa_frontend_rtl.py      # logical properties, rtl-ok exemptions
python3 scripts/qa_frontend_docs.py     # doc claims vs measured values
python3 scripts/qa_frontend_freeze.py
grep -ril "reefshield" frontend/        # must return nothing
```

- [ ] **Token discipline.** No hex literals. Every `token-ok:` exemption gets reviewed
      by you, and the reason has to be "fixed brand artwork" or "reads against
      photography" — not "the token looked wrong here".
- [ ] **`--ink-3` never on `--surface-2`.** It measures 4.17 in dark theme and axe
      fails the build. This has already shipped once, on the masthead badge.
- [ ] **i18n parity.** Four namespaces — `common`, `nav`, `pages`, `tools` — currently
      736 keys at exact EN/AR parity, with matching interpolation variables. A key
      added to one locale only is a merge blocker.
- [ ] **The `data-*` contract.** Seven specs target `[data-chrome]`, `[data-mode=…]`,
      `[data-open-overlay=…]`, `[data-risk-card]`, `[data-band]`, `[data-legend-band]`,
      `[data-time-handle]`, `[data-missing]`, `[data-state]`, `[data-provenance]`, and
      named map layer IDs. **Restyle freely, rename nothing.**
- [ ] **The untranslated-key walk.** `tests/rebrand-smoke.spec.ts` asserts no raw i18n
      key reaches the DOM in either language. A missing translation does not throw —
      i18next renders the key — so this test is the only thing that catches it.
      **Extend it as pages grow.**
- [ ] **Every number through `<ValueWithUnit>`.** It is the single numeric funnel:
      bidi isolation, tabular figures, provenance as border form, null-as-gap. Four
      integrity tests depend on it.

---

## Your rows

### `p4-13` Honest Limits — `/limitations`

The page renders. It is the most important page in the product and it is thin.

- [ ] Render `docs/pitch_limitations.md` and `docs/forcing_limitations.md` in full.
- [ ] Every uncomfortable fact stated plainly, including: soil is a global model not a
      local measurement; `sensitivity_weight` is an unreviewed 1.0 placeholder;
      bathymetry resolution limits; the reef-zone width assumption; land-cover snapshot
      year vs event year; wind forcing permanently zero.
- [ ] Collect the four **Absent** features from Mahdi (`b1`, `b2`, `b3`, `b9`) and give
      each one a sentence. This is where absent things live.
- [ ] Keep the "Arabic pending" marker where a source document has no translation.
      **Do not machine-translate a source document and present it as the source.**
- [ ] ⚠️ If you regenerate `public/fixtures/limitations.json`, you inherit unrelated
      doc drift — it moves 9 items to 12 and breaks a scene-walk assertion. Own the
      diff and update the spec deliberately, or leave the fixture alone.

### `p4-19` One-Line Mission · `p4-18` Toughest Coral Fact — `/`

- [ ] `p4-19` is **Done** — the hero carries it in both languages. Do not regress it.
- [ ] `p4-18` is not started: one sourced fact about Gulf of Aqaba thermal resilience,
      with its citation. **Sourced** — no folklore, no rounded-up superlative.

### `p4-H` Offline Emergency Mode — with Mahdi

- [ ] ⚠️ **`offline-arabic.spec.ts` "no external requests" fails today.** Three real
      backend calls fire during a plain pan/zoom on the main map. Confirmed unrelated
      to terrain work via `git stash` isolation in Phase 4, and **unowned since**.
      It is yours now. Either gate those calls behind the data-source mode or accept
      and document them.
- [ ] The physical wifi-off run — a person, not a spec. Sign it with a date.
- [ ] Everything under `public/` is committed on purpose: basemap GeoJSON, six woff2
      faces plus three Montserrat faces, the vendored MapLibre RTL plugin. **No
      frontend asset may be fetched at runtime.** Reject any PR that adds one.

### Auth — the standing gap

There is **no authentication of any kind**: no accounts, no sessions, no user model,
and every mutating endpoint is open.

- [ ] `/login` renders a permanent notice saying so and does **not** fake a session.
      Keep it that way — the temptation to "just navigate to /dashboard on submit" is
      exactly the failure this guards against.
- [ ] `/signup` keeps its local confirmation and states the request is not transmitted.
- [ ] `/account` shows preferences, not a profile.
- [ ] If auth is ever built, it is a backend change first. Do not simulate it.

---

## The shell work that makes the whole thing feel finished

- [ ] **Route titles.** `DashboardChrome` currently shows `Overview` on every page
      because the masthead title is hard-wired. Drive it from the route.
- [ ] **Mobile.** The rail collapses at `lg`, but no page below has been checked on a
      narrow viewport. Do a pass.
- [ ] **Loading and error states** for every page, using `States.tsx`. Three visually
      distinct states, each explaining itself. A spinner is not a state.
- [ ] **Focus management** across route changes — move focus to the page heading, or
      keyboard users land nowhere.
- [ ] **The five overlays keep working** from the map screen *and* have routes. Do not
      delete `OverlayHost` in favour of routes; a judge mid-demo should not have to
      leave the map to check provenance.
- [ ] **Persistent assistant surface.** The plan asks for the assistant reachable from
      every dashboard page, not only `/assistant`.

---

## Final review checklist — you sign this, not the person who wrote the page

For each of the 44 rows, before it may be marked Done in
[`00-feature-surface-matrix.md`](00-feature-surface-matrix.md):

- [ ] Uses only shared components — `PageShell`, `Card`, `Segmented`, `Logo`, `Link`,
      `ValueWithUnit`. No page-local re-implementations.
- [ ] No hardcoded value that the API could supply.
- [ ] Renders its `caveats[]` and any `*_status` placeholder flag.
- [ ] Three states present and distinguishable.
- [ ] Arabic checked by eye, not only by the parity script — RTL layout, LTR numerals.
- [ ] axe clean in all four theme × language combinations.
- [ ] Screenshot filed under `tasks/phase7/evidence/<route>/`.

**You may return a row.** A returned row goes back to its owner with the specific gate
it failed. That is the mechanism that stops Phase 7 from producing eleven pages that
look like eleven products — and it is why this role exists.
