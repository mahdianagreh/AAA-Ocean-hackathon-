"""NASA GPM IMERG data ingestion utilities for ReefShield Aqaba.

Two access paths are supported:

* ``search_imerg`` — CMR metadata search; returns granule handles only.
* ``download_imerg_subset`` — NASA Harmony spatial + variable subset,
  which returns a small NetCDF holding only ``Grid/precipitation`` inside
  the requested box (~44 KB per granule versus ~7.6 MB for a full-globe
  HDF5 granule).

Authentication order:
  1. `.env` / real environment variables  -> earthaccess strategy="environment"
  2. interactive prompt                    -> only when stdin is a TTY
  3. otherwise                             -> raise a clear, actionable error

``strategy="all"`` is deliberately NOT used: this project pins
earthaccess 0.17.0 and relies on the two explicit paths above.

Credentials are never printed, logged, or committed. Harmony result URLs are
never logged either — only local filenames.
"""

from __future__ import annotations

import logging
import os
import re
import sys
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from pathlib import Path

import earthaccess
import numpy as np
import xarray as xr
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Repo root is four levels up: ingestion -> src -> backend -> <root>
PROJECT_ROOT = Path(__file__).resolve().parents[3]
ENV_FILE = PROJECT_ROOT / ".env"

# Make `backend/src` importable whether this module is imported as a package,
# imported by the tests, or run directly as a file.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config.spatial import TERRAIN_AOI  # noqa: E402

# override=False so a real shell/CI variable always beats the file.
load_dotenv(ENV_FILE, override=False)

#: Rainfall must cover the full contributing catchments — Wadi Yutum reaches
#: ~90 km inland. See config/spatial.py for why the old coastal box was wrong.
DOWNLOAD_BBOX = TERRAIN_AOI.wsen
IMERG_SHORT_NAME = "GPM_3IMERGHH"
IMERG_VERSION = "07"

IMERG_COLLECTION_ID = "C2723754847-GES_DISC"
IMERG_VARIABLE = "Grid/precipitation"

USERNAME_VAR = "EARTHDATA_USERNAME"
PASSWORD_VAR = "EARTHDATA_PASSWORD"

#: NetCDF group holding the IMERG grid.
IMERG_GROUP = "Grid"
#: Sentinel written by NASA for missing cells.
IMERG_FILL_VALUE = -9999.9
#: Native precipitation unit — a rate, not an accumulation.
PRECIPITATION_UNITS = "mm/hr"
SOURCE_PRODUCT = "NASA GPM IMERG V07 Final Run"

HARMONY_OUTPUT_FORMAT = "application/netcdf"

_MISSING_CREDENTIALS_MSG = (
    "NASA Earthdata credentials not found and no interactive terminal is "
    "available.\n"
    f"Set {USERNAME_VAR} and {PASSWORD_VAR} in {{env_file}} "
    "(see .env.example), or export them in the environment.\n"
    "Register a free account at https://urs.earthdata.nasa.gov/users/new "
    "— use your username, not your email address."
)


class HarmonySubsetError(RuntimeError):
    """Raised when a Harmony subset request cannot be completed."""


def _credentials_present() -> bool:
    """True when both Earthdata variables are set and non-empty."""
    return bool(
        (os.getenv(USERNAME_VAR) or "").strip()
        and (os.getenv(PASSWORD_VAR) or "").strip()
    )


def _as_datetime(value: str | datetime) -> datetime:
    """Coerce an ISO-8601 string to a timezone-aware UTC datetime.

    harmony-py calls ``.isoformat()`` on temporal bounds, so a plain string
    raises ``AttributeError`` at submission time — and ``Request.is_valid()``
    does not catch it. Normalising here keeps the string-based public API
    while giving harmony-py the datetime it requires.
    """
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

    text = str(value).strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(
            f"Could not parse {value!r} as an ISO-8601 timestamp, e.g. "
            "'2016-10-27T03:00:00Z'."
        ) from exc
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _stdin_is_interactive() -> bool:
    """True only in a real terminal, where prompting a human can work."""
    try:
        return sys.stdin is not None and sys.stdin.isatty()
    except (AttributeError, ValueError):  # detached / closed stdin
        return False


def authenticate() -> earthaccess.Auth:
    """Authenticate with NASA Earthdata.

    Prefers credentials from `.env`; prompts only in a real terminal.
    Raises RuntimeError in a headless environment with no credentials.
    """
    if _credentials_present():
        strategy = "environment"
    elif _stdin_is_interactive():
        strategy = "interactive"
    else:
        raise RuntimeError(_MISSING_CREDENTIALS_MSG.format(env_file=ENV_FILE))

    auth = earthaccess.login(strategy=strategy, persist=False)

    if not auth.authenticated:
        raise RuntimeError(
            f"NASA Earthdata authentication failed (strategy={strategy!r}). "
            "Check the username — it is not the email address — and that the "
            "password is current."
        )

    return auth


def search_imerg(
    start_date: str,
    end_date: str,
    count: int = 5,
):
    """Search IMERG Final Run granules without downloading them."""
    return earthaccess.search_data(
        short_name=IMERG_SHORT_NAME,
        version=IMERG_VERSION,
        temporal=(start_date, end_date),
        bounding_box=DOWNLOAD_BBOX,
        count=count,
    )


