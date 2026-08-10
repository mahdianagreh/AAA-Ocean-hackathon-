"""The plume map renders real geometry, and nothing in it is generated.

This exists because the alternative was AI-generated imagery of a predicted flood, and
the failure mode of that choice is invisible: a diffusion model draws a confident wrong
coastline, the result looks like satellite imagery, and it reads as an OBSERVATION in a
project whose validation story is "the satellite could not see the plume, so we said so".

So the guarantees worth pinning are about provenance and about geometry being real:

  - contours are clipped to the sea, which is the check that exposed the synthetic stub
    returning circles over Aqaba's city centre, the airport and a golf course
  - a missing basemap degrades honestly instead of being faked
  - the animation frames share one extent, so a growing plume actually appears to grow
  - the response says, in a header and burned into the image, that nothing is generated
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend" / "src"))

pytest.importorskip("matplotlib")
pytest.importorskip("PIL")

from rendering import plume_map as pm  # noqa: E402

VECTORS = PROJECT_ROOT / "data" / "processed" / "vectors"


def _contour(t_hours: float, probability: float, coords) -> dict:
    return {"t_hours": t_hours, "probability": probability,
            "geometry": {"type": "Polygon", "coordinates": [coords]}}


#: A square straddling the Aqaba shoreline: its western half is sea, its eastern half is
#: the city. Clipping must keep only the western half.
STRADDLING = [(34.96, 29.52), (35.02, 29.52), (35.02, 29.56), (34.96, 29.56),
              (34.96, 29.52)]


@pytest.mark.skipif(not (VECTORS / "coastline.gpkg").exists(),
                    reason="coastline not built")
def test_contours_are_clipped_to_the_sea():
    """The check that caught the stub. A marine plume cannot cross the shoreline.

    The synthetic particle stub returns concentric circles around the release point with
    no knowledge of the coast, so unclipped the plume covered the city, the airport and a
    golf course. That fault was invisible in JSON and obvious the moment it was drawn —
    which is the whole argument for rendering real geometry rather than generating a
    picture, because a generated picture would have drawn a plausible coast instead.
    """
    contours = [_contour(6.0, 0.7, STRADDLING)]

    clipped = pm.contours_to_frame(contours, clip_to_sea=True)
    raw = pm.contours_to_frame(contours, clip_to_sea=False)

    assert not raw.empty and not clipped.empty
    assert clipped.geometry.area.sum() < raw.geometry.area.sum(), (
        "clipping removed nothing — either the coastline layer is wrong or the test "
        "square no longer straddles the shore"
    )
    # And what survives must be inside the sea, not merely smaller.
    import geopandas as gpd

    sea = gpd.read_file(VECTORS / "coastline.gpkg", layer="water").to_crs(pm.WEB).union_all()
    assert clipped.geometry.iloc[0].difference(sea.buffer(1)).area < 1.0


def test_contours_are_reprojected_to_web_mercator():
    """Input is lon/lat; drawing happens in EPSG:3857. A missed reprojection puts the
    plume in the Gulf of Guinea, which is where 0,0 lives."""
    frame = pm.contours_to_frame([_contour(3.0, 0.8, STRADDLING)], clip_to_sea=False)
    assert frame.crs.to_string() == pm.WEB
    minx, miny, maxx, maxy = frame.total_bounds
    assert 3_800_000 < minx < 4_000_000, minx     # Aqaba longitude in metres
    assert 3_300_000 < miny < 3_600_000, miny


def test_empty_contours_do_not_raise():
    """No plume is a legitimate answer — an outlet that discharges into an enclosed
    basin may produce nothing. It must render, not 500."""
    assert pm.contours_to_frame([], clip_to_sea=True).empty
    png = pm.render([], event_id="AQ-2016-10-28", outlet_id="AQ-O01",
                    horizon_hours=24)
    assert png.startswith(b"\x89PNG")


def test_frame_times_are_sorted_and_unique():
    times = pm.frame_times([_contour(24, 0.4, STRADDLING), _contour(3, 0.8, STRADDLING),
                            _contour(3, 0.8, STRADDLING), _contour(12, 0.6, STRADDLING)])
    assert times == [3.0, 12.0, 24.0]


def test_a_missing_basemap_is_reported_not_faked(tmp_path, monkeypatch):
    """A fresh clone has no basemap: it is derived and git-ignored.

    The renderer must still produce an image and say the background is blank. Inventing
    or approximating imagery here would be the exact substitution this module exists to
    avoid.
    """
    monkeypatch.setattr(pm, "BASEMAP_DIR", tmp_path)
    assert pm.load_basemap(tmp_path) is None

    png = pm.render([_contour(6.0, 0.7, STRADDLING)], event_id="AQ-2016-10-28",
                    outlet_id="AQ-O01", horizon_hours=24)
    assert png.startswith(b"\x89PNG")


def test_basemap_metadata_records_its_extent_by_name():
    """`left/right/bottom/top` spelled out, not a bare 4-tuple.

    contextily returns (left, right, bottom, top) — which matches neither `.wsen` nor
    `.nwse` nor `.cds_area`, the three orderings already in this project. A silent
    reorder would place every plume in the wrong sea, and it would look fine.
    """
    meta_path = pm.BASEMAP_DIR / f"{pm.BASEMAP_STEM}.json"
    if not meta_path.exists():
        pytest.skip("basemap not baked")
    meta = json.loads(meta_path.read_text())
    for key in ("left", "right", "bottom", "top", "crs", "attribution", "fetched_utc"):
        assert key in meta, key
    assert meta["crs"] == pm.WEB
    assert meta["left"] < meta["right"] and meta["bottom"] < meta["top"]


@pytest.mark.skipif(not (pm.BASEMAP_DIR / f"{pm.BASEMAP_STEM}.json").exists(),
                    reason="basemap not baked")
def test_every_frame_shares_one_extent():
    """Frames must register against each other or the animation is meaningless.

    The extent is computed from the FULL contour set, so `upto_hours` changes what is
    drawn and never what is framed. Framing on the visible subset would rescale each
    frame and a growing plume would appear static.
    """
    from PIL import Image

    contours = [_contour(3.0, 0.8, STRADDLING), _contour(12.0, 0.6, STRADDLING),
                _contour(24.0, 0.4, STRADDLING)]
    sizes = set()
    for upto in (3.0, 12.0, 24.0):
        png = pm.render(contours, event_id="AQ-2016-10-28", outlet_id="AQ-O01",
                        horizon_hours=24, upto_hours=upto)
        with Image.open(io.BytesIO(png)) as im:
            sizes.add(im.size)
    assert len(sizes) == 1, f"frames differ in size: {sizes}"


def test_risk_colours_cover_every_band_the_engine_emits():
    """The map and the risk cards must not disagree about what 'high' looks like."""
    from exposure.engine import risk_level

    emitted = {risk_level(s / 100) for s in range(0, 101, 5)}
    assert emitted <= set(pm.RISK_COLOURS), emitted - set(pm.RISK_COLOURS)


@pytest.mark.skipif(not (VECTORS / "reef_zones.gpkg").exists(), reason="no reef zones")
def test_unscored_zones_are_not_labelled_nan():
    """`.map` over missing keys yields NaN, not None, so a `is not None` guard let every
    unscored zone render as "R-02 · nan" on the image."""
    import pandas as pd

    zones = pm._reef_zones({"R-01": {"risk_level": "high", "risk_score": 62.0}})
    assert zones is not None
    scored = zones[zones["reef_zone_id"] == "R-01"].iloc[0]
    assert pd.notna(scored["risk_score"])
    others = zones[zones["reef_zone_id"] != "R-01"]
    assert others["risk_score"].isna().all(), "unscored zones must be NaN, not a number"


class TestEndpoint:
    """The HTTP surface, including the provenance headers."""

    @pytest.fixture(scope="class")
    @classmethod
    def client(cls):
        pytest.importorskip("fastapi")
        from fastapi.testclient import TestClient

        from api.main import app
        return TestClient(app)

    def test_map_returns_a_png(self, client):
        r = client.get("/api/v1/plume/map",
                       params={"event_id": "AQ-2016-10-28", "outlet_id": "AQ-O01"})
        assert r.status_code == 200, r.text[:300]
        assert r.headers["content-type"] == "image/png"
        assert r.content.startswith(b"\x89PNG")

    def test_headers_declare_that_nothing_is_generated(self, client):
        """Machine-readable provenance beside the footer burned into the image, so a
        client can label it without reading pixels."""
        r = client.get("/api/v1/plume/map",
                       params={"event_id": "AQ-2016-10-28", "outlet_id": "AQ-O01"})
        assert r.headers["X-ReefShield-Generated-Imagery"] == "none"
        assert r.headers["X-ReefShield-Plume-Source"] in {"stub", "particle-engine"}
        assert r.headers["X-ReefShield-Basemap"] in {"esri-worldimagery-baked", "absent"}

    def test_frames_lists_only_times_the_simulation_produced(self, client):
        """Returned rather than assumed, so the client cannot request a timestep that
        does not exist."""
        r = client.get("/api/v1/plume/map/frames",
                       params={"event_id": "AQ-2016-10-28", "outlet_id": "AQ-O01"})
        assert r.status_code == 200
        body = r.json()
        assert body["frame_count"] == len(body["frames"]) > 0
        times = [f["t_hours"] for f in body["frames"]]
        assert times == sorted(times)
        for f in body["frames"]:
            assert f"upto_hours={f['t_hours']:g}" in f["url"]

    def test_frames_carry_forcing_provenance_verbatim_from_the_run(self, client):
        """05-abd.md core-C: the UI must render the currents/wind provenance rather
        than assert its own copy of it, which means the frames endpoint -- the one
        the dashboard plume panel and Replay actually call -- has to carry it."""
        r = client.get("/api/v1/plume/map/frames",
                       params={"event_id": "AQ-2016-10-28", "outlet_id": "AQ-O01"})
        assert r.status_code == 200
        body = r.json()
        assert body["provenance"], "no provenance -- the UI would have nothing to render"
        assert any("current" in p["detail"].lower() for p in body["provenance"])
        assert body["caveats"], "no caveats -- wind-is-zero would be unstated"
        assert any("ConstantWindField(0, 0)" in c["message"] for c in body["caveats"])
        # AQ-2016-10-28 is the one event `data/models/plume_calibration.json` is
        # calibrated against, so this checkout must resolve the tie-break fields --
        # not fall back to the "no calibration ran" None branch.
        assert body["windage_is_tiebreak"] is True
        assert body["windage_fraction"] == 0.0
        assert "tie-break" in body["windage_caveat"]

    def test_windage_fields_are_none_when_uncalibrated_for_this_event(self, client, monkeypatch):
        """A different event has no calibration fit against it -- the response must
        say "not calibrated" (None), never silently reuse the anchor's numbers."""
        import api.main as main_module
        monkeypatch.setattr(main_module, "_load_plume_calibration", lambda: None)
        r = client.get("/api/v1/plume/map/frames",
                       params={"event_id": "AQ-2016-10-28", "outlet_id": "AQ-O01"})
        assert r.status_code == 200
        body = r.json()
        assert body["windage_fraction"] is None
        assert body["windage_is_tiebreak"] is False
        assert body["windage_caveat"] is None

    def test_unknown_outlet_is_404_not_a_blank_map(self, client):
        r = client.get("/api/v1/plume/map",
                       params={"event_id": "AQ-2016-10-28", "outlet_id": "AQ-O99"})
        assert r.status_code == 404
