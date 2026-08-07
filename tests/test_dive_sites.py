"""Dive Site Safety Status — tasks/phase4/04-pulga.md item 5, feature B.

Unblocked by Karam's 6 Aug handoff: `osm_id` is now a stable join key in
`frontend/public/basemap/places.geojson` (115/115 unique, confirmed against the
source OSM re-extract). This tests the join `GET /api/v1/dive-sites` performs —
nearest reef zone by real EPSG:32636 distance — and a real finding made while
building it: the source OSM category (`kind: dive`) is not a clean "underwater
dive site" filter. It also carries Wadi Rum desert attractions (Siq al Khazali,
Barrah Canyon, sand dunes, petroglyphs) 32.5 km or more inland — a genuine data
quality issue in the input, not a bug in the join, and the API must say so rather
than either silently drop those rows or silently present them as real dive
sites at zero cost to plausibility.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend" / "src"))

os.environ.setdefault(
    "REEFSHIELD_EXPOSURE_DB", str(Path(tempfile.mkdtemp()) / "test_dive_sites.sqlite")
)


def _client():
    from api.main import app
    from fastapi.testclient import TestClient

    return TestClient(app)


def test_dive_sites_endpoint_returns_the_real_places_not_a_placeholder():
    from api.main import PREFIX

    client = _client()
    r = client.get(f"{PREFIX}/dive-sites")
    assert r.status_code == 200
    sites = r.json()
    assert len(sites) == 46, "expected exactly the 46 kind=dive POIs in places.geojson"
    names = {s["name_en"] for s in sites}
    assert "Cedar Pride Shipwreck" in names
    assert "Rainbow reef" in names


def test_every_site_has_a_stable_osm_id_and_a_measured_distance():
    from api.main import PREFIX

    client = _client()
    sites = client.get(f"{PREFIX}/dive-sites").json()
    ids = [s["osm_id"] for s in sites]
    assert len(ids) == len(set(ids)), "osm_id must be unique — it is the join key"
    for s in sites:
        assert s["osm_id"], s
        assert s["nearest_reef_zone_id"] is not None
        assert s["distance_m"] is not None
        assert s["distance_m"] >= 0


def test_real_coastal_dive_sites_are_not_flagged():
    """Known real dive/wreck sites, measured 0-997 m from a reef zone during
    development — must come back with no caveat."""
    from api.main import PREFIX

    client = _client()
    sites = {s["name_en"]: s for s in client.get(f"{PREFIX}/dive-sites").json()}
    for name in ("Cedar Pride Shipwreck", "Rainbow reef", "Gorgon 1",
                 "Japanese Gardens Coral Reefs", "King abdullah reef"):
        assert name in sites, f"{name} missing from the response"
        s = sites[name]
        assert s["distance_m"] < 1500, f"{name}: {s['distance_m']} m — expected close to a reef"
        assert s["caveats"] == [], f"{name} was flagged: {s['caveats']}"


def test_desert_pois_in_the_dive_category_are_honestly_flagged():
    """The actual data-quality finding: Wadi Rum attractions tagged `kind: dive`
    are tens of km inland. The join must not pretend these are coastal dive
    sites — a caveat, not a silent drop and not a silent pass-through."""
    from api.main import PREFIX

    client = _client()
    sites = {s["name_en"]: s for s in client.get(f"{PREFIX}/dive-sites").json()}
    for name in ("Wadi Rum", "Barrah Canyon", "Siq al Khazali"):
        assert name in sites, f"{name} missing from the response"
        s = sites[name]
        assert s["distance_m"] > 20_000, f"{name}: {s['distance_m']} m — expected tens of km"
        assert s["caveats"], f"{name} ({s['distance_m']:.0f} m) should carry a distance caveat"
        assert s["caveats"][0]["severity"] == "warning"


def test_flag_threshold_separates_the_two_real_clusters():
    """Not a fitted number — a round threshold sitting inside the actual 32x gap
    between the closest desert POI (~32,500 m) and the farthest real dive site
    (997 m) found in the data. This pins that the gap stays a gap; if a future
    OSM re-extract adds a genuine dive site between 1 and 2 km from a reef, this
    test failing is the right signal to revisit the threshold, not silently
    misclassify it."""
    from api.main import PREFIX

    client = _client()
    sites = client.get(f"{PREFIX}/dive-sites").json()
    distances = sorted(s["distance_m"] for s in sites)
    unflagged = [d for d in distances if d <= 2000]
    flagged = [d for d in distances if d > 2000]
    assert unflagged and flagged
    assert max(unflagged) < 1500
    assert min(flagged) > 30_000


def test_dive_sites_response_matches_the_declared_schema_shape():
    from api.main import PREFIX

    client = _client()
    sites = client.get(f"{PREFIX}/dive-sites").json()
    assert sites
    for s in sites[:5]:
        assert set(s) == {"osm_id", "name_en", "name_ar", "lon", "lat",
                          "nearest_reef_zone_id", "distance_m", "caveats"}