def download_imerg_subset(
    start_time: str,
    end_time: str,
    output_dir: Path,
    bbox: tuple[float, float, float, float] = DOWNLOAD_BBOX,
    collection_id: str = IMERG_COLLECTION_ID,
    variable: str = IMERG_VARIABLE,
) -> list[Path]:
    """Download a Harmony spatial + variable subset of IMERG precipitation.

    Requests only ``Grid/precipitation`` inside ``bbox`` as NetCDF, which is
    far smaller than the full-globe HDF5 granule.

    Args:
        start_time: ISO-8601 start, e.g. ``"2016-10-25T00:00:00Z"``.
        end_time: ISO-8601 end, e.g. ``"2016-10-25T00:29:59Z"``.
        output_dir: Directory to write results into; created if absent.
        bbox: ``(west, south, east, north)`` in degrees.

    Returns:
        Resolved local paths of the downloaded files.

    Raises:
        HarmonySubsetError: if validation, submission, processing, or
            download fails.
        RuntimeError: if Earthdata credentials are unavailable.
    """
    # Imported lazily so that search-only workflows do not need harmony-py.
    try:
        from harmony import BBox, Client, Collection, Request
    except ImportError as exc:  # pragma: no cover - environment issue
        raise HarmonySubsetError(
            "harmony-py is required for subset downloads: pip install harmony-py"
        ) from exc

    authenticate()  # validates credentials and fails fast with a clear message

    username = (os.getenv(USERNAME_VAR) or "").strip()
    password = (os.getenv(PASSWORD_VAR) or "").strip()
    if not (username and password):
        raise RuntimeError(_MISSING_CREDENTIALS_MSG.format(env_file=ENV_FILE))

    west, south, east, north = bbox
    output_dir = Path(output_dir)

    client = Client(auth=(username, password))
    request = Request(
        collection=Collection(id=collection_id),
        spatial=BBox(west, south, east, north),
        # harmony-py requires datetime objects here, not ISO strings.
        temporal={"start": _as_datetime(start_time),
                  "stop": _as_datetime(end_time)},
        variables=[variable],
        format=HARMONY_OUTPUT_FORMAT,
        concatenate=False,
    )

    if not request.is_valid():
        raise HarmonySubsetError(
            "Harmony request is invalid: "
            f"{'; '.join(request.error_messages())}"
        )

    logger.info(
        "Submitting Harmony subset: %s from %s %s..%s "
        "bbox=(%.2f, %.2f, %.2f, %.2f)",
        variable, collection_id, start_time, end_time, west, south, east,
        north,
    )

    try:
        job_id = client.submit(request)
    except Exception as exc:
        raise HarmonySubsetError(
            f"Harmony submission failed: {type(exc).__name__}: {exc}"
        ) from exc

    if not job_id:
        raise HarmonySubsetError("Harmony returned no job id.")

    logger.info("Harmony job accepted; waiting for processing")
    try:
        client.wait_for_processing(job_id, show_progress=False)
    except Exception as exc:
        raise HarmonySubsetError(
            f"Harmony processing failed: {type(exc).__name__}: {exc}"
        ) from exc

    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        futures = client.download_all(
            job_id, directory=str(output_dir), overwrite=True
        )
        paths = [Path(future.result()).resolve() for future in futures]
    except Exception as exc:
        raise HarmonySubsetError(
            f"Harmony download failed: {type(exc).__name__}: {exc}"
        ) from exc

    missing = [p for p in paths if not p.exists()]
    if missing or not paths:
        raise HarmonySubsetError(
            "Harmony reported success but files are missing on disk: "
            f"{[p.name for p in missing] or 'no files returned'}"
        )

    # Log names only — never Harmony result URLs.
    logger.info(
        "Downloaded %d Harmony file(s): %s",
        len(paths), ", ".join(p.name for p in paths),
    )
    return paths


