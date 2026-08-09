# Phase 8 — Nizar

**Your pages this phase:**

| # | Page | Route | Your role |
|---|---|---|---|
| 11 | System Health & Diagnostics | `/system` | content accuracy; **Ali** implements |
| 13 | Sign in | `/login` | **content + backend + frontend — all yours** |
| 14 | Request access | `/signup` | **content + backend + frontend — all yours** |

Page 11 carries the only outright **rendering bug** in the phase. Pages 13 and 14 are
**auth, and they are yours end to end** — you own Supabase, so you own the identity
layer that sits on it, the screens in front of it, and the honesty of what those
screens claim.

**Scope note, stated once.** Phase 8 as written is a design-and-clarity phase — *no new
features, no new endpoints*. Pages 13 and 14 were added at the team's request and
**build real functionality**, so they are a deliberate, authorized expansion of this
phase, not an exception someone slipped in. They are split below into a **Track A
(design)** that is unambiguously in Phase 8's original scope and safe to ship on its
own, and a **Track B (functionality)** that is the new work. **Track A must not wait on
Track B**, and Track B has one hard gate described below that is not negotiable.

Everything else you notice goes in the final report as a suggestion — do not act on it
inside this phase.

---

## What Ali is building on this page

- [ ] **Fix the `[object Object]` rendering bug.** "Memory & Cache Stats" currently
      shows literally `[object Object]` for both **"Plume"** and **"Exposure"** instead
      of real cache statistics. Locate where this object is interpolated directly
      instead of having its actual fields extracted and displayed, fix the rendering
      logic, then style the corrected output.
- [ ] **Redesign "Artifact Availability"** from a flat two-column list into **grouped,
      categorized status cards** (e.g. "Terrain & Hydrology": catchments, outlets,
      coastline; "Marine": reef_zones, bathymetry — grouped logically by what each
      artifact actually is), with a **consistent status badge per item**.
- [ ] **Keep the "Overall Health" OK badge treatment**, confirming it matches the final
      theme pass.

---

## Your specific responsibility on this page

**Identify the actual fields inside the Plume and Exposure cache objects — size, entry
count, last updated, hit rate, whatever the cache object genuinely contains — so Ali
can render real values instead of `[object Object]`, and confirm the artifact-grouping
categories used in the redesign match the real data sources this system actually
tracks.**

---

### 1. The cache fields — the bug is already traced, confirm the fix

