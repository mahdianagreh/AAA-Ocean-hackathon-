"""
Seed `data_sources` — one row per product actually retrieved by the team so far.

Per data-model.md §7 Phase 0 (S5): "the first data in the database; everything else
FKs to it." Transcribed from docs/data_dictionary.md and reefshield_aqaba_concept.md
§11 — not invented. Idempotent: safe to re-run any time a new source is documented.

known_limitation is copied close to verbatim from the dictionary so the caveat that
lives on a slide also lives in the API response (data-model.md §3.6).
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import text

from src.db.client import session_scope

UPSERT_SQL = text(
    """
    INSERT INTO data_sources (
        id, name, provider, product, version, temporal_resolution,
        spatial_resolution_m, native_crs, access_url, access_method,
        requires_account, license, citation, first_accessed_at,
        last_checked_at, known_limitation, notes
    ) VALUES (
        :id, :name, :provider, :product, :version, :temporal_resolution,
        :spatial_resolution_m, :native_crs, :access_url, :access_method,
        :requires_account, :license, :citation, :first_accessed_at,
        :last_checked_at, :known_limitation, :notes
    )
    ON CONFLICT (id) DO UPDATE SET
        name = EXCLUDED.name,
        provider = EXCLUDED.provider,
        product = EXCLUDED.product,
        version = EXCLUDED.version,
        temporal_resolution = EXCLUDED.temporal_resolution,
        spatial_resolution_m = EXCLUDED.spatial_resolution_m,
        native_crs = EXCLUDED.native_crs,
        access_url = EXCLUDED.access_url,
        access_method = EXCLUDED.access_method,
        requires_account = EXCLUDED.requires_account,
        license = EXCLUDED.license,
        citation = EXCLUDED.citation,
        last_checked_at = EXCLUDED.last_checked_at,
        known_limitation = EXCLUDED.known_limitation,
        notes = EXCLUDED.notes
    """
)

# Access-date strings from the dictionary, converted to timestamptz (UTC midday, since
# only the date — not the time — is documented).
_D = lambda date_str: dt.datetime.fromisoformat(date_str + "T12:00:00+00:00")

SOURCES = [
    dict(
        id="cop_dem_glo30",
        name="Copernicus DEM GLO-30",
        provider="ESA / Copernicus",
        product="Copernicus_DSM_COG_10 (GLO-30)",
        version="GLO-30, COG distribution",
        temporal_resolution="static",
        spatial_resolution_m=30,
        native_crs="EPSG:4326",
        access_url="s3://copernicus-dem-30m/",
        access_method="aws-s3",
        requires_account=False,
        license="Free for any use with attribution to ESA / Copernicus",
        citation="https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM",
        first_accessed_at=_D("2026-08-01"),
        last_checked_at=_D("2026-08-02"),
        known_limitation=(
            "Surface model — buildings, container stacks and road embankments are in "
            "the elevation values. Caused 3 of 5 outlets to route through port "
            "infrastructure."
        ),
        notes="Production DEM. Catchment delineation, outlets, all terrain features.",
    ),
    dict(
        id="srtm_gl1",
        name="NASA SRTM 1 arc-second",
        provider="NASA",
        product="SRTM GL1 (skadi)",
        version="skadi distribution",
        temporal_resolution="static",
        spatial_resolution_m=30,
        native_crs="EPSG:4326",
        access_url="https://s3.amazonaws.com/elevation-tiles-prod/skadi/",
        access_method="aws-s3",
        requires_account=False,
        license="Public domain (NASA)",
        citation="https://data.nasa.gov/dataset/nasa-shuttle-radar-topography-mission-global-1-arc-second-netcdf-v003-57aa4",
        first_accessed_at=_D("2026-08-02"),
        last_checked_at=_D("2026-08-02"),
        known_limitation=(
            "Yields 136,927 depressions against GLO-30's 20,352 over the same area — "
            "too noisy for depression-based analysis here. Cross-check only, not a "
            "pipeline dependency."
        ),
        notes="Confirms outlet positions to within 600 m; disagrees on catchment area.",
    ),
    dict(
        id="esa_worldcover_2021",
        name="ESA WorldCover 10 m",
        provider="ESA",
        product="ESA WorldCover",
        version="v200, 2021 epoch",
        temporal_resolution="static",
        spatial_resolution_m=10,
        native_crs="EPSG:4326",
        access_url="https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/",
        access_method="aws-s3",
        requires_account=False,
        license="CC BY 4.0 — attribution: (c) ESA WorldCover project 2021",
        citation="https://esa-worldcover.org/en/data-access",
        first_accessed_at=_D("2026-08-01"),
        last_checked_at=_D("2026-08-01"),
        known_limitation=(
            "2021 epoch only, no time series — cannot capture land-use change between "
            "the Feb 2013 and Oct 2016 flood events; both are modelled against 2021 "
            "land cover."
        ),
        notes=None,
    ),
    dict(
        id="isric_soilgrids_v2",
        name="ISRIC SoilGrids",
        provider="ISRIC",
        product="SoilGrids",
        version="v2.0",
        temporal_resolution="static",
        spatial_resolution_m=250,
        native_crs="EPSG:4326",
        access_url="https://maps.isric.org/mapserv?map=/map/<var>.map",
        access_method="http",
        requires_account=False,
        license="CC BY 4.0",
        citation="https://docs.isric.org/globaldata/soilgrids/index.html",
        first_accessed_at=_D("2026-08-01"),
        last_checked_at=_D("2026-08-01"),
        known_limitation=(
            "Globally model-derived, not surveyed. Use as a relative erodibility proxy "
            "across catchments, never as a measured local soil property."
        ),
        notes=None,
    ),
    dict(
        id="osm_jordan",
        name="OpenStreetMap Jordan extract",
        provider="OpenStreetMap contributors / Geofabrik",
        product="jordan-latest.osm.pbf",
        version=None,
        temporal_resolution="static",
        spatial_resolution_m=None,
        native_crs="EPSG:4326",
        access_url="https://download.geofabrik.de/asia/jordan-latest.osm.pbf",
        access_method="http",
        requires_account=False,
        license="ODbL 1.0 — (c) OpenStreetMap contributors",
        citation="https://download.geofabrik.de/asia/jordan.html",
        first_accessed_at=_D("2026-08-01"),
        last_checked_at=_D("2026-08-01"),
        known_limitation=(
            "Completeness in Aqaba is unknown for drainage infrastructure. An unmapped "
            "channel is not an absent channel — only useful as positive evidence when a "
            "feature is mapped."
        ),
        notes="Vector, no intrinsic resolution.",
    ),
    dict(
        id="gmrt_bathymetry",
        name="GMRT (Global Multi-Resolution Topography)",
        provider="gmrt.org / Lamont-Doherty",
        product="GMRT GridServer",
        version="max resolution, topo layer",
        temporal_resolution="static",
        spatial_resolution_m=53,
        native_crs="EPSG:4326",
        access_url="https://www.gmrt.org/services/GridServer",
        access_method="http",
        requires_account=False,
        license="Open — GMRT / GEBCO attribution",
        citation="https://www.gmrt.org/",
        first_accessed_at=_D("2026-08-01"),
        last_checked_at=_D("2026-08-01"),
        known_limitation=(
            "GEBCO stand-in — every programmatic GEBCO route was closed. ~53 m grid "
            "spacing but true information content is ~450 m; fine for basin geometry, "
            "not for reef-scale depth change or harbour structures. File kept named "
            "gmrt_aqaba.tif, never renamed to imply it is GEBCO."
        ),
        notes="Depth field + coastline mask for the particle engine boundary.",
    ),
    dict(
        id="reef_zones_provisional_derivation",
        name="Reef zones — provisional hand derivation",
        provider="Team (ReefShield Aqaba)",
        product="Provisional reef zone polygons",
        version="provisional, pending ACA swap-in",
        temporal_resolution="static",
        spatial_resolution_m=None,
        native_crs="EPSG:4326",
        access_url=None,
        access_method=None,
        requires_account=False,
        license="n/a — own derivation",
        citation=None,
        first_accessed_at=_D("2026-08-01"),
        last_checked_at=_D("2026-08-01"),
        known_limitation=(
            "PLACEHOLDER geometry derived from the water mask + published dive-site "
            "positions, not from a habitat survey. sensitivity_weight is a team "
            "assumption (uniform 1.0), not scientifically derived. Swap-in #3 is the "
            "Allen Coral Atlas v2.0 export."
        ),
        notes=None,
    ),
    dict(
        id="allen_coral_atlas",
        name="Allen Coral Atlas",
        provider="Allen Coral Atlas / Arizona State University",
        product="ACA reef habitat v2.0",
        version="v2.0",
        temporal_resolution="static",
        spatial_resolution_m=5,
        native_crs="EPSG:4326",
        access_url="https://allencoralatlas.org/",
        access_method="gee",
        requires_account=True,
        license="CC BY 4.0",
        citation="https://developers.google.com/earth-engine/datasets/catalog/ACA_reef_habitat_v2_0",
        first_accessed_at=None,
        last_checked_at=None,
        known_limitation=(
            "Not yet pulled — registered as the swap-in target for the provisional reef "
            "zones. Maps shallow reef habitat only, not ecological sensitivity."
        ),
        notes="Pending — Pulga's swap-in #3.",
    ),
    dict(
        id="imerg_v07_final",
        name="NASA GPM IMERG V07 — Final Run",
        provider="NASA / JAXA (GPM mission), NASA GES DISC",
        product="GPM_3IMERGHH",
        version="V07 (files V07B)",
        temporal_resolution="30min",
        spatial_resolution_m=11000,
        native_crs="EPSG:4326",
        access_url="https://gpm.nasa.gov/data/imerg",
        access_method="earthaccess",
        requires_account=True,
        license="Open, NASA Earthdata terms",
        citation="https://gpm.nasa.gov/data/imerg",
        first_accessed_at=_D("2026-08-01"),
        last_checked_at=_D("2026-08-01"),
        known_limitation=(
            "~11 km cells smooth the localized convective storms that cause Aqaba flash "
            "floods — a documented product limitation, not a pipeline defect."
        ),
        notes="Suitable for training. Gauge-adjusted, calibrated.",
    ),
    dict(
        id="imerg_v07_early",
        name="NASA GPM IMERG V07 — Early Run",
        provider="NASA / JAXA, GES DISC",
        product="GPM_3IMERGHHE",
        version="V07 (files V07C)",
        temporal_resolution="30min",
        spatial_resolution_m=11000,
        native_crs="EPSG:4326",
        access_url="https://gpm.nasa.gov/data/imerg",
        access_method="earthaccess",
        requires_account=True,
        license="Open, NASA Earthdata terms",
        citation="https://gpm.nasa.gov/data/imerg",
        first_accessed_at=_D("2026-08-01"),
        last_checked_at=_D("2026-08-01"),
        known_limitation=(
            "Preliminary, uncalibrated — never mix into a training set built on Final "
            "Run. Granules can be missing (83.33% window completeness observed "
            "2026-08-01)."
        ),
        notes="Live/near-real-time demo path only.",
    ),
    dict(
        id="era5_land",
        name="ERA5-Land Hourly",
        provider="ECMWF / Copernicus Climate Change Service (C3S)",
        product="reanalysis-era5-land",
        version=None,
        temporal_resolution="hourly",
        spatial_resolution_m=9000,
        native_crs="EPSG:4326",
        access_url="https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land",
        access_method="cdsapi",
        requires_account=True,
        license="Copernicus licence, accepted 2026-08-01",
        citation="https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land",
        first_accessed_at=_D("2026-08-01"),
        last_checked_at=_D("2026-08-01"),
        known_limitation=(
            "Land-only — cells over the Gulf are permanently NaN. Accumulations reset "
            "daily at 00 UTC. Precipitation does not match IMERG; use ERA5-Land for "
            "soil moisture/wind state, IMERG for rainfall magnitude, never averaged."
        ),
        notes="7 variables: swvl1, tp, sro, ssro, u10, v10, t2m.",
    ),
    dict(
        id="sentinel2_l2a_pc",
        name="Sentinel-2 L2A (via Microsoft Planetary Computer)",
        provider="ESA Copernicus, served via Microsoft Planetary Computer",
        product="Sentinel-2 L2A",
        version=None,
        temporal_resolution="static",
        spatial_resolution_m=10,
        native_crs="EPSG:32636",
        access_url="https://planetarycomputer.microsoft.com/api/stac/v1",
        access_method="http",
        requires_account=False,
        license="Copernicus open data",
        citation="https://planetarycomputer.microsoft.com/",
        first_accessed_at=_D("2026-08-02"),
        last_checked_at=_D("2026-08-02"),
        known_limitation=(
            "The plume probability raster derived from these scenes is a documented "
            "artifact, not a validated detection — see docs/event_audit.md §1a. Two "
            "independent sensors and the Kalman et al. 2025 mooring agree the real "
            "plume had already dispersed before either satellite pass."
        ),
        notes="No CDSE/GEE login needed — anonymous SAS-token signing.",
    ),
    dict(
        id="landsat_c2_pc",
        name="Landsat Collection 2 L2 (via Microsoft Planetary Computer)",
        provider="USGS/NASA, served via Microsoft Planetary Computer",
        product="Landsat 7/8 Collection 2 Level 2",
        version=None,
        temporal_resolution="static",
        spatial_resolution_m=30,
        native_crs="EPSG:32636",
        access_url="https://planetarycomputer.microsoft.com/api/stac/v1",
        access_method="http",
        requires_account=False,
        license="Public domain (USGS/NASA)",
        citation="https://planetarycomputer.microsoft.com/",
        first_accessed_at=_D("2026-08-02"),
        last_checked_at=_D("2026-08-02"),
        known_limitation=(
            "Landsat 7 SLC-off gaps affect the Feb 2013 candidate scenes; exact event "
            "date for that backup event is still unresolved."
        ),
        notes="Landsat 8 used as independent post-event corroboration for AQ-2016-10-28.",
    ),
    dict(
        id="kalman_2025_mooring",
        name="Kalman et al. 2025 — offshore mooring record",
        provider="Literature (peer-reviewed)",
        product="Salinity/turbidity mooring, 250 m offshore Kinnet Canal outlet, 13 m depth",
        version=None,
        temporal_resolution="5min",
        spatial_resolution_m=None,
        native_crs=None,
        access_url=None,
        access_method="http",
        requires_account=False,
        license="Literature — see citation",
        citation="Kalman et al. 2025 (full text in data/raw/literature/)",
        first_accessed_at=_D("2026-08-02"),
        last_checked_at=_D("2026-08-02"),
        known_limitation=(
            "The project's validation target replacing satellite plume masking (which "
            "returned a NO-GO for AQ-2016-10-28). One event, n=1 — final validation "
            "only, never trained on."
        ),
        notes="Salinity min 38.75 permille (-1.75, 19-sigma below background); turbidity peak 2.18 g/L.",
    ),
    dict(
        id="noaa_gfs",
        name="NOAA GFS",
        provider="NOAA NCEP",
        product="pgrb2.0p25",
        version=None,
        temporal_resolution="3-hourly steps to 48h lead",
        spatial_resolution_m=25000,
        native_crs="EPSG:4326",
        access_url="https://registry.opendata.aws/noaa-gfs-bdp-pds/",
        access_method="aws-s3",
        requires_account=False,
        license="US Government work, public domain",
        citation="https://www.ncei.noaa.gov/products/weather-climate-models/global-forecast",
        first_accessed_at=_D("2026-08-02"),
        last_checked_at=_D("2026-08-02"),
        known_limitation="~0.25 deg standard grid.",
        notes="Deterministic forecast rainfall + 10m wind, pulled live via Herbie byte-range subsetting.",
    ),
    dict(
        id="noaa_gefs",
        name="NOAA GEFS",
        provider="NOAA NCEP",
        product="atmos.5, pgrb2a",
        version=None,
        temporal_resolution="3-hourly steps to 48h lead, 30 members",
        spatial_resolution_m=50000,
        native_crs="EPSG:4326",
        access_url="https://registry.opendata.aws/noaa-gefs/",
        access_method="aws-s3",
        requires_account=False,
        license="US Government work, public domain",
        citation="https://www.ncei.noaa.gov/products/weather-climate-models/global-ensemble-forecast",
        first_accessed_at=_D("2026-08-02"),
        last_checked_at=_D("2026-08-02"),
        known_limitation=(
            "Coarse for local convection — captures synoptic-scale uncertainty, not "
            "whether a single thunderstorm cell lands on Wadi Yutum or 10km away."
        ),
        notes="Supplies the dashboard's confidence number via exceedance probability.",
    ),
    dict(
        id="ecmwf_ifs_opendata",
        name="ECMWF IFS Open Data",
        provider="ECMWF",
        product="IFS open data (oper stream)",
        version=None,
        temporal_resolution="3-hourly steps to 48h lead",
        spatial_resolution_m=25000,
        native_crs="EPSG:4326",
        access_url="https://data.ecmwf.int/",
        access_method="http",
        requires_account=False,
        license="CC BY 4.0 — attribute ECMWF",
        citation="https://www.ecmwf.int/en/forecasts/datasets/open-data",
        first_accessed_at=_D("2026-08-02"),
        last_checked_at=_D("2026-08-02"),
        known_limitation=(
            "Rolling archive, limited variables, short retention — never usable for "
            "historical backfill, live/near-real-time only."
        ),
        notes="Feeds the GFS-vs-IFS agreement flag.",
    ),
    dict(
        id="hycom_glby008",
        name="HYCOM GLBy0.08 (FMRC best)",
        provider="US Navy / hycom.org",
        product="GLBy0.08/latest",
        version=None,
        temporal_resolution="3-hourly",
        spatial_resolution_m=9000,
        native_crs="EPSG:4326",
        access_url="https://tds.hycom.org/thredds/dodsC/GLBy0.08/latest",
        access_method="http",
        requires_account=False,
        license="Approved for public release, unlimited distribution",
        citation="https://www.hycom.org/dataserver",
        first_accessed_at=_D("2026-08-02"),
        last_checked_at=_D("2026-08-02"),
        known_limitation=(
            "~1/12 deg (~9km) resolution across a gulf 15-25km wide: roughly 2-3 grid "
            "cells span the entire basin. The provisional outlet cell (34.96, 29.54) is "
            "masked/nan in this grid; nearest resolved open water is ~6km further into "
            "the gulf mouth — confirmed empirically, not just asserted. See "
            "docs/forcing_limitations.md."
        ),
        notes="Backup current source; direction cross-check against Copernicus Marine at the outlet.",
    ),
    dict(
        id="copernicus_marine_phy",
        name="Copernicus Global Ocean Physics Analysis & Forecast",
        provider="Copernicus Marine Service",
        product="GLOBAL_ANALYSISFORECAST_PHY_001_024 (cmems_mod_glo_phy_anfc_0.083deg_PT1H-m)",
        version=None,
        temporal_resolution="hourly",
        spatial_resolution_m=9000,
        native_crs="EPSG:4326",
        access_url="https://data.marine.copernicus.eu/product/GLOBAL_ANALYSISFORECAST_PHY_001_024/description",
        access_method="copernicusmarine",
        requires_account=True,
        license="Copernicus Marine licence (free with registration)",
        citation="https://data.marine.copernicus.eu/product/GLOBAL_ANALYSISFORECAST_PHY_001_024/description",
        first_accessed_at=None,
        last_checked_at=None,
        known_limitation=(
            "Not yet pulled — COPERNICUS_MARINE_USERNAME/PASSWORD not available as of "
            "2026-08-03. Primary current source once registered; same ~9km resolution "
            "limitation as HYCOM applies."
        ),
        notes="Fetch/cache functions written and ready (backend/src/ingestion/ocean_currents.py).",
    ),
]


def seed_data_sources() -> int:
    """Upsert every row in SOURCES. Returns the number of rows written."""
    with session_scope() as session:
        for source in SOURCES:
            session.execute(UPSERT_SQL, source)
    return len(SOURCES)


if __name__ == "__main__":
    n = seed_data_sources()
    print(f"Upserted {n} data_sources rows.")
