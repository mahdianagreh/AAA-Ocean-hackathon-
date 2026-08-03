"""Central credential/config loader for ReefShield Aqaba.

Import this ONCE at the top of any script that touches an external data
source.  It loads `.env` into the process environment, so libraries that
read standard variables themselves (earthaccess, cdsapi,
copernicusmarine) just work with no extra wiring:

    from src.config import settings
    import earthaccess
    earthaccess.login(strategy="environment")

Never hard-code a credential in a script, and never print one.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"

# override=False: a real shell/CI variable always wins over the file.
load_dotenv(ENV_FILE, override=False)


def _get(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


# Settings field -> the .env variable it comes from. Most are the field name
# upper-cased, but the Copernicus Marine toolbox insists on long names, so
# error messages must not guess.
ENV_VAR_NAMES = {
    "earthdata_username": "EARTHDATA_USERNAME",
    "earthdata_password": "EARTHDATA_PASSWORD",
    "cdsapi_url": "CDSAPI_URL",
    "cdsapi_key": "CDSAPI_KEY",
    "cmems_username": "COPERNICUSMARINE_SERVICE_USERNAME",
    "cmems_password": "COPERNICUSMARINE_SERVICE_PASSWORD",
    "cdse_username": "CDSE_USERNAME",
    "cdse_password": "CDSE_PASSWORD",
    "cdse_s3_access_key": "CDSE_S3_ACCESS_KEY",
    "cdse_s3_secret_key": "CDSE_S3_SECRET_KEY",
    "cdse_s3_endpoint": "CDSE_S3_ENDPOINT",
    "earthengine_project": "EARTHENGINE_PROJECT",
    "google_credentials": "GOOGLE_APPLICATION_CREDENTIALS",
    "aoi_name": "AOI_NAME",
}


def env_name(field: str) -> str:
    """The .env variable backing a Settings field."""
    return ENV_VAR_NAMES.get(field, field.upper())


@dataclass(frozen=True)
class Settings:
    """Resolved configuration. Values may be empty if not yet registered."""

    # 1. NASA Earthdata — IMERG, HLS, SRTM
    earthdata_username: str = _get("EARTHDATA_USERNAME")
    earthdata_password: str = _get("EARTHDATA_PASSWORD")

    # 2. Copernicus CDS — ERA5-Land
    cdsapi_url: str = _get("CDSAPI_URL", "https://cds.climate.copernicus.eu/api")
    cdsapi_key: str = _get("CDSAPI_KEY")

    # 3. Copernicus Marine — ocean currents
    cmems_username: str = _get("COPERNICUSMARINE_SERVICE_USERNAME")
    cmems_password: str = _get("COPERNICUSMARINE_SERVICE_PASSWORD")

    # 4. Copernicus Data Space — Sentinel-2 L2A
    cdse_username: str = _get("CDSE_USERNAME")
    cdse_password: str = _get("CDSE_PASSWORD")
    cdse_s3_access_key: str = _get("CDSE_S3_ACCESS_KEY")
    cdse_s3_secret_key: str = _get("CDSE_S3_SECRET_KEY")
    cdse_s3_endpoint: str = _get(
        "CDSE_S3_ENDPOINT", "https://eodata.dataspace.copernicus.eu"
    )

    # 5. Google Earth Engine
    earthengine_project: str = _get("EARTHENGINE_PROJECT", "reefshield-aqaba-504407")
    google_credentials: str = _get("GOOGLE_APPLICATION_CREDENTIALS")

    # Project paths
    aoi_name: str = _get("AOI_NAME", "aqaba")

    @property
    def data_dir(self) -> Path:
        raw = _get("DATA_DIR", "./data")
        path = Path(raw)
        return path if path.is_absolute() else PROJECT_ROOT / path

    def require(self, *names: str) -> None:
        """Fail fast with a useful message instead of a confusing 401.

        >>> settings.require("earthdata_username", "earthdata_password")
        """
        missing = [n for n in names if not getattr(self, n, "")]
        if missing:
            raise RuntimeError(
                "Missing credentials in .env: "
                + ", ".join(env_name(m) for m in missing)
                + f"\nEdit {ENV_FILE} — see .env.example for where to register."
            )


settings = Settings()

__all__ = ["settings", "Settings", "PROJECT_ROOT", "ENV_FILE", "env_name"]