def read_imerg_subset(path: Path) -> xr.Dataset:
    """Open a Harmony IMERG NetCDF subset and normalise its layout.

    IMERG stores precipitation as ``(time, lon, lat)``. This transposes it to
    ``(time, lat, lon)``, masks fill values to NaN, and keeps the native
    ``mm/hr`` rate untouched — no accumulation is computed here. Bounds
    variables (``lat_bnds``, ``lon_bnds``, ``time_bnds``) are carried through
    when present.

    Args:
        path: Path to a Harmony-produced NetCDF/NetCDF4 file.

    Returns:
        Dataset with ``precipitation`` dimensioned ``(time, lat, lon)`` and
        ``source_product`` set in the attributes.

    Raises:
        FileNotFoundError: if `path` does not exist.
        KeyError: if the file has no precipitation variable.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"IMERG subset not found: {path}")

    # Harmony preserves the source layout, so the grid lives in /Grid.
    try:
        dataset = xr.open_dataset(path, group=IMERG_GROUP, decode_times=True)
    except OSError:
        dataset = xr.open_dataset(path, decode_times=True)

    if "precipitation" not in dataset.variables:
        available = sorted(map(str, dataset.variables))
        dataset.close()
        raise KeyError(
            f"No 'precipitation' variable in {path.name}; found: {available}"
        )

    units = dataset["precipitation"].attrs.get("units", PRECIPITATION_UNITS)

    # Normalise (time, lon, lat) -> (time, lat, lon); a no-op if already so.
    target = [d for d in ("time", "lat", "lon")
              if d in dataset["precipitation"].dims]
    extra = [d for d in dataset["precipitation"].dims if d not in target]
    if extra:  # keep any unexpected dimension rather than dropping data
        target = target + extra
    if tuple(dataset["precipitation"].dims) != tuple(target):
        logger.debug(
            "Transposing precipitation %s -> %s",
            dataset["precipitation"].dims, tuple(target),
        )
        dataset["precipitation"] = dataset["precipitation"].transpose(*target)

    # xarray masks _FillValue already; catch CodeMissingValue too.
    precip = dataset["precipitation"]
    dataset["precipitation"] = precip.where(
        ~np.isclose(precip, IMERG_FILL_VALUE, atol=0.5)
    )

    # where() drops attrs by default — restore the unit explicitly.
    dataset["precipitation"].attrs["units"] = units
    dataset["precipitation"].attrs.setdefault(
        "long_name", "Merged microwave-infrared precipitation rate"
    )

    present_bounds = [name for name in ("lat_bnds", "lon_bnds", "time_bnds")
                      if name in dataset.variables]
    dataset.attrs["source_product"] = SOURCE_PRODUCT
    dataset.attrs["bounds_available"] = ", ".join(present_bounds) or "none"

    logger.info(
        "Read %s: precipitation%s units=%s bounds=[%s]",
        path.name, tuple(dataset["precipitation"].sizes.items()),
        units, dataset.attrs["bounds_available"],
    )
    return dataset


def precipitation_rate_to_depth(
    dataset: xr.Dataset,
    interval_hours: float = 0.5,
    rate_period_hours: float = 1.0,
) -> xr.Dataset:
    """Add rainfall depth in mm alongside the untouched native rate.

    ``depth = rate * interval_hours / rate_period_hours``

    The second term matters because IMERG's products do not share a rate
    denominator. Half-hourly granules report **mm/hr** over 30 minutes, so
    depth is ``rate * 0.5 / 1``. Daily granules report **mm/day** over 24
    hours, so depth is ``rate * 24 / 24`` — the value already *is* the depth.
    Applying the half-hourly rule to a daily granule understates it 48-fold,
    and nothing about the result looks wrong.

    Args:
        dataset: Dataset from :func:`read_imerg_subset`.
        interval_hours: Length of the granule's accumulation window, in hours.
        rate_period_hours: Denominator of the rate's unit, in hours — 1.0 for
            ``mm/hr``, 24.0 for ``mm/day``. Both come from the product
            registry; do not guess them per call site.

    Returns:
        A new dataset with ``precipitation_depth_mm`` added; the original
        ``precipitation`` variable is preserved unchanged.

    Raises:
        KeyError: if `dataset` has no ``precipitation`` variable.
        ValueError: if `interval_hours` is not positive.
    """
    if "precipitation" not in dataset.variables:
        raise KeyError("Dataset has no 'precipitation' variable.")
    if interval_hours <= 0:
        raise ValueError(
            f"interval_hours must be positive, got {interval_hours!r}"
        )
    if rate_period_hours <= 0:
        raise ValueError(
            f"rate_period_hours must be positive, got {rate_period_hours!r}"
        )

    result = dataset.copy()
    native_units = result["precipitation"].attrs.get("units", PRECIPITATION_UNITS)
    factor = interval_hours / rate_period_hours
    depth = result["precipitation"] * factor
    depth.attrs = {
        "units": "mm",
        "long_name": "Precipitation depth over the granule interval",
        "interval_hours": interval_hours,
        "rate_period_hours": rate_period_hours,
        "conversion_factor": factor,
        "derived_from": (
            f"precipitation ({native_units}) * interval_hours "
            "/ rate_period_hours"
        ),
    }
    result["precipitation_depth_mm"] = depth

    logger.info(
        "Derived precipitation_depth_mm from %s: interval_hours=%s / "
        "rate_period_hours=%s -> factor %s",
        native_units, interval_hours, rate_period_hours, factor,
    )
    return result


# ---------------------------------------------------------------------------
# Product registry and generic windowed retrieval
# ---------------------------------------------------------------------------

#: Verified IMERG product registry.
#:
#: Every entry was resolved from NASA CMR and its Harmony capabilities were
#: checked before being written here — nothing is guessed. Final and Early are
#: separate products and must never be mixed: Early is preliminary, uncalibrated
#: and unsuitable for training or historical analysis.
IMERG_PRODUCTS: dict[str, dict] = {
    "final": {
        "short_name": "GPM_3IMERGHH",
        "version": "07",
        "collection_id": "C2723754847-GES_DISC",
        "variable": "Grid/precipitation",
        "title": "GPM IMERG Final Precipitation L3 Half Hourly 0.1 degree",
        "run_type": "final",
        "preliminary": False,
        "calibrated_final_product": True,
        "suitable_for_training": True,
        "capabilities_verified": True,
        "bbox_subset": True,
        "variable_subset": True,
        "granule_minutes": 30,
        "rate_units": "mm/hr",
        "rate_period_hours": 1.0,
    },
    "early": {
        "short_name": "GPM_3IMERGHHE",
        "version": "07",
        "collection_id": "C2723758340-GES_DISC",
        "variable": "Grid/precipitation",
        "title": "GPM IMERG Early Precipitation L3 Half Hourly 0.1 degree",
        "run_type": "early",
        "preliminary": True,
        "calibrated_final_product": False,
        "suitable_for_training": False,
        "capabilities_verified": True,
        "bbox_subset": True,
        "variable_subset": True,
        "granule_minutes": 30,
        "rate_units": "mm/hr",
        "rate_period_hours": 1.0,
    },
    # Daily Final. Stage 1 of the two-stage sweep: one file per day instead of
    # 48, so 28 years costs ~10,000 granules rather than ~490,000.
    #
    # It differs from the half-hourly products in three ways, each of which
    # would fail silently if assumed away:
    #
    #   1. The variable is `precipitation`, with NO `Grid/` prefix.
    #   2. The units are mm/DAY, not mm/hr. Multiplying by 0.5 h — correct for
    #      a half-hourly granule — understates a daily depth by 48x.
    #   3. The file has no `Grid` group and declares no `_FillValue`.
    #      `read_imerg_subset` masks the -9999.9 sentinel defensively anyway,
    #      which is why that one is already safe.
    #
    # Resolved from CMR on 2026-08-02 (short_name GPM_3IMERGDF -> exactly one
    # collection). Harmony's /capabilities endpoint was returning HTTP 500 for
    # every IMERG product that day, including the two already verified, so
    # capability was established two other ways instead: the collection carries
    # the identical six service associations as the verified half-hourly
    # product, and a real one-day subset request succeeded and returned a
    # correctly clipped 12x13 grid. See docs/imerg_daily_capability.json.
    "daily_final": {
        "short_name": "GPM_3IMERGDF",
        "version": "07",
        "collection_id": "C2723754864-GES_DISC",
        "variable": "precipitation",
        "title": "GPM IMERG Final Precipitation L3 1 day 0.1 degree",
        "run_type": "daily_final",
        "preliminary": False,
        "calibrated_final_product": True,
        "suitable_for_training": True,
        "capabilities_verified": True,
        "bbox_subset": True,
        "variable_subset": True,
        "granule_minutes": 1440,
        "rate_units": "mm/day",
        "rate_period_hours": 24.0,
        "screening_only": True,
    },
}

GRANULE_MINUTES = 30
DEFAULT_MAX_GRANULES = 500
DEFAULT_CHUNK_GRANULES = 48

_GRANULE_STAMP_RE = re.compile(r"3IMERG\.(\d{8})-S(\d{6})-E\d{6}")


class IMERGProductError(ValueError):
    """Raised for an unknown or unverified IMERG product."""


def get_imerg_product(run_type: str) -> dict:
    """Registry entry for a run type, or a clear error."""
    key = str(run_type).lower()
    if key not in IMERG_PRODUCTS:
        raise IMERGProductError(
            f"Unknown IMERG run_type {run_type!r}; known: "
            f"{sorted(IMERG_PRODUCTS)}"
        )
    product = IMERG_PRODUCTS[key]
    if not product.get("capabilities_verified"):
        raise IMERGProductError(
            f"IMERG product {key!r} has not passed capability validation; "
            "resolve and verify it through CMR/Harmony before use."
        )
    return product


def _as_utc_datetime(value: str | datetime, label: str) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def expected_granule_count(
    start_time: str | datetime,
    end_time: str | datetime,
    granule_minutes: int = GRANULE_MINUTES,
) -> int:
    """Granules whose start falls inside [start, end].

    `granule_minutes` is the product's cadence: 30 for the half-hourly
    products, 1440 for daily. Defaulting to 30 keeps every existing caller
    unchanged.
    """
    start = _as_utc_datetime(start_time, "start_time")
    end = _as_utc_datetime(end_time, "end_time")
    if end < start:
        raise ValueError(
            f"end_time ({end.isoformat()}) precedes start_time "
            f"({start.isoformat()})"
        )
    span = (end - start).total_seconds()
    return int(span // (granule_minutes * 60)) + 1


def expected_granule_timestamps(
    start_time: str | datetime,
    end_time: str | datetime,
    granule_minutes: int = GRANULE_MINUTES,
) -> list[datetime]:
    """Every granule start in the window, at the product's cadence."""
    start = _as_utc_datetime(start_time, "start_time")
    end = _as_utc_datetime(end_time, "end_time")
    step = timedelta(minutes=granule_minutes)
    stamps, cursor = [], start
    while cursor <= end:
        stamps.append(cursor)
        cursor += step
    return stamps


