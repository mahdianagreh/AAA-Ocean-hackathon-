"""
Loader: Abd's satellite imagery audit + observed plume -> `satellite_scenes`,
`observed_plumes`.

Source: data/processed/vectors/observed_plume.gpkg (110 small polygons, all at
probability_threshold=0.7 — dissolved here into the single MultiPolygon the
`observed_plumes.geom` column expects) plus the documented scene facts from
docs/data_dictionary.md §8 and docs/event_audit.md.

**Honesty flag, carried through on purpose (data-model.md §3.4, §22.4):** the
concept doc and event_audit.md are explicit that this raster is a documented
artifact, not a validated plume detection — the coastline-hugging anomaly comes
from atmospheric-correction/sun-angle noise, and both available satellite
passes were 2.5-3.5 days after the real plume (per the Kalman et al. 2025
mooring) had already dispersed. `decision='rejected'` and `label_tier='bronze'`
reflect that verdict; this is not a Gold observation.

Idempotent: both tables upsert on primary key.
"""

from __future__ import annotations

import datetime as dt

import geopandas as gpd
from sqlalchemy import text

from src.db.client import session_scope

EVENT_ID = "AQ-2016-10-28"
SCENE_ID = "S2A_MSIL2A_20161102T082112_R121_T36RXT_20210213T163836"

REPO_ROOT_PLUME_GPKG = "data/processed/vectors/observed_plume.gpkg"


def _repo_root():
    from pathlib import Path

    return Path(__file__).resolve().parents[4]


UPSERT_SCENE_SQL = text(
    """
    INSERT INTO satellite_scenes (
        id, source_id, platform, acquisition_time, event_id, days_from_event,
        role, cloud_pct_scene, cloud_pct_aoi_water, plume_visible, decision,
        decision_reason
    ) VALUES (
        :id, :source_id, :platform, :acquisition_time, :event_id, :days_from_event,
        :role, :cloud_pct_scene, :cloud_pct_aoi_water, :plume_visible, :decision,
        :decision_reason
    )
    ON CONFLICT (id) DO UPDATE SET
        acquisition_time = EXCLUDED.acquisition_time,
        event_id = EXCLUDED.event_id,
        days_from_event = EXCLUDED.days_from_event,
        role = EXCLUDED.role,
        cloud_pct_scene = EXCLUDED.cloud_pct_scene,
        cloud_pct_aoi_water = EXCLUDED.cloud_pct_aoi_water,
        plume_visible = EXCLUDED.plume_visible,
        decision = EXCLUDED.decision,
        decision_reason = EXCLUDED.decision_reason
    """
)

UPSERT_PLUME_SQL = text(
    """
    INSERT INTO observed_plumes (
        event_id, scene_id, acquisition_time, index_used, threshold_value,
        baseline_raster_id, probability_raster_id, geom, area_km2, centroid,
        label_tier, quality_score, qc_notes, is_provisional
    ) VALUES (
        :event_id, :scene_id, :acquisition_time, :index_used, :threshold_value,
        :baseline_raster_id, :probability_raster_id,
        ST_Multi(ST_GeomFromText(:geom_wkt, 4326)), :area_km2,
        ST_GeomFromText(:centroid_wkt, 4326), :label_tier, :quality_score,
        :qc_notes, :is_provisional
    )
    """
)
# No natural-key uniqueness on this table (bigserial id only) — idempotency is
# enforced by the manual existence check in load_observed_plume() below, not by
# ON CONFLICT.


def seed_satellite_scene() -> None:
    acquisition_time = dt.datetime(2016, 11, 2, 8, 21, 12, tzinfo=dt.timezone.utc)
    event_peak = dt.datetime(2016, 10, 28, 6, 50, tzinfo=dt.timezone.utc)
    days_from_event = (acquisition_time - event_peak).total_seconds() / 86400.0

    with session_scope() as session:
        session.execute(
            UPSERT_SCENE_SQL,
            dict(
                id=SCENE_ID,
                source_id="sentinel2_l2a_pc",
                platform="S2A",
                acquisition_time=acquisition_time,
                event_id=EVENT_ID,
                days_from_event=days_from_event,
                role="post_event",
                cloud_pct_scene=3.6,
                cloud_pct_aoi_water=0.07,
                plume_visible="no",
                decision="rejected",
                decision_reason=(
                    "No plume visible. NO-GO for satellite validation per "
                    "docs/event_audit.md §1a — two independent sensors and the "
                    "Kalman et al. 2025 mooring agree the real plume had already "
                    "dispersed before this pass (2.5-3.5 days post-event)."
                ),
            ),
        )


def load_observed_plume() -> int:
    gpkg_path = _repo_root() / REPO_ROOT_PLUME_GPKG
    if not gpkg_path.exists():
        print(f"SKIP observed_plumes: missing {gpkg_path}")
        return 0

    patches = gpd.read_file(gpkg_path)
    # 110 small polygons -> one dissolved MultiPolygon per data-model.md's
    # "one observation" shape (observed_plumes.geom is a single MultiPolygon).
    dissolved = patches.union_all()
    dissolved_gdf = gpd.GeoSeries([dissolved], crs=patches.crs)
    area_km2 = float(dissolved_gdf.area.iloc[0] / 1e6)  # already in EPSG:32636 (metres)
    dissolved_4326 = dissolved_gdf.to_crs("EPSG:4326").iloc[0]
    centroid_4326 = dissolved_gdf.centroid.to_crs("EPSG:4326").iloc[0]

    with session_scope() as session:
        baseline_id = session.execute(
            text("SELECT id FROM raster_assets WHERE path = :p"),
            {"p": "rasters/plume/baseline_composite.tif"},
        ).scalar_one_or_none()
        probability_id = session.execute(
            text("SELECT id FROM raster_assets WHERE path = :p"),
            {"p": "rasters/plume/observed_plume_probability.tif"},
        ).scalar_one_or_none()

        exists = session.execute(
            text("SELECT 1 FROM observed_plumes WHERE event_id = :e AND scene_id = :s"),
            {"e": EVENT_ID, "s": SCENE_ID},
        ).first()
        if exists:
            print("observed_plumes row already present for this (event, scene) — skipping insert.")
            return 0

        session.execute(
            UPSERT_PLUME_SQL,
            dict(
                event_id=EVENT_ID,
                scene_id=SCENE_ID,
                acquisition_time=dt.datetime(2016, 11, 2, 8, 21, 12, tzinfo=dt.timezone.utc),
                index_used="reflectance_anomaly",
                threshold_value=0.7,
                baseline_raster_id=baseline_id,
                probability_raster_id=probability_id,
                geom_wkt=dissolved_4326.wkt,
                area_km2=area_km2,
                centroid_wkt=centroid_4326.wkt,
                label_tier="bronze",
                quality_score=0.1,
                qc_notes=(
                    "Documented artifact, not a validated detection — coastline-hugging "
                    "anomaly from atmospheric-correction/sun-angle noise, confirmed by "
                    "testing a same-season baseline and a larger coastal buffer without "
                    "it going away. See docs/event_audit.md §1a. Do not consume as "
                    "ground truth."
                ),
                is_provisional=False,
            ),
        )
    return 1


def run() -> None:
    seed_satellite_scene()
    print(f"Upserted satellite_scenes row for {SCENE_ID}.")
    n = load_observed_plume()
    print(f"Inserted {n} observed_plumes row(s).")


if __name__ == "__main__":
    run()
