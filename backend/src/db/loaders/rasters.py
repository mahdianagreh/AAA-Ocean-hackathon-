"""
Loader: project rasters -> Supabase Storage + `raster_assets`.

Per data-model.md §1: "every heavy file has a row in raster_assets carrying its
path, CRS, checksum, and the data_sources.id it came from. Nothing in data/ is
anonymous, and nothing in Postgres is a pixel." This uploads the bytes to Storage
and writes exactly that bridging row.

Idempotent: `upload_file(..., upsert=True)` overwrites the same Storage path, and
the `raster_assets` insert upserts on `path`, so re-running after a file changes
on disk is a single command.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import rasterio
from pyproj import Transformer
from sqlalchemy import text

from src.db.client import session_scope
from src.db.storage import upload_file

REPO_ROOT = Path(__file__).resolve().parents[4]

UPSERT_SQL = text(
    """
    INSERT INTO raster_assets (
        kind, source_id, path, format, crs, pixel_size_m, bbox, valid_time,
        bytes, checksum_sha256, is_provisional
    ) VALUES (
        :kind, :source_id, :path, :format, :crs, :pixel_size_m,
        ST_GeomFromText(:bbox_wkt, 4326), :valid_time, :bytes,
        :checksum_sha256, :is_provisional
    )
    ON CONFLICT (path) DO UPDATE SET
        kind = EXCLUDED.kind,
        source_id = EXCLUDED.source_id,
        format = EXCLUDED.format,
        crs = EXCLUDED.crs,
        pixel_size_m = EXCLUDED.pixel_size_m,
        bbox = EXCLUDED.bbox,
        valid_time = EXCLUDED.valid_time,
        bytes = EXCLUDED.bytes,
        checksum_sha256 = EXCLUDED.checksum_sha256,
        is_provisional = EXCLUDED.is_provisional
    """
)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _bbox_wkt_4326(local_path: Path) -> str:
    """Reproject the raster's bounds to EPSG:4326, since raster_assets.bbox is
    declared geometry(Polygon, 4326) regardless of the raster's own working CRS."""
    with rasterio.open(local_path) as src:
        b = src.bounds
        transformer = Transformer.from_crs(src.crs, "EPSG:4326", always_xy=True)
        corners = [(b.left, b.bottom), (b.right, b.bottom), (b.right, b.top), (b.left, b.top)]
        lonlat = [transformer.transform(x, y) for x, y in corners]
        ring = ", ".join(f"{lon} {lat}" for lon, lat in lonlat + [lonlat[0]])
        return f"POLYGON(({ring}))"


# (local path, bucket, storage key, kind, source_id, is_provisional, valid_time)
RASTERS = [
    dict(
        local_path=REPO_ROOT / "data" / "processed" / "bathymetry" / "depth_utm36n.tif",
        bucket="rasters",
        dest_path="bathymetry/depth_utm36n.tif",
        kind="depth",
        source_id="gmrt_bathymetry",
        is_provisional=False,
        valid_time=None,  # static layer
    ),
    dict(
        local_path=REPO_ROOT / "data" / "processed" / "plume" / "baseline_composite.tif",
        bucket="rasters",
        dest_path="plume/baseline_composite.tif",
        kind="baseline_composite",
        source_id="sentinel2_l2a_pc",
        is_provisional=False,
        valid_time=None,  # median of 9 pre-event scenes, no single valid time
    ),
    dict(
        local_path=REPO_ROOT / "data" / "processed" / "plume" / "observed_plume_probability.tif",
        bucket="rasters",
        dest_path="plume/observed_plume_probability.tif",
        kind="plume_probability",
        source_id="sentinel2_l2a_pc",
        is_provisional=False,
        # Post-event Sentinel-2 scene acquisition time (S2A_MSIL2A_20161102T082112).
        valid_time="2016-11-02T08:21:12+00:00",
    ),
]


def load_rasters() -> dict[str, int]:
    """Upload every raster in RASTERS and upsert its raster_assets row.
    Returns the storage path -> raster_assets.id mapping for callers that need to
    link (e.g. observed_plumes.probability_raster_id)."""
    ids: dict[str, int] = {}
    with session_scope() as session:
        for r in RASTERS:
            local_path: Path = r["local_path"]
            if not local_path.exists():
                print(f"SKIP {r['kind']}: missing {local_path}")
                continue

            storage_path = upload_file(r["bucket"], r["dest_path"], local_path)

            with rasterio.open(local_path) as src:
                crs = str(src.crs)
                pixel_size_m = float(src.res[0])

            row = session.execute(
                UPSERT_SQL,
                dict(
                    kind=r["kind"],
                    source_id=r["source_id"],
                    path=storage_path,
                    format="GeoTIFF",
                    crs=crs,
                    pixel_size_m=pixel_size_m,
                    bbox_wkt=_bbox_wkt_4326(local_path),
                    valid_time=r["valid_time"],
                    bytes=local_path.stat().st_size,
                    checksum_sha256=_sha256(local_path),
                    is_provisional=r["is_provisional"],
                ),
            )
            asset_id = session.execute(
                text("SELECT id FROM raster_assets WHERE path = :p"), {"p": storage_path}
            ).scalar_one()
            ids[storage_path] = asset_id
            print(f"Uploaded {r['kind']} -> {storage_path} (raster_assets.id={asset_id})")
    return ids


if __name__ == "__main__":
    load_rasters()