def granule_timestamp_from_name(name: str) -> datetime | None:
    """Granule start time parsed from a Harmony/GES DISC filename."""
    match = _GRANULE_STAMP_RE.search(name)
    if not match:
        return None
    return datetime.strptime(
        match.group(1) + match.group(2), "%Y%m%d%H%M%S"
    ).replace(tzinfo=timezone.utc)


def existing_granules(directory: Path) -> dict[datetime, Path]:
    """Map granule start -> file for a download directory (filenames only)."""
    directory = Path(directory)
    if not directory.is_dir():
        return {}
    found: dict[datetime, Path] = {}
    for path in sorted(directory.glob("*.nc*")):
        stamp = granule_timestamp_from_name(path.name)
        if stamp is not None and path.stat().st_size > 0:
            found.setdefault(stamp, path)
    return found


def _contiguous_runs(
    stamps: list[datetime], granule_minutes: int = GRANULE_MINUTES
) -> list[tuple[datetime, datetime]]:
    if not stamps:
        return []
    step = timedelta(minutes=granule_minutes)
    runs, run_start, previous = [], stamps[0], stamps[0]
    for stamp in stamps[1:]:
        if stamp - previous != step:
            runs.append((run_start, previous))
            run_start = stamp
        previous = stamp
    runs.append((run_start, previous))
    return runs


def _chunk_run(
    run: tuple[datetime, datetime],
    chunk_granules: int,
    granule_minutes: int = GRANULE_MINUTES,
) -> list[tuple[datetime, datetime]]:
    step = timedelta(minutes=granule_minutes)
    start, end = run
    chunks, cursor = [], start
    while cursor <= end:
        stop = min(cursor + step * (chunk_granules - 1), end)
        chunks.append((cursor, stop))
        cursor = stop + step
    return chunks


