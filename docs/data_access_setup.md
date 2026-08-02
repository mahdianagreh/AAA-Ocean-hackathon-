# Data Access Setup — ReefShield Aqaba

External accounts and access methods required to run the ingestion pipeline.

Every teammate registers their **own** free accounts. There is no shared login.
Some approvals take hours, so register on Day 1 even for sources you will not
touch until later.

---

## ⚠️ Credential handling rules

- **`.env` must never be committed.** It is listed in `.gitignore`; leave it
  there. If you ever see `.env` in `git status`, stop and fix the ignore rule
  before committing anything.
- `.env.example` is the shared template. It stays **minimal and valueless** —
  variable names only, never a real or example secret.
- Never paste a password, API key, or token into chat, a screenshot, a commit
  message, an issue, or a log line.
- Never write credentials into a `.py` file. Read them from the environment.
- If a credential is exposed even once, rotate it at the provider immediately
  and update your local `.env`.

Current `.env.example` contents — the only two variables the pipeline needs
today:

```
EARTHDATA_USERNAME=
EARTHDATA_PASSWORD=
```

To get started:

```bash
cp .env.example .env
chmod 600 .env          # readable only by you
# then fill in your own username and password
```

---

## Account status at a glance

| # | Account | Purpose | Status |
|---|---------|---------|--------|
| 1 | NASA Earthdata | GPM IMERG Final + Early | **Required — in use now, GES DISC approved** |
| 2 | Copernicus Climate Data Store | ERA5-Land | **Required — CONFIGURED, licence accepted** |
| 3 | Copernicus Marine | Ocean currents | **Required — needed later** |
| 4 | Copernicus Data Space | Sentinel-2 imagery | **Required — needed later** |
| 5 | Google Earth Engine | Fast geospatial access | *Optional* |
| 6 | NASA Earthdata Search | Browsing / validating datasets | *Optional — no separate account* |

---

## 1. NASA Earthdata — **Required (in use now)**

- **Purpose:** GPM IMERG precipitation — the rainfall input driving event
  detection. This is the only source the pipeline authenticates against today.
- **Registration URL:** https://urs.earthdata.nasa.gov/users/new
- **Environment variables:**

  ```
  EARTHDATA_USERNAME
  EARTHDATA_PASSWORD
  ```

- **Used by:** `backend/src/ingestion/imerg.py`, via the `earthaccess` library.
- **Products in use:** Final Run `GPM_3IMERGHH` (`C2723754847-GES_DISC`) and
  Early Run `GPM_3IMERGHHE` (`C2723758340-GES_DISC`). Both capability-verified
  through Harmony; see the registry `IMERG_PRODUCTS`.
- **Notes:**
  - Log in with your **username**, not your email address. This is the single
    most common setup mistake.
  - The module loads `.env` and authenticates with
    `earthaccess.login(strategy="environment")` when both variables are
    present, and only falls back to an interactive prompt in a real terminal.
    In a headless run with no credentials it raises a clear error instead of
    hanging on a prompt.
  - Some GES DISC datasets require a one-time application approval on your
    Earthdata profile before downloads succeed. Search works without it.

## 2. Copernicus Climate Data Store (CDS) — **Required (CONFIGURED)**

> **Status: working.** `~/.cdsapirc` is configured (mode 600, outside the repo)
> and the ERA5-Land licence has been accepted. Retrieval of all seven variables
> is proven. See `docs/era5_land_temporal_semantics.md` for how the accumulated
> variables are interpreted.

- **Purpose:** ERA5-Land reanalysis — soil moisture, runoff proxy, and wind.
- **Registration URL:** https://cds.climate.copernicus.eu/
- **Notes:**
  - `cdsapi` credentials live in `~/.cdsapirc`, **never** in `.env` or
    `.env.example`. That file holds a secret, so it stays outside the repo;
    `.gitignore` also lists `.cdsapirc` as a second line of defence.
  - Get the two-line block from https://cds.climate.copernicus.eu/how-to-api,
    write it to `~/.cdsapirc`, then `chmod 600 ~/.cdsapirc`.
  - You must accept the ERA5-Land licence once on the dataset page
    (`?tab=download#manage-licences`) or requests fail with HTTP 403
    "required licences not accepted" even with valid credentials.
  - Required package: `cdsapi>=0.7.7`.

## 3. Copernicus Marine — **Required (needed later)**

- **Purpose:** Ocean current data for the marine plume transport engine.
- **Registration URL:** https://data.marine.copernicus.eu/
- **Notes:** Accessed through the `copernicusmarine` toolbox. Credential
  configuration will be documented when that ingestion module is built.

## 4. Copernicus Data Space — **Required (needed later)**

- **Purpose:** Sentinel-2 imagery for observing and validating sediment plumes.
- **Registration URL:** https://dataspace.copernicus.eu/
- **Notes:** Supports both interactive download and S3-style bulk access. Which
  path we use will be decided when the imagery module is built.

## 5. Google Earth Engine — *Optional*

- **Purpose:** Optional fast access to geospatial datasets, including
  Sentinel-2 and reef habitat layers, without local downloads.
- **Registration URL:** https://earthengine.google.com/
- **Notes:**
  - Optional. Nothing in the pipeline depends on it; it is a convenience and
    cross-check path.
  - Register your **own** project. Authentication is browser-based
    (`earthengine authenticate`), so there is no password to store.

## 6. NASA Earthdata Search — *Optional (no separate account)*

- **Purpose:** Browsing and validating NASA datasets — confirming a granule
  exists, checking coverage and time ranges before writing download code.
- **URL:** https://search.earthdata.nasa.gov/
- **Notes:** A web tool, not an API. It uses your existing NASA Earthdata login
  from section 1; no additional registration and no extra variables.

---

## Verifying your setup

```bash
source .venv/bin/activate
python backend/src/ingestion/imerg.py
```

Expected output:

```
Granules found: 5
```

This performs a metadata search only — no files are downloaded.

---

## Area of interest

The project uses **two extents, not one** — see `tasks/00-contracts.md` §1.
Both are defined once, in `backend/src/config/spatial.py`; never retype them.

```
TERRAIN_AOI = 34.75, 29.15, 35.94, 30.30   # W, S, E, N — EPSG:4326
              land side: DEM, hydrology, rainfall, land cover, soil

MARINE_AOI  = 34.80, 29.25, 35.05, 29.60   # W, S, E, N — EPSG:4326
              sea side: currents, bathymetry, imagery, reef zones
```

Download against the union (`data/aoi/aqaba_aoi.geojson`) or wider, and clip
to the relevant extent at analysis time.

> **Superseded 2 August 2026.** The single padded box this section used to
> name reached only 29.70 N and 35.15 E. Wadi Yutum drains ~90 km inland to
> 35.89 E, so that box covered about 9 % of the terrain AOI. Anything fetched
> before this date needs re-pulling — run `python scripts/check_aoi_coverage.py`
> for the current gap list.
