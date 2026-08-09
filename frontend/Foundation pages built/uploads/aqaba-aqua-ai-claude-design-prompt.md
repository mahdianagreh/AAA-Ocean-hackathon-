# Prompt for Claude Design — Foundation Build (Home / Login / Signup)
### Copy everything below the line into Claude Design as a single message

---

Build the foundational three pages for **AQABA AQUA AI** — a marine intelligence
dashboard platform (not a marketing site) that forecasts flash-flood sediment risk to
coral reefs in the Gulf of Aqaba. This is a **single-pass build**: produce all three
pages — Home, Login, Signup — as complete, production-quality React components in one
response. Do not leave placeholders or "TODO" sections; every piece of copy, every
color, and every spacing value is specified below so no follow-up clarification should
be needed.

## Tech stack

- React + TypeScript, functional components
- Tailwind CSS using the exact custom tokens below (extend `tailwind.config.js` with
  these, don't approximate with default Tailwind colors)
- Single-file components are fine; keep `Home.tsx`, `Login.tsx`, `Signup.tsx` as three
  separate exports
- Fully responsive (mobile-first), accessible (WCAG AA minimum contrast, visible focus
  states, no color-only communication — the brand guide requires this explicitly)
- No external UI kit — build components from the design tokens directly

## Design tokens — use these exactly, do not substitute

```css
:root {
  --color-primary: #0A1F4D;      /* Deep Navy — primary brand, headers, primary buttons */
  --color-secondary: #0D3D7A;    /* Ocean Blue — secondary UI */
  --color-teal: #007A99;         /* Marine Teal — charts, data accents */
  --color-accent: #00B7C3;       /* Aqua — accent, AI-related highlights, focus states */
  --color-soft: #E6F7FA;         /* Foam White — soft background sections */
  --color-bg: #FFFFFF;           /* Pure White — main surface */
  --color-dark: #09111F;
  --color-slate: #46566D;        /* secondary text */
  --color-border: #DCE5EC;
  --color-surface: #F4F7FA;

  --radius-sm: 8px;
  --radius-md: 12px;
  --radius-lg: 16px;
  --radius-card: 20px;

  --shadow-sm: 0 4px 12px rgba(10,31,77,.08);
  --shadow-md: 0 10px 30px rgba(10,31,77,.12);
  --shadow-lg: 0 20px 60px rgba(10,31,77,.18);
}
```

**Gradient** (use only for hero background, CTA buttons, and the logo mark — not for
large body text blocks or general backgrounds):
```css
background: linear-gradient(135deg, #0A1F4D 0%, #0D3D7A 35%, #007A99 65%, #00B7C3 100%);
```

**Typography:** Montserrat (weights: 400, 600, 700), fallback `Inter, system-ui,
sans-serif`. Scale: Hero 64px/700, H1 48px/700, H2 36px/700, H3 28px/600, H4 24px/600,
Body 16px/400, Small 14px/400. Body text minimum 16px per the accessibility requirement.

**Spacing:** 8-point grid — use only 4, 8, 12, 16, 24, 32, 48, 64, 96, 128px values.

**Buttons:**
- Primary: `background: #0A1F4D`, white text, `radius-md`
- Secondary: white background, navy border, navy text
- Accent: `background: #00B7C3`, hover → `#007A99`

**Cards:** white background, `radius-card` (20px), `1px solid #DCE5EC` border,
24px padding, `shadow-sm` default, `shadow-md` on hover if interactive

**Inputs:** 48px height, `radius-md` (12px), `1px solid #DCE5EC` border, focus ring in
`#00B7C3`

**Icons:** outline style, 2px stroke, rounded corners, minimal geometric — no filled
icons, no cartoon style

## Logo mark — describe and recreate as inline SVG

The logo is three overlapping triangular "A" shapes forming one larger triangle
silhouette, styled as a mountain-to-wave form: the outer point is a sharp peak in
lighter aqua/teal (`#00B7C3`–`#007A99` gradient), and the interior contains a stylized
breaking-wave curve rendered in the same teal-to-navy gradient, with the base of the
form in Deep Navy (`#0A1F4D`). The wordmark "AQABA AQUA AI" sits beside it in
Montserrat Bold, all-caps, letter-spaced, with "AQABA AQUA" in Deep Navy and "AI"
picked out in the Aqua accent color. A thin single vertical divider line (in the accent
gradient) separates the icon from the wordmark. Recreate this as a clean inline SVG
component (`<Logo />`) reusable across all three pages — approximate the wave-mountain
shape with simple path geometry, do not attempt photorealism; a clean geometric
interpretation is correct and preferred per the brand guide's "minimal geometric
style" instruction.

---

## PAGE 1 — Home (dashboard entry point, not a marketing landing page)

This platform is an **operational tool**, not a brochure — the home page should read as
the front door to a working system, with marketing/context content kept brief and
factual, never salesy.

### Structure, top to bottom:

**1. Navbar**
Logo left. Right side: "How it works," "Data Sources," "Login" (secondary button),
"Get Access" (primary button, gradient background). Sticky on scroll, white background
with `shadow-sm` once scrolled.

**2. Hero section** — gradient background (the full brand gradient), white text
- Eyebrow label (small, letter-spaced, Aqua color): "MARINE INTELLIGENCE FOR THE GULF OF AQABA"
- H1: "See the flood before it reaches the reef."
- Subhead (body size, slightly muted white/foam): "AQABA AQUA AI forecasts flash-flood
  sediment risk to Gulf of Aqaba coral reefs — connecting rainfall, terrain, and ocean
  currents into one early-warning system, hours before the sediment arrives."
- Two buttons: primary white "Get Access" and secondary outline "See How It Works"
- Below the buttons, a live-feeling stat strip (four small stat cards, glass/translucent
  style over the gradient): "27mm — mean annual rainfall" · "24,400t — sediment moved in
  a single 2016 event" · "8 reef zones tracked" · "Live GFS + GEFS forecasting"

**3. The Problem section** (white background)
- H2: "A flood in the desert is a marine event. Nothing treats it as one."
- Two-column layout: left is body text explaining the wadi-to-reef chain in plain
  language (rain doesn't soak into the desert, it becomes a fast flood, it carries
  sediment into the sea, it smothers the reef before anyone knows it's coming); right is
  a simple stylized SVG diagram showing the chain: mountain icon → wadi/flow icon → wave
  icon → reef icon, connected by a thin gradient line

**4. How It Works section** (soft background, `--color-soft`)
- H2: "Five real signals, one prediction."
- Five-card horizontal row (stack vertically on mobile), each a white card with an
  outline icon, a short title, and one line of description:
  1. Rainfall Forecasting — "Live satellite and ensemble weather data, tracked per catchment"
  2. Runoff Modeling — "Trained on real terrain, soil, and historical storm data"
  3. Sediment Estimation — "Anchored to a real, documented flood event"
  4. Plume Transport — "Ocean current and particle modeling shows where sediment spreads"
  5. Reef Exposure — "Named reef zones scored by real, explainable risk"

**5. Trust/Validation section** (white background)
- H2: "Validated against real, measured data — not assumptions."
- A single wide card: left side a short stat ("Model correctly ranked the real October
  2016 flood as the highest-risk storm in 26 years — without ever training on it"),
  right side three small honesty badges: "Real sensor validation," "Open data only,"
  "Every limitation documented"

**6. CTA section** (gradient background again, shorter than hero)
- H2 in white: "Built for the people protecting this coastline."
- Short line: "Coastal authorities, researchers, and dive operators — request access to
  the live dashboard."
- One large primary button: "Request Access" → links to Signup

**7. Footer** (`--color-dark` background, white/slate text)
- Logo (white monochrome version) left
- Three columns: Platform (How it works, Data Sources, Login), Project (About, Data
  Dictionary, Limitations), Contact
- Bottom line: small text, "AQABA AQUA AI — Marine Intelligence, Environmental AI,
  Ocean Technology"

---

## PAGE 2 — Login

Centered single-column layout, generous white space, card-based.

- Background: `--color-surface` (very light), full viewport height, centered content
- Logo at top, centered, smaller scale
- White card, `radius-card`, `shadow-md`, max-width ~420px, 32-48px padding
- H2 inside card: "Welcome back"
- Small subtext: "Sign in to your AQABA AQUA AI dashboard"
- Form fields (48px height inputs per spec):
  - Email input, labeled
  - Password input, labeled, with a show/hide toggle icon (outline eye icon)
  - "Forgot password?" small link, right-aligned, Aqua accent color
- Primary button, full width: "Sign In"
- Divider line with small "or" text
- Secondary button, full width, outline style: "Continue with organization SSO" (icon +
  text — this is a plausible enterprise/institutional login path given the buyer
  profile is coastal authorities and development teams, not consumers)
- Bottom of card, centered small text: "Don't have access yet? **Request Access**" (link
  to Signup, Aqua accent)
- Include basic client-side validation states (empty field, invalid email format) with
  error text below the field in a clear error color (use `#C0392B`-equivalent red or
  similar — brand guide doesn't specify an error color, so choose one with sufficient
  contrast and note in a code comment that it should be confirmed with the design system
  owner)

---

## PAGE 3 — Signup / Request Access

Same centered card layout and background as Login, for visual consistency.

- Logo at top, centered
- H2: "Request Access"
- Small subtext: "AQABA AQUA AI is currently available to coastal authorities, research
  institutions, and development partners. Tell us about your organization."
- Form fields:
  - Full name
  - Work email
  - Organization name
  - Role / title
  - Dropdown: "Organization type" — options: "Coastal/Marine Authority," "Research
    Institution," "Development / Environmental Team," "NGO / Non-profit," "Dive
    Operator / Tourism," "Other"
  - Short text area (optional): "What would you like to use the platform for?"
  - Checkbox: "I agree to the Terms of Use and Data Policy" (required)
- Primary button, full width: "Submit Request"
- Bottom of card, centered small text: "Already have access? **Sign In**" (link to Login)
- After-submit state: replace the form with a simple confirmation card — checkmark icon
  in Aqua, "Request received" heading, "Our team will review your request and follow up
  by email within a few business days." — build this as a local state toggle, no backend
  call needed for this pass

---

## Build notes

- Keep all three pages visually part of one system — same navbar/logo treatment
  where applicable, same button and card styles throughout, same spacing scale
- This is a first foundation pass: prioritize getting all three pages complete,
  consistent, and responsive over adding extra polish to any single one
- Use realistic, specific copy exactly as written above rather than generic
  placeholder text — every stat and sentence given here is meant to be used as-is
- Where a design decision isn't fully specified above (e.g., exact error-state color),
  make a reasonable choice consistent with the brand palette and leave a short code
  comment noting it as a decision to confirm later, rather than leaving it blank

---

*End of prompt. Paste everything above this line as one message to Claude Design.*