def fetch_imerg_window(
    start_time: str | datetime,
    end_time: str | datetime,
    bbox: tuple[float, float, float, float],
    output_dir: Path,
    run_type: str = "final",
    max_granules: int = DEFAULT_MAX_GRANULES,
    chunk_granules: int = DEFAULT_CHUNK_GRANULES,
    resume: bool = True,
    skip_unavailable: bool = False,
) -> list[Path]:
    """Download IMERG precipitation for any window and any bounding box.

    Uses Harmony spatial + variable subsetting, so only ``Grid/precipitation``
    inside `bbox` is transferred — never a global HDF5.

    Args:
        start_time: First granule start, inclusive. UTC.
        end_time: Last granule start, inclusive. UTC.
        bbox: ``(west, south, east, north)``.
        output_dir: Destination directory.
        run_type: ``"final"`` or ``"early"``; kept strictly separate.
        max_granules: Refuse windows larger than this.
        chunk_granules: Granules per Harmony job.
        resume: Skip granules already on disk.
        skip_unavailable: Continue when a chunk has no matching granules.
            Near-real-time products legitimately have gaps, so the Early Run
            demo sets this. Historical Final Run runs leave it False so a
            genuinely missing granule fails loudly.

    Returns:
        Paths of all granules for the window, in time order.

    Raises:
        IMERGProductError: unknown/unverified product.
        ValueError: reversed range or the safety limit exceeded.
        HarmonySubsetError: a Harmony job failed.
    """
    product = get_imerg_product(run_type)
    granule_minutes = product.get("granule_minutes", GRANULE_MINUTES)
    wanted = expected_granule_timestamps(
        start_time, end_time, granule_minutes=granule_minutes
    )
    if len(wanted) > max_granules:
        raise ValueError(
            f"Window spans {len(wanted)} granules, above max_granules="
            f"{max_granules}. Narrow the window or raise the limit."
        )

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    present = existing_granules(output_dir) if resume else {}
    missing = [stamp for stamp in wanted if stamp not in present]

    logger.info(
        "IMERG %s window: %d granule(s) wanted, %d present, %d to download",
        product["run_type"], len(wanted), len(present), len(missing),
    )

    for run in _contiguous_runs(missing, granule_minutes=granule_minutes):
        for chunk_start, chunk_stop in _chunk_run(
            run, chunk_granules, granule_minutes=granule_minutes
        ):
            try:
                download_imerg_subset(
                    start_time=chunk_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    end_time=(
                        chunk_stop + timedelta(minutes=granule_minutes - 1,
                                               seconds=59)
                    ).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    output_dir=output_dir,
                    bbox=bbox,
                    collection_id=product["collection_id"],
                    variable=product["variable"],
                )
            except HarmonySubsetError as exc:
                if skip_unavailable and "No matching granules" in str(exc):
                    logger.warning(
                        "No granules available for %s..%s — skipping (gap "
                        "recorded, nothing interpolated)",
                        chunk_start.isoformat(), chunk_stop.isoformat(),
                    )
                    continue
                raise

    present = existing_granules(output_dir)
    return [present[stamp] for stamp in wanted if stamp in present]


def process_imerg_window(
    paths: Sequence[Path],
    rolling_windows_hours: Sequence[int] = (1, 3, 6, 24),
    run_type: str = "final",
    bbox: tuple[float, float, float, float] | None = None,
) -> xr.Dataset:
    """Combine granules and derive trailing rolling accumulations.

    Args:
        paths: Granule files, any order.
        rolling_windows_hours: Window lengths in hours; each becomes
            ``rain_{n}h_mm``.
        run_type: Recorded as ``imerg_run_type`` so Final and Early outputs
            can never be confused downstream.
        bbox: Recorded in the attributes when known.

    Returns:
        Dataset with precipitation, per-interval depth, one variable per
        rolling window, and completeness metadata.
    """
    product = get_imerg_product(run_type)
    ordered = sorted(
        (Path(p) for p in paths),
        key=lambda p: granule_timestamp_from_name(p.name) or datetime.min.replace(
            tzinfo=timezone.utc
        ),
    )
    combined = combine_imerg_subsets(ordered, expected_interval_minutes=GRANULE_MINUTES)
    combined = precipitation_rate_to_depth(combined, interval_hours=0.5)

    windows = {}
    for hours in rolling_windows_hours:
        intervals = int(round(float(hours) * 2))
        if intervals < 1:
            raise ValueError(f"rolling window {hours} h is shorter than 30 min")
        windows[f"rain_{int(hours) if float(hours).is_integer() else hours}h_mm"] = intervals

    result = add_rolling_accumulations(
        combined, windows=windows, interval_hours=0.5
    )

    times = np.atleast_1d(result["time"].values)
    stamps = [_timestamp_label(t) for t in times]
    values = np.asarray(result["precipitation"].values, dtype="float64")
    missing_mask = np.isnan(values)

    result.attrs.update({
        "imerg_run_type": product["run_type"],
        "imerg_short_name": product["short_name"],
        "imerg_collection_id": product["collection_id"],
        "imerg_version": product["version"],
        "preliminary": str(product["preliminary"]).lower(),
        "calibrated_final_product": str(
            product["calibrated_final_product"]).lower(),
        "suitable_for_training": str(product["suitable_for_training"]).lower(),
        "source_product": (
            SOURCE_PRODUCT if product["run_type"] == "final"
            else "NASA GPM IMERG V07 Early Run"
        ),
        "granule_count": len(stamps),
        "first_timestamp_utc": stamps[0] if stamps else None,
        "last_timestamp_utc": stamps[-1] if stamps else None,
        "rolling_windows_hours": list(rolling_windows_hours),
        "total_valid_cells": int((~missing_mask).sum()),
        "total_missing_cells": int(missing_mask.sum()),
        "data_completeness_percent": float(
            100.0 * (~missing_mask).sum() / max(missing_mask.size, 1)
        ),
        "interpolation_performed": "no",
    })
    if bbox is not None:
        result.attrs["bbox_west_south_east_north"] = list(bbox)
    return result