**Root cause, located.**
[`SystemHealthPage.tsx:85`](../../frontend/src/routes/SystemHealthPage.tsx#L85) renders

```tsx
{typeof value === 'number' ? value.toLocaleString() : String(value)}
```

while iterating `Object.entries(cacheStats)`. But
[`GET /api/v1/cache-stats`](../../backend/src/api/main.py#L2031) returns

```python
{"plume": da.PLUME_CACHE.stats(), "exposure": da.EXPOSURE_CACHE.stats()}
```

and `TTLCache.stats()`
([`data_access.py:855`](../../backend/src/api/data_access.py#L855)) returns

```python
{"hits": self.hits, "misses": self.misses, "size": len(self._store)}
```

So each top-level value is a **dict, not a scalar**, and `String({…})` evaluates to
`"[object Object]"`. Two objects in, two `[object Object]`s out. It is a one-level
nesting the renderer never expected.

**What you confirm:**

- [ ] **The field list is exactly three: `hits`, `misses`, `size`.** Confirm that is
      still what `TTLCache.stats()` returns, and that neither cache overrides it.
- [ ] **What each field means in plain language**, for the labels Ali writes:
      - `hits` — requests served from cache
      - `misses` — requests that had to be computed
      - `size` — **entries currently held**, not bytes. Confirm this, because "size"
        will be read as memory by anyone looking at a page titled *Memory & Cache
        Stats*. If it is an entry count, the label must say **Entries**, not Size.
- [ ] **What is genuinely absent.** There is **no** `last_updated` and **no** stored
      `hit_rate` on the object. Confirm that. If Ali shows a hit rate it is
      `hits / (hits + misses)` **computed in the component**, and it must be labelled as
      derived — source vs derived is a project rule and it does not stop at the API
      boundary. Confirm what it should display when `hits + misses == 0`: a gap, never
      `0 %`, because zero traffic is not a zero hit rate.
- [ ] **The TTL is context the number needs.** Both caches are `TTLCache(ttl_seconds=1800)`.
      Confirm whether the 30-minute TTL should appear on the card — an entry count with
      no TTL beside it reads as a permanent total.
- [ ] **The frontend type must stop being `Record<string, unknown>`.**
      [`live.ts:508`](../../frontend/src/api/live.ts#L508) types this response as
      `Record<string, unknown>`, which is exactly why the compiler let `String(value)`
      through. Confirm the concrete shape so Ali can declare it — a real interface makes
      this class of bug a build failure instead of a screen full of
      `[object Object]`.
- [ ] **Check for the same pattern elsewhere.** Any other place in the UI that iterates
      an API object with `String(value)` will fail identically the moment a nested value
      appears. Worth one grep; report what you find.

---

### 2. The artifact grouping — must match what the system actually tracks

The list is not free-form. It comes from `ARTIFACTS` in
[`data_access.py:31`](../../backend/src/api/data_access.py#L31), surfaced through
`artifact_status()` as `HealthOut.artifacts_present: Record<string, boolean>`. The
**real keys today** are:

`catchments` · `outlets` · `coastline` · `reef_zones` · `reef_zones_provisional` ·
`bathymetry` · `landcover` · `soil` · `urban` · `rainfall_climatology` ·
`rainfall_daily` · `seasonal_risk_calendar` · `event_catalogue` · `event_dates` ·
`forecast_snapshot` · `data_dictionary` · `osm_buildings` · `osm_drainage`

**What you confirm:**

- [ ] **The grouping, item by item.** Assign every one of the keys above to a group and
      hand Ali the finished mapping. A starting shape, for you to correct rather than
      accept:

      | group | keys |
      |---|---|
      | Terrain & Hydrology | `catchments`, `outlets`, `coastline` |
      | Marine | `reef_zones`, `reef_zones_provisional`, `bathymetry` |
      | Catchment features | `landcover`, `soil`, `urban` |
      | Rainfall & Events | `rainfall_climatology`, `rainfall_daily`, `seasonal_risk_calendar`, `event_catalogue`, `event_dates` |
      | Forecast | `forecast_snapshot` |
      | Reference & OSM | `data_dictionary`, `osm_buildings`, `osm_drainage` |

      **Every key lands in exactly one group.** A key with no group vanishes from the
      redesigned page — an artifact that silently stops being monitored is worse than an
      ugly flat list.
- [ ] **`osm_buildings` and `osm_drainage` point at the same file** (`osm_aqaba.gpkg`),
      so they are always present or absent together. Decide whether they show as two
      rows or one, and make sure the page does not imply two independent checks where
      there is one file.
- [ ] **`reef_zones` vs `reef_zones_provisional` need explicit treatment.** `reef_zones`
      absent is a **known degraded state**, not a failure — the health endpoint already
      emits the reason: *the Allen Coral Atlas export is blocked on Earth Engine browser
      authentication, so `reef_zones_PROVISIONAL.gpkg` is being served.* Confirm the
      redesigned card shows the substitution rather than a bare red dot, and that
      **PROVISIONAL stays visible in the label** — the Day-12 gate is a
      `grep -ri PROVISIONAL` and a UI that drops the suffix defeats it.
- [ ] **Plain-language group names, raw key as secondary detail.** Global Rule 4 says no
      raw internal field names as headlines — but an operator needs `landcover_by_catchment.parquet`
      to know which file to go fix. Confirm the display name for each key, with the raw
      key kept as small secondary text.
- [ ] **The status badge is three-state, not two.** `artifacts_present` is a boolean, but
      the page's meaning is not: **present**, **absent and that degrades the system**
      (`degraded_reason` names it), and **absent but expected** (git-ignored raw data —
      the test suite skips 47 tests for exactly this reason). Confirm which keys fall in
      the third bucket, so a normal dev machine does not light up red for files that were
      never meant to be committed.
- [ ] **`degraded_reason[]` keeps rendering in full.** It is the sentence that explains
      the red dot. Confirm nothing in the regrouping drops it.
- [ ] **Confirm the OK badge's logic is unchanged.** `status` is `"ok"` only when
      `degraded_reason` is empty — note that a missing `landcover`/`soil`/`urban`
      *does* degrade, while a missing `bathymetry` currently does **not** produce a
      reason. Confirm that is intended; if it is not, that is a finding to report, not a
      change to make in this phase.

---

---
---

# PAGES 13 & 14 — Sign in and Request access

`frontend/src/routes/Login.tsx` · route `/login`
`frontend/src/routes/Signup.tsx` · route `/signup`

**These two are yours end to end** — the content, the backend, and the frontend. You
own Supabase, and auth is the one feature where the database, the session and the
screen cannot be owned by different people without something quietly breaking.

**Ali does not implement these two.** He holds the cross-cutting gates on them —
tokens, i18n parity, RTL, axe — the same as on every other screen, and he can reject a
merge that breaks the design system. The code is yours.

## Read this before you touch either file

**There is no authentication backend today, and that is a documented decision, not an
oversight.** Both files open with a docstring stating it in full. Paraphrasing loses
the point, so here it is as written in
[`Login.tsx:7`](../../frontend/src/routes/Login.tsx#L7):

> *THERE IS NO AUTHENTICATION BACKEND. Not "not wired up yet": the API exposes no
> /login, /token, /session or /users/me, and no middleware reads a credential. So this
> screen does exactly what the canvas designed it to do — validate its own fields
> locally — and nothing more. It does not set a session, it does not navigate to
> /dashboard, and it does not pretend a correct-looking email and password mean
> anything.*
>
> *A form that silently accepts input and lands you on a dashboard is worse than no
> form: it teaches everyone downstream that sign-in works.*

`Signup.tsx` carries the matching constraint: there is no intake endpoint either,
nothing typed there leaves the browser, and the "Request received" screen says plainly
that the request **was not transmitted** — because *a confirmation that implies a human
will read it, when nothing was sent, is the same failure as a fake login wearing a
friendlier face.*

**The consequence for you, and it is the single most important line in this file:**

> **The permanent notice comes down if and only if auth genuinely works.** Not when the
> Supabase project exists. Not when the client library is installed. Not when the
> happy path works on your machine. The notice, the disabled SSO button, the
> `unavailableStatus` line and the `notTransmitted` paragraph are one interlocked set
> of honest claims. **Remove any of them early and the product tells its first lie**,
> on the first screen a judge sees. They are removed together, in one commit, behind a
> real session — or they all stay.

A styling pass **never** removes them. That is Track A's hard constraint.

---

## TRACK A — Design perfection (in Phase 8's original scope, ship this regardless)

This is the part that is unambiguously a Phase 8 task: make both screens look finished,
change no claim. Do this first and completely. It stands on its own even if Track B
does not land before the 13th.

The two screens are already in good shape — real `useId()` wiring, `aria-invalid`,
`aria-describedby`, `role="status"` with `aria-live="polite"`, text-not-colour-alone
errors, logical properties (`pe-12`, `end-1`) for RTL. **Do not regress any of that.**
What follows is polish on top.

### Shared across both screens

- [ ] **Lift the ad-hoc `FIELD` constant into the shared input component.** Both files
      declare their own local
      `const FIELD = 'h-12 w-full rounded-md border bg-surface px-4 …'`. That is the
      48 px foundation input duplicated by hand in two places — the same standard Ali
      is applying to the Assistant page's input and the Site Scoring form. One shared
      component, used by both auth screens and those pages. **A third hand-rolled copy
      is how a design system dies.**
- [ ] **Style the submit button to the primary-button standard.** Both are currently
      `bg-ink text-ink-inverse` typed inline. Same component as every other primary
      action in the phase.
- [ ] **Give the permanent notice the phase's caveat treatment** — the shared
      `CaveatCard`: **ℹ icon + bold headline + explanation + source pill**. It is
      currently a bare `border-hairline-2 bg-surface-2` box, which reads as a hint. It
      is not a hint, it is the most important sentence on the page. **Restyle it up,
      never down, and keep it non-dismissible.**
- [ ] **Error message treatment.** Errors currently render as `text-ink` with a
      `t('auth.errors.prefix')` word in front — correct behaviour (text, not colour
      alone), plain presentation. Give them the theme's inline-error style **while
      keeping the text prefix**. Removing the prefix to rely on a red border would fail
      the same colour-blind rule the file's comment at
      [`Login.tsx:153`](../../frontend/src/routes/Login.tsx#L153) calls out.
- [ ] **Focus states.** These are the only two screens in the product a user will
      navigate entirely by keyboard before they can see anything else. Every input,
      the reveal toggle, the checkbox, both buttons and every link get a visible focus
      ring from the tokens.
- [ ] **The `AuthAside` panel** — confirm its stat tiles use real values from the
      landing keys (they do today: `landing.hero.stats.*`) and that the brand gradient
      matches the Dashboard's after commit `0c335af`.
- [ ] **Responsive.** `main` has `min-w-[340px]`; the card is `max-w-[420px]` on Login
      and `max-w-[460px]` on Signup. Confirm both hold at 320 px wide without the aside
      forcing a horizontal scroll, and that the aside collapses rather than squeezing.
- [ ] **Dark theme.** Both screens are `bg-canvas` / `bg-surface` with `text-ink-2` and
      `text-ink-3` throughout. Check every `text-ink-3` instance: **`--ink-3` is for
      `--canvas` and `--surface` only — never on `--surface-2`**, where it measures 4.17
      in dark and axe fails the build. The notice box is `bg-surface-2` and its body
      text is `text-ink-2` today, which is correct — keep it that way when you restyle.
- [ ] **RTL.** Both use logical properties already (`pe-12`, `end-1`, `text-end`). The
      email and password inputs are pinned `dir="ltr"` deliberately — an email address
      and a password are LTR strings even in an Arabic UI. **Keep that.** Confirm the
      reveal toggle still lands inside the field's end edge when mirrored, and that
      `python3 scripts/qa_frontend_rtl.py` stays green.
- [ ] **Arabic typography.** Montserrat has no Arabic coverage; Arabic is IBM Plex Sans
      Arabic. Confirm both headlines and the notice render in the Arabic face, not a
      fallback.

### Page 13 — Sign in, specific items

- [ ] **Button: password reveal toggle** — already correct behaviourally
      (`aria-pressed`, `aria-controls`, `aria-label` swaps). Style it to the theme: hit
      target at least 44 px, token colours, visible focus ring.
- [ ] **Button: submit ("Sign in")** — primary standard. It keeps `aria-describedby`
      pointing at the notice. **It does not become a link to `/dashboard`.**
- [ ] **Button: SSO — stays disabled.** The docstring's reasoning is exact: *an enabled
      button for an identity provider that does not exist is the same lie in a
      different shape.* Style the disabled state properly — currently `text-ink-3` on
      `bg-surface`, which is legible but reads as broken rather than deliberate. Pair
      it with its `ssoUnavailable` caption so the disabled state is explained, not just
      shown.
- [ ] **The status line** (`role="status"`, `aria-live="polite"`) that appears after a
      well-formed submission. Style it as a small info row. It is the sentence that
      tells the user why nothing happened; it must not look like an error, and it must
      not look like success.
- [ ] **"Forgot password"** is currently plain text, not a link, because there are no
      accounts to reset. Keep it as text. Style it so it does not look like a link that
      failed to render.
- [ ] **The "Open dashboard" link inside the notice** — this is the real escape hatch
      and the honest one. Make it obviously actionable.

### Page 14 — Request access, specific items

- [ ] **Nine form controls, one visual language**: full name, work email, organisation,
      role, organisation type (`<select>`), use case (`<textarea>`), the agreement
      checkbox, the submit button. The `<select>` and `<textarea>` are the two most
      likely to render as unstyled browser defaults — check both in Safari and Firefox,
      light and dark.
- [ ] **The agreement checkbox** is `size-6` with `accent-accent`. Confirm the native
      accent colour resolves from the token in both themes, and that the label's click
      target covers the full text.
- [ ] **Required vs optional must be visible before submission, not after.** Name,
      email, organisation and the checkbox are gated; role, org type and use case are
      not. Only "use case" is marked optional today, so a user cannot tell that role and
      org type are also optional until they submit successfully without them. Mark all
      three consistently.
- [ ] **The "Request received" confirmation screen** gets the full card treatment —
      the checkmark icon is already there and good. **The `notTransmitted` paragraph is
      the load-bearing sentence on that screen** (the file comment says exactly that).
      Give it the `CaveatCard` treatment; do not let it become fine print under a big
      green checkmark. Consider whether a checkmark is even the right icon for
      "received but not transmitted" — it currently reads as success. That is a real
      design question and it is yours to answer.
- [ ] **Confirm the six organisation types** (`authority`, `research`, `development`,
      `ngo`, `dive`, `other`) are the right list, and that their EN and AR labels are
      domain-correct — "authority" here means ASEZA and the marine park, and a
      machine-translated Arabic label for that is likely wrong.

---

## TRACK B — Real authentication (the new functionality, and the honesty gate)

This is the work that makes the notice removable. **You own it because you own
Supabase.** Nothing here ships half-done — see the gate at the end.

### B1 — Decide the model, and write the decision down first

- [ ] **Supabase Auth, or a FastAPI-issued session?** You already run Supabase
      (Postgres + PostGIS), so Supabase Auth is the short path: it gives you users,
      password hashing, email confirmation and JWT issuance without writing any of it.
      The alternative — auth in FastAPI against your own `users` table — means owning
      password hashing and token rotation yourself, in the last four days before a
      demo. **Recommend Supabase Auth unless something in `data-model.md` rules it out.**
- [ ] **Check `data-model.md` first.** The schema is already specified there and the
      standing instruction is **transcribe it, do not redesign it**. If it defines a
      users/roles table, that is the shape — do not invent a second one next to it.
- [ ] **Write the decision into `tasks/00-contracts.md` §5** before you build. Whichever
      way it goes, five other people need to know how a request proves who it is from.

### B2 — The Supabase side

- [ ] **Connection reality check.** `db.<ref>.supabase.co` is **IPv6-only** — it has an
      AAAA record and no A record. Use the **pooler** (IPv4), username
      `postgres.<project_ref>`. This has already cost this project time once; it will
      look like an unexplained hang, not an error.
- [ ] **Row Level Security on, before the first row exists.** A Supabase table without
      RLS is world-readable to anyone holding the anon key, and the anon key ships in
      the frontend bundle by design. Enable RLS and write the policies in the same
      migration that creates the table.
- [ ] **Key discipline, and this one is not stylistic.** The **anon/publishable key**
      belongs in the frontend and is safe there *only because* RLS is on. The
      **service-role key bypasses RLS entirely and must never reach the browser** — not
      in a `VITE_*` variable, not in a build-time constant, not in a comment. Anything
      needing it runs server-side. **Never commit `.env`.**
- [ ] **Access model.** This product is for named institutions — ASEZA, the marine park,
      research groups. Decide whether sign-up is **self-serve** or **invite/approval
      only**. The Signup screen is literally titled *Request access* and the flow ends
      in "we will get back to you", which points hard at approval-gated. If it is
      approval-gated, self-serve Supabase sign-up is the wrong default and must be
      turned off in the project settings — otherwise anyone can mint an account and the
      screen's own promise is false.
- [ ] **Email confirmation on**, and confirm the sender domain actually delivers.
      A confirmation email that silently never arrives is indistinguishable from a
      broken sign-up.

### B3 — The API side

- [ ] **Decide what auth actually protects, honestly.** Every endpoint the frontend uses
      today is public and read-only over open data. The endpoints where identity
      genuinely matters are the **writes**:
      `POST /api/v1/reports/{id}/review` (who reviewed it — the report literally stores
      `reviewed_by`), `POST /api/v1/reef-zones/{id}/photos` (who uploaded), and
      `POST /api/v1/sites/score` (who created a candidate site).
      **`reviewed_by` is the strongest argument for auth in the whole product** — a
      human-review audit trail whose author is a free-text string a client can put
      anything into is not an audit trail. Start there.
- [ ] **Add token verification as middleware/dependency**, verifying the Supabase JWT
      against the project's JWKS. Do not hand-roll signature checking.
- [ ] **Add `GET /api/v1/users/me`** — the frontend needs one call to answer "am I
      signed in, and as whom". Its absence is named explicitly in the Login docstring.
- [ ] **Keep reads public.** This is a public-good ocean product; putting the reef zones
      behind a login would be a real loss and is not what auth is for here. Protect the
      writes.
- [ ] **`tests/test_api_startup.py` must still pass.** A green suite is not evidence the
      stack runs: the suite once sat at 482-green while `docker compose up` started
      nothing, because tests imported `backend.src.api.main` while the container runs
      `--app-dir /app/backend/src`. **Auth middleware is exactly the kind of import-time
      addition that breaks under one path and not the other.** Run the container, not
      just pytest.

### B4 — The frontend side

- [ ] **A single `useAuth` hook / auth context** as the only place session state lives.
      No component reads the token directly.
- [ ] **Session persistence and refresh** — a token that expires mid-demo and silently
      starts 401-ing every panel is the worst possible failure mode on stage. Handle
      refresh, and handle refresh *failure* with a visible "your session ended" state.
- [ ] **Wire Login's real submit.** Keep every existing local validation — the email
      typo check, the required-field checks — and add the server round trip after them.
      Three states the screen does not have today and needs: **pending** (button
      disabled, spinner, no double-submit), **server error** (wrong credentials, network
      down, account not yet approved — each a different message), and **success**
      (navigate to `/dashboard`).
- [ ] **Never reveal whether an email exists.** "Wrong email" and "wrong password" get
      the **same** message. This is standard and it matters more here because the user
      list is a short list of named regional institutions.
- [ ] **Rate-limit the sign-in attempt path** server-side.
- [ ] **Wire Signup's real submit** to whatever B2 decided — a real Supabase sign-up, or
      a real access-request row. Then and only then does `notTransmitted` change, and it
      changes to a sentence that is *also* true: what was actually sent, where it went,
      and what happens next. If approval is manual, say a human approves it, and say
      roughly when.
- [ ] **Sign out.** There is no sign-out affordance anywhere in the product today
      because there has never been a session. It belongs in `DashboardChrome`, next to
      the account link.
- [ ] **`/account` currently shows what?** Check `AccountPage.tsx` — if it renders
      placeholder identity, it becomes real or it becomes honest, in the same commit as
      the rest.
- [ ] **Route protection.** Decide what `/dashboard` does for a signed-out user once
      sessions exist. Today the notice explicitly invites them in, and reads are public,
      so **the honest answer may well be "nothing changes"** — the dashboard stays open
      and only the write actions require a session. Do not add a login wall by reflex.
- [ ] **EN + AR keys in the same commit** for every new string: pending, each error, the
      session-expired state, sign-out, and the rewritten notice. The `auth.*` namespace
      already exists and is at parity — keep it there.

### B5 — The gate

**Track B is done when all of these are true, and the permanent notices come down in
the same commit that makes the last of them true — not before:**

1. A real user, created through the real flow, can sign in from a clean browser.
2. The session survives a page reload and refreshes before expiry.
3. `GET /api/v1/users/me` returns that user, verified from the token, not from a
   client-supplied id.
4. At least one write endpoint rejects an unauthenticated request — `reviewed_by` on a
   report is set from the verified token, not from the request body.
5. Sign-out works and actually invalidates the client session.
6. Wrong credentials produce a real, indistinguishable error — not a silent no-op.
7. `docker compose up` starts the stack with auth enabled, and
   `tests/test_api_startup.py` passes against the container's import path.
8. RLS is on, and the service-role key appears nowhere in `frontend/`.

**If any of the eight is not true on the 13th, Track A ships and the notices stay
exactly as they are.** A demo where sign-in is honestly absent is a demo with one fewer
feature. A demo where sign-in appears to work and does not is a demo that lied about
its own product on the first screen — and this project's entire pitch is that it does
not do that.

---

## Your final report

**Page 11**

- The exact cache field list, their plain-language labels, and the verdict on `size` =
  entries vs bytes.
- The **root cause of `[object Object]` in one sentence**, for the phase report.
- Whether the same `String(value)` pattern appears anywhere else in the UI.
- The finished artifact→group mapping, with every key assigned and the three-state badge
  buckets identified.

**Pages 13 & 14**

- Track A: screenshots of both screens, light and dark, EN and AR, plus a keyboard-only
  pass through each form. Explicit confirmation that **the permanent notice, the
  disabled SSO button, the status line and the `notTransmitted` paragraph are all still
  present and still true**.
- Track B: the auth-model decision and where it is written down; the access model
  (self-serve vs approval-gated) and which Supabase setting enforces it; which
  endpoints now require a token; and a **straight yes or no on each of the eight gate
  items**. If it is a no, say so plainly — that is the answer this file is asking for,
  not a reason to round up.

**A Suggestions section** for anything you noticed and deliberately did not act on.
