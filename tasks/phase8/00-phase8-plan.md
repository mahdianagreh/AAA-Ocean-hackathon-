# Phase 8 — Design Perfection (every page except the Dashboard)

**Project:** AQABA AQUA AI
**Written:** 9 August 2026
**Window:** 9 Aug → 13 Aug 2026, the last days before presenting.

Phase 7 gave every feature a real surface wired to a real endpoint. Phase 8 makes
each of those surfaces look **finished** and read **clearly**. That is the entire
scope.

> **This is a design and clarity phase only.** No new features, no new data, no new
> endpoints except the two narrow backend items explicitly listed (Page 5's PDF
> question, Page 11's cache-stat rendering). If you notice something else worth
> improving, write it at the end of your report as a suggestion — **do not act on it
> inside this phase.**

The Dashboard is **out of scope**. It landed its own premium pass in commit `0c335af`
and is the reference the other twelve pages are being brought up to.

---

## The twelve pages, and who owns each

Every page is assigned to the person who owns the **underlying data or feature**, plus
**Ali**, who implements the actual UI on every page in this phase. The domain owner's
job is to confirm their page's content is accurately and completely represented in the
redesign. They are not expected to write frontend code unless they already do.

| # | Page | Route / file | Domain owner | Implementation |
|---|---|---|---|---|
| 1 | Storm Replay | [ReplayPage.tsx](../../frontend/src/routes/ReplayPage.tsx) | **Abd** | Ali |
| 2 | Reef Zones (index) | [ReefZonesPage.tsx](../../frontend/src/routes/ReefZonesPage.tsx) | **Pulga** | Ali |
| 3 | Reef Zone detail — Caveats | [ReefZonePage.tsx](../../frontend/src/routes/ReefZonePage.tsx) | **Pulga** | Ali |
| 4 | Alerts | [AlertsPage.tsx](../../frontend/src/routes/AlertsPage.tsx) | **Pulga** | Ali |
| 5 | Reports | [ReportsPage.tsx](../../frontend/src/routes/ReportsPage.tsx) | **Pulga** | Ali |
| 6 | Explain / Ask (Assistant) | [AssistantPage.tsx](../../frontend/src/routes/AssistantPage.tsx) | **Pulga** | Ali |
| 7 | Validation | [ValidationPage.tsx](../../frontend/src/routes/ValidationPage.tsx) | **Abd** | Ali |
| 8 | Provenance | [ProvenancePage.tsx](../../frontend/src/routes/ProvenancePage.tsx) | **Karam** | Ali |
| 9 | Site Scoring | [SiteScorePage.tsx](../../frontend/src/routes/SiteScorePage.tsx) | **Karam** (content) + **Pulga** (backend) | Ali |
| 10 | Honest Limits | [LimitationsPage.tsx](../../frontend/src/routes/LimitationsPage.tsx) | **Mahdi** (content) + **Pulga** (limitations docs) | Ali |
| 11 | System Health & Diagnostics | [SystemHealthPage.tsx](../../frontend/src/routes/SystemHealthPage.tsx) | **Nizar** | Ali |
| 12 | Data Explorer | [DataExplorerPage.tsx](../../frontend/src/routes/DataExplorerPage.tsx) | **Karam** | Ali |
| 13 | Sign in | [Login.tsx](../../frontend/src/routes/Login.tsx) | **Nizar** | **Nizar** |
| 14 | Request access | [Signup.tsx](../../frontend/src/routes/Signup.tsx) | **Nizar** | **Nizar** |

**Pages 13 and 14 are the one amendment to this phase.** They were added at the team's
request after the plan was first written, and unlike the other twelve they carry **real
new functionality** — authentication — which the original scope rule excludes. They are
therefore a deliberate, authorized expansion, and they are **Nizar's end to end**: he
owns Supabase, so he owns the identity layer, the screens in front of it, and the
honesty of what those screens claim. Ali holds the design-system gates on them, the
same as everywhere else, but does not implement them. See [`05-nizar.md`](05-nizar.md),
where they are split into a design track that is in Phase 8's original scope and a
functionality track that is not.

Per-person files, each **self-contained** — open only your own file and you know
exactly which pages, which sections and which buttons you are responsible for:

- [`01-ali.md`](01-ali.md) — the full implementation checklist for **Pages 1–12**, plus
  the cross-cutting gates on 13 and 14
- [`02-pulga.md`](02-pulga.md) — Pages 3, 4, 5, 6, 9 (backend), 10 (backend)
- [`03-mahdi.md`](03-mahdi.md) — Page 10
- [`04-karam.md`](04-karam.md) — Pages 8, 9 (content), 12
- [`05-nizar.md`](05-nizar.md) — Pages 11, 13, 14
- [`06-abd.md`](06-abd.md) — Pages 1, 7

---

## Global rules — apply to every page, regardless of owner

1. **Every wall of plain paragraph text becomes structured content** — cards,
   accordions, badges, icons, or a table.
2. **Every caveat block gets one consistent treatment:** icon (⚠ Warning / ℹ Note) +
   bold headline + explanation + source shown as a **small pill**, never as plain
   inline gray text.
3. **Repeated, near-identical caveats are grouped into one card**, never repeated
   separately.
4. **No raw internal field names visible to the user.** `sites.criterion.C1` becomes
   "Ephemeral drainage"; the raw key survives only as small secondary detail.
5. **No page may render `[object Object]`** or any other unserialized raw value
   anywhere.
6. **Fix data/asset dependencies where genuinely possible; where not, flag it
   explicitly rather than styling around it.** The Storm Replay basemap is the known
   case.

## Standing law carried over from Phase 7 — still in force

These are not restated in every per-person file. They apply to every line of code
written in this phase.

1. **No hex literals, no ad-hoc colour, no second design system.** Everything comes
   from the tokens in [`../phase7/00-design-system.md`](../phase7/00-design-system.md).
   `python3 scripts/qa_frontend_tokens.py` must exit 0 before you push.
2. **A number on screen comes from the API or it does not go on screen.** Phase 8 adds
   no numbers. If a redesign needs a value the endpoint does not return, render the
   honest empty state.
3. **Missing is never zero.** A null renders as a visible gap through `ValueWithUnit`.
4. **Every caveat the API sends must render.** Phase 8 regroups and restyles caveats.
   It **deletes none of them**, and it changes **no word of their content**.
5. **Bilingual in the same commit.** EN and AR keys land together; `common`, `nav`,
   `pages`, `tools` stay at exact parity. Every new accordion, pill, tooltip and
   button label in this phase is a new key pair.
6. **`--ink-3` is for text on `--canvas` and `--surface` only** — never on
   `--surface-2`. It measures 4.17 in dark theme and axe fails the build.
7. **No row is Done without a screenshot**, light and dark, EN and AR.

## The gates

```bash
cd frontend && npm run qa               # tsc + oxlint + stylelint + vitest
npx playwright test                     # 7 suites + the rebrand smoke walk
python3 scripts/qa_frontend_tokens.py   # hex literals, token coverage
python3 scripts/qa_frontend_rtl.py      # logical properties, rtl-ok exemptions
python3 scripts/qa_frontend_docs.py     # doc claims vs measured values
```

---

## Two content discrepancies found while writing this plan — resolve, do not paper over

**(a) Page 10 says "9 things our data cannot tell you". The source document has 12.**
[`docs/pitch_limitations.md`](../../docs/pitch_limitations.md) carries twelve numbered
sections (§1–§12), not nine. Before the accordion is built, Mahdi and Pulga must
settle whether the page renders 9 of 12 by design or whether the count has drifted.
Building a 9-item accordion over a 12-item source would silently drop three real
limitations — exactly the failure this project exists to avoid. **The accordion item
count follows the source document, whatever the header currently says.**

**(c) Pages 13 and 14 rest on a claim that must not be styled away.** Both auth screens
carry a permanent, non-dismissible notice stating there is no authentication backend —
because there genuinely is none: the API exposes no `/login`, `/token`, `/session` or
`/users/me`. The notice, the disabled SSO button, the sign-in status line and Signup's
"this request was not transmitted" paragraph are one interlocked set of honest claims.
**A design pass never removes them.** They come down together, in one commit, only when
a real session genuinely works — the eight-item gate is in [`05-nizar.md`](05-nizar.md).

**(b) Page 3's grouped bathymetry card must not invent percentages.** The per-zone
land-cell percentages are computed at request time in
[`backend/src/api/caveats.py:148`](../../backend/src/api/caveats.py#L148)
(`depth_is_land_dominated`), not hard-coded. The grouped card must render the values
the API actually returns for each zone in the group, and R-02's "no water cell at all"
case is a **different caveat branch** (`depth_median is None`) — it cannot be folded
into a percentage list. See [`02-pulga.md`](02-pulga.md).

---

## Definition of done

1. All 12 pages pass visual review against the theme tokens — no unstyled defaults, no
   raw internal field names, no `[object Object]` anywhere.
2. Every wall-of-text caveat section is restructured into cards per the Global Rules.
3. Honest Limits' numbered list is a working accordion.
4. Site Scoring's criteria list is a real scorecard component.
5. The Assistant page's answer container has a fixed, comfortable reading width.
6. Reports have a working themed PDF download.
7. The Storm Replay basemap gap is explicitly flagged, not silently styled around.
8. Every per-person file is self-contained and specific — exact pages, exact sections,
   exact buttons, no cross-references and no summaries.

## What the final report must contain

- Per-page completion status for all 12 pages.
- Confirmation of the `[object Object]` fix **and its root cause**.
- Confirmation of the PDF export working end to end.
- Confirmation that all six per-person files are genuinely self-contained.
- A closing **Suggestions** section for anything noticed but deliberately not acted on.