def missing_granule_timestamps(
    paths: Sequence[Path],
    start_time: str | datetime,
    end_time: str | datetime,
) -> list[str]:
    """Granule starts expected in the window but absent from `paths`."""
    have = {
        granule_timestamp_from_name(Path(p).name)
        for p in paths
    }
    return [
        stamp.strftime("%Y-%m-%dT%H:%M:%SZ")
        for stamp in expected_granule_timestamps(start_time, end_time)
        if stamp not in have
    ]


def wettest_windows(
    dataset: xr.Dataset,
    rolling_windows_hours: Sequence[int] = (1, 3, 6, 24),
    interval_hours: float = 0.5,
) -> dict[str, dict]:
    """Maximum accumulation for every requested rolling duration."""
    output: dict[str, dict] = {}
    for hours in rolling_windows_hours:
        label = int(hours) if float(hours).is_integer() else hours
        name = f"rain_{label}h_mm"
        if name in dataset.variables:
            output[name] = find_wettest_window(
                dataset, name, interval_hours=interval_hours
            )
    return output


def _timestamp_label(value) -> str:
    """Format a time coordinate value as ``YYYY-MM-DDTHH:MM:SSZ``."""
    if hasattr(value, "strftime"):          # cftime or datetime
        return value.strftime("%Y-%m-%dT%H:%M:%SZ")
    return str(np.datetime_as_string(value, unit="s")) + "Z"


def _time_deltas(times) -> list[timedelta]:
    """Consecutive gaps in a time coordinate, as ``timedelta`` objects."""
    values = list(np.atleast_1d(times))
    deltas = []
    for earlier, later in zip(values, values[1:]):
        gap = later - earlier
        if isinstance(gap, np.timedelta64):
            gap = timedelta(microseconds=float(gap / np.timedelta64(1, "us")))
        deltas.append(gap)
    return deltas


def combine_imerg_subsets(
    paths: Sequence[Path],
    expected_interval_minutes: int = 30,
) -> xr.Dataset:
    """Combine per-granule IMERG subsets into one time-ordered dataset.

    Every file is read with :func:`read_imerg_subset`, so each arrives already
    normalised to ``(time, lat, lon)`` with fills masked to NaN. The result is
    sorted ascending in time and validated for duplicates, gaps and grid
    consistency — silent misalignment here would corrupt every downstream
    accumulation.

    Args:
        paths: Paths to Harmony IMERG NetCDF subsets.
        expected_interval_minutes: Required spacing between consecutive
            granules; IMERG half-hourly is 30.

    Returns:
        Combined dataset whose ``precipitation`` is ``(time, lat, lon)``.

    Raises:
        ValueError: if `paths` is empty, timestamps duplicate, the spacing is
            irregular, the grids differ, or dimensions are not
            ``(time, lat, lon)``.
    """
    if not paths:
        raise ValueError("No IMERG subset paths supplied.")

    expected_gap = timedelta(minutes=expected_interval_minutes)
    loaded: list[xr.Dataset] = []
    reference: xr.Dataset | None = None

    for path in paths:
        dataset = read_imerg_subset(Path(path))
        try:
            dims = tuple(dataset["precipitation"].dims)
            if dims != ("time", "lat", "lon"):
                raise ValueError(
                    f"{Path(path).name}: precipitation dimensions are {dims}, "
                    "expected ('time', 'lat', 'lon')."
                )
            if reference is None:
                reference = dataset
            else:
                for axis in ("lat", "lon"):
                    if dataset[axis].size != reference[axis].size or not np.allclose(
                        dataset[axis].values, reference[axis].values,
                        rtol=0, atol=1e-6,
                    ):
                        raise ValueError(
                            f"{Path(path).name}: {axis} grid differs from "
                            f"{Path(paths[0]).name}; refusing to combine "
                            "mismatched grids."
                        )
            loaded.append(dataset.load())
        finally:
            dataset.close()

    combined = xr.concat(loaded, dim="time", data_vars="minimal",
                         coords="minimal", compat="override")
    combined = combined.sortby("time")

    labels = [_timestamp_label(t) for t in np.atleast_1d(combined["time"].values)]
    duplicates = sorted({label for label in labels if labels.count(label) > 1})
    if duplicates:
        raise ValueError(
            f"Duplicate timestamps in the combined dataset: {duplicates}. "
            "Each granule must appear exactly once."
        )

    gaps = _time_deltas(combined["time"].values)
    irregular = [
        (labels[i], labels[i + 1], gap)
        for i, gap in enumerate(gaps) if gap != expected_gap
    ]
    if irregular:
        detail = "; ".join(
            f"{a} -> {b} is {int(g.total_seconds() // 60)} min"
            for a, b, g in irregular
        )
        raise ValueError(
            f"Irregular or missing {expected_interval_minutes}-minute "
            f"intervals: {detail}. Expected every gap to be "
            f"{expected_interval_minutes} minutes."
        )

    dims = tuple(combined["precipitation"].dims)
    if dims != ("time", "lat", "lon"):
        raise ValueError(
            f"Combined precipitation dimensions are {dims}, expected "
            "('time', 'lat', 'lon')."
        )

    combined.attrs["source_product"] = SOURCE_PRODUCT
    combined.attrs["granule_count"] = len(labels)
    combined.attrs["granule_interval_minutes"] = expected_interval_minutes
    combined.attrs["window_start_utc"] = labels[0]

    logger.info(
        "Combined %d granules: precipitation%s %s -> %s",
        len(labels), tuple(combined["precipitation"].shape),
        labels[0], labels[-1],
    )
    return combined


