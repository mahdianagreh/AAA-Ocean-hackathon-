"""
Supabase Storage client — the file half of the architecture (§1 of data-model.md):
every pixel and grid cell lives here, never in Postgres. Pair every upload with a
`raster_assets` row (see backend/src/db/loaders/raster_assets.py) carrying the path,
CRS, checksum and source — nothing in Storage is anonymous.

Watch — secrets: the service-role key is not the anon key. It goes in the backend
environment only, never near the frontend bundle. `.env` was already committed once
in this project (commit 2f0a6d6) — do not be the second time.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from supabase import Client, create_client

REPO_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(REPO_ROOT / "backend" / ".env")

BUCKETS = ["rasters", "netcdf", "trajectories", "figures"]

_PROJECT_REF = "vcgpenwdaniwhvrucavm"
_DEFAULT_SUPABASE_URL = f"https://{_PROJECT_REF}.supabase.co"

_client: Client | None = None


def get_storage_client() -> Client:
    """The one Supabase client for Storage operations. Requires the service-role key
    (SUPABASE_SERVICE_ROLE_KEY) in backend/.env — never the anon key, and never in
    frontend code."""
    global _client
    if _client is not None:
        return _client

    url = os.getenv("SUPABASE_URL", _DEFAULT_SUPABASE_URL)
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not key:
        raise RuntimeError(
            "SUPABASE_SERVICE_ROLE_KEY is not set in backend/.env. "
            "Get it from Supabase → Project Settings → API → service_role secret."
        )
    _client = create_client(url, key)
    return _client


def upload_file(bucket: str, dest_path: str, local_path: Path, upsert: bool = True) -> str:
    """Upload one file to a bucket, returning the storage path. Idempotent: `upsert=True`
    overwrites an existing object at the same path rather than erroring, so loaders can
    be re-run safely."""
    if bucket not in BUCKETS:
        raise ValueError(f"Unknown bucket {bucket!r}; expected one of {BUCKETS}")

    client = get_storage_client()
    with open(local_path, "rb") as f:
        client.storage.from_(bucket).upload(
            dest_path,
            f.read(),
            file_options={"upsert": "true" if upsert else "false"},
        )
    return f"{bucket}/{dest_path}"