def calculate_rainfall_accumulation(
    dataset: xr.Dataset,
    interval_hours: float = 0.5,
    output_variable: str = "rain_3h_mm",
) -> xr.Dataset:
    """Accumulate a rate series into total rainfall depth over the window.

    The accumulation duration is *derived* as
    ``interval_hours * number_of_time_steps`` — never hard-coded — so the same
    function serves 1 h, 3 h, 6 h or 24 h windows.

    NaN is treated as unknown rather than zero: if any interval in a cell is
    missing, that cell's total is NaN. Summing a gap as zero would silently
    understate rainfall.

    Args:
        dataset: Combined dataset from :func:`combine_imerg_subsets`.
        interval_hours: Duration each time step represents.
        output_variable: Name for the accumulated-depth variable.

    Returns:
        A new dataset with ``precipitation_depth_mm`` (time, lat, lon) and
        ``output_variable`` (lat, lon) added. The ``mm/hr`` rate is preserved.

    Raises:
        KeyError: if `dataset` has no ``precipitation`` variable.
        ValueError: if `interval_hours` is not positive, or precipitation
            contains negative values that are not masked fills.
    """
    if "precipitation" not in dataset.variables:
        raise KeyError("Dataset has no 'precipitation' variable.")
    if interval_hours <= 0:
        raise ValueError(
            f"interval_hours must be positive, got {interval_hours!r}"
        )

    precip = dataset["precipitation"]
    values = np.asarray(precip.values, dtype="float64")

    # Fill values are already NaN by this point, so any surviving negative is
    # a genuine data problem rather than a sentinel.
    finite = values[~np.isnan(values)]
    if finite.size and float(finite.min()) < 0.0:
        worst = float(finite.min())
        raise ValueError(
            f"Negative precipitation rate found ({worst} mm/hr). Source fill "
            f"values should already be NaN; a negative rate is invalid. "
            "Check read_imerg_subset() masking before accumulating."
        )

    interval_count = int(precip.sizes["time"])
    accumulation_hours = float(interval_hours) * interval_count

    depth = precip * interval_hours
    depth.attrs = {
        "units": "mm",
        "long_name": "Precipitation depth per granule interval",
        "interval_hours": interval_hours,
        "derived_from": "precipitation (mm/hr) * interval_hours",
    }

    # skipna=False: a missing interval makes the total unknown, not smaller.
    total = depth.sum(dim="time", skipna=False)

    times = np.atleast_1d(dataset["time"].values)
    window_start = _timestamp_label(times[0])
    last = times[-1]
    try:
        window_end = _timestamp_label(last + timedelta(hours=interval_hours))
    except TypeError:  # numpy datetime64 needs a numpy delta
        window_end = _timestamp_label(
            last + np.timedelta64(int(interval_hours * 3600), "s")
        )

    total.attrs = {
        "units": "mm",
        "long_name": f"Accumulated rainfall depth over {accumulation_hours} h",
        "accumulation_hours": accumulation_hours,
        "interval_hours": float(interval_hours),
        "interval_count": interval_count,
        "window_start_utc": window_start,
        "window_end_utc": window_end,
        "source_product": SOURCE_PRODUCT,
        "nan_policy": "NaN if any interval in the cell is missing",
    }

    result = dataset.copy()
    result["precipitation_depth_mm"] = depth
    result[output_variable] = total
    result.attrs["source_product"] = SOURCE_PRODUCT
    result.attrs["accumulation_hours"] = accumulation_hours
    result.attrs["window_start_utc"] = window_start
    result.attrs["window_end_utc"] = window_end

    logger.info(
        "Accumulated %s: %d x %s h = %s h, %s -> %s",
        output_variable, interval_count, interval_hours, accumulation_hours,
        window_start, window_end,
    )
    return result


#: Trailing rolling accumulations: variable name -> half-hour interval count.
ROLLING_WINDOWS: dict[str, int] = {
    "rain_1h_mm": 2,
    "rain_3h_mm": 6,
    "rain_6h_mm": 12,
    "rain_24h_mm": 48,
}


def add_rolling_accumulations(
    dataset: xr.Dataset,
    windows: dict[str, int] | None = None,
    interval_hours: float = 0.5,
    source_variable: str = "precipitation_depth_mm",
) -> xr.Dataset:
    """Add trailing rolling rainfall accumulations, one per requested window.

    Each output is a **trailing** sum: the value at time *t* covers the
    ``interval_count`` intervals ending with *t*. The first
    ``interval_count - 1`` steps are NaN because a full window is not yet
    available — ``min_periods`` equals the full interval count, never less.

    Missing data propagates: if any interval inside a window is NaN, the whole
    window is NaN (``skipna=False`` semantics). Nothing is interpolated and no
    missing value is treated as zero — a gap makes the total unknown, not
    smaller.

    Args:
        dataset: Dataset containing `source_variable` on ``(time, lat, lon)``.
        windows: Mapping of output name to interval count; defaults to
            :data:`ROLLING_WINDOWS`.
        interval_hours: Hours represented by one interval.
        source_variable: Per-interval depth variable to accumulate.

    Returns:
        A new dataset with one ``(time, lat, lon)`` variable per window.

    Raises:
        KeyError: if `source_variable` is absent.
        ValueError: if an interval count is not a positive integer, exceeds the
            available time steps, or `interval_hours` is not positive.
    """
    if source_variable not in dataset.variables:
        raise KeyError(
            f"Dataset has no {source_variable!r}; call "
            "precipitation_rate_to_depth() first."
        )
    if interval_hours <= 0:
        raise ValueError(
            f"interval_hours must be positive, got {interval_hours!r}"
        )

    windows = dict(windows) if windows else dict(ROLLING_WINDOWS)
    depth = dataset[source_variable]
    n_times = int(depth.sizes["time"])

    result = dataset.copy()
    for name, interval_count in windows.items():
        if not isinstance(interval_count, int) or interval_count < 1:
            raise ValueError(
                f"{name}: interval_count must be a positive integer, "
                f"got {interval_count!r}"
            )
        if interval_count > n_times:
            raise ValueError(
                f"{name}: needs {interval_count} intervals but the dataset "
                f"has only {n_times}."
            )

        # construct() pads the leading edge with NaN, so summing with
        # skipna=False yields NaN until a full window exists. This is
        # min_periods == interval_count and NaN propagation in one step.
        stacked = depth.rolling(
            time=interval_count, min_periods=interval_count, center=False
        ).construct("_window")
        rolled = stacked.sum("_window", skipna=False)
        rolled = rolled.transpose("time", "lat", "lon")

        window_hours = float(interval_hours) * interval_count
        rolled.attrs = {
            "units": "mm",
            "long_name": f"Trailing {window_hours:g} h accumulated rainfall",
            "window_hours": window_hours,
            "interval_hours": float(interval_hours),
            "interval_count": interval_count,
            "rolling_alignment": "trailing",
            "missing_data_policy": "propagate_nan",
            "min_periods": interval_count,
            "source_product": SOURCE_PRODUCT,
        }
        result[name] = rolled

        logger.info(
            "Added %s: %d intervals = %g h trailing, first valid index %d",
            name, interval_count, window_hours, interval_count - 1,
        )

    return result


def find_wettest_window(
    dataset: xr.Dataset,
    variable: str,
    interval_hours: float | None = None,
) -> dict:
    """Locate the maximum trailing accumulation across all cells and times.

    A trailing value at time *t* spanning ``interval_count`` intervals covers
    ``[t - (interval_count - 1) * interval, t + interval)``, so the reported
    window start is the first contributing interval's timestamp and the window
    end is one interval past *t*.

    Args:
        dataset: Dataset containing `variable` from
            :func:`add_rolling_accumulations`.
        variable: Rolling accumulation variable name.
        interval_hours: Override for the interval length; taken from the
            variable's attributes when omitted.

    Returns:
        Dict with ``variable``, ``window_hours``, ``interval_count``,
        ``max_mm``, ``window_start_utc``, ``window_end_utc``,
        ``label_timestamp_utc``, ``lat``, ``lon``, and index positions.
        ``max_mm`` is ``None`` when every value is NaN.

    Raises:
        KeyError: if `variable` is absent.
    """
    if variable not in dataset.variables:
        raise KeyError(f"Dataset has no {variable!r}.")

    array = dataset[variable]
    interval = float(
        interval_hours
        if interval_hours is not None
        else array.attrs.get("interval_hours", 0.5)
    )
    interval_count = int(array.attrs.get("interval_count", 1))
    window_hours = float(array.attrs.get("window_hours",
                                         interval * interval_count))

    values = np.asarray(array.values, dtype="float64")
    if not np.any(np.isfinite(values)):
        return {
            "variable": variable,
            "window_hours": window_hours,
            "interval_count": interval_count,
            "max_mm": None,
            "note": "all values are NaN — no complete window available",
        }

    flat = int(np.nanargmax(values))
    t_index, lat_index, lon_index = np.unravel_index(flat, values.shape)

    times = np.atleast_1d(dataset["time"].values)
    label = times[int(t_index)]
    start_index = int(t_index) - (interval_count - 1)
    window_start = times[start_index]

    step = timedelta(hours=interval)
    try:
        window_end = label + step
    except TypeError:  # numpy datetime64 needs a numpy delta
        window_end = label + np.timedelta64(int(interval * 3600), "s")

    return {
        "variable": variable,
        "window_hours": window_hours,
        "interval_count": interval_count,
        "max_mm": float(values[t_index, lat_index, lon_index]),
        "window_start_utc": _timestamp_label(window_start),
        "window_end_utc": _timestamp_label(window_end),
        "label_timestamp_utc": _timestamp_label(label),
        "lat": float(dataset["lat"].values[int(lat_index)]),
        "lon": float(dataset["lon"].values[int(lon_index)]),
        "time_index": int(t_index),
        "lat_index": int(lat_index),
        "lon_index": int(lon_index),
    }


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )

    authenticate()

    granules = search_imerg(
        start_date="2016-10-25",
        end_date="2016-10-26",
        count=5,
    )

    print(f"Granules found: {len(granules)}")
