"""B4 — Automated Site-Scoring Agent.

Scores a candidate bounding box against the six-criterion rubric
(`docs/Ali/research/01-signature.md`, C1-C6) — **not** by reading that file
(Standing Law rule 11: `docs/ali/*` stays out of the RAG corpus and the app
surface, unconditionally; this module never imports or quotes it), but by
computing real per-criterion evidence from this project's own real, processed
datasets — the same ones the rest of the backend already reads.

A pure computation module, same division of labour as `runoff_model.py`:
returns plain dicts, takes real geodata/dataframes as arguments rather than
importing `api.data_access` itself (this project's existing modules under
`models/` never import from `api/` — `main.py` reads the artifacts and passes
them in, matching how it already does that for the runoff model).

WHY NO LIVE EXTERNAL FETCH
--------------------------
An earlier sketch of this feature considered a live OSM Overpass query for a
bounding box outside Aqaba. Building it, that turned out to be the wrong call
for this codebase specifically: every other "live" data path in this project
either reads a cached/frozen snapshot (`forecast_snapshot`) or refuses
outright rather than reach the network mid-request. A live Overpass call at
request time would be the only external network dependency anywhere in this
backend's request path, would make this endpoint's tests non-deterministic,
and would fail exactly when a demo needs it least (conference wifi). So
instead: a bounding box outside where this project's own real datasets have
coverage gets an honest `"insufficient_data"` criterion — which is also,
simply, a true statement. Documented here as a deliberate deviation from the
original sketch, found while building it, not a shortcut taken silently.

THE ONE CRITERION THAT IS ALWAYS insufficient_data, EVEN FOR AQABA ITSELF
--------------------------------------------------------------------------
C6 ("data-poor and unmonitored") asks whether OTHER monitoring infrastructure
exists somewhere. No geospatial dataset can characterise the ABSENCE of a
gauge network or an operational model elsewhere — that is a desk-research
judgement call, and the one document that makes it for Aqaba is deliberately
excluded from the app surface (see above). So C6 is always reported honestly
as `insufficient_data`, never guessed at, regardless of location.
"""

from __future__ import annotations

from shapely.geometry import box as shapely_box

CRITERIA: tuple[str, ...] = ("C1", "C2", "C3", "C4", "C5", "C6")

CRITERION_LABELS: dict[str, str] = {
    "C1": "Ephemeral, not perennial, drainage",
    "C2": "Rare but high-intensity rainfall",
    "C3": "Reef or seagrass within a few kilometres",
    "C4": "Narrow shelf or restricted-flushing basin",
    "C5": "Development at the outlet",
    "C6": "Data-poor and unmonitored",
}

ONE_SITE_CAVEAT = (
    "This six-criterion rubric was built and tuned against exactly one site — "
    "Aqaba. A score for any other coordinate is the rubric's first real test, "
    "not a validated instrument."
)


def _clip(gdf, bbox: tuple[float, float, float, float]):
    """Real-geometry clip, never a silent empty-frame-as-zero. `None` in, `None`
    out; an empty clip is reported by the caller as `insufficient_data`, not
    coerced into a score of 0."""
    if gdf is None or gdf.empty:
        return None
    w, s, e, n = bbox
    clipped = gdf.clip(shapely_box(w, s, e, n))
    return clipped if not clipped.empty else None


def score_c1_ephemeral_drainage(bbox, drainage_gdf) -> dict:
    """Real fraction of drainage features tagged `intermittent=yes` inside the
    box — a directly measured proxy for ephemeral vs. perennial character, not
    an assertion carried over from the research doc."""
    clipped = _clip(drainage_gdf, bbox)
    if clipped is None or "intermittent" not in clipped.columns:
        return _insufficient("C1", "no OSM drainage-feature coverage for this box")
    total = len(clipped)
    intermittent = int((clipped["intermittent"] == "yes").sum())
    fraction = intermittent / total if total else 0.0
    score = 2.0 if fraction >= 0.5 else (1.0 if intermittent > 0 else 0.0)
    return _scored(
        "C1", score,
        source_file="data/processed/vectors/osm_aqaba.gpkg",
        section="drainage_features layer, real clip to the requested box",
        excerpt=f"{intermittent}/{total} drainage features in this box are tagged "
                f"intermittent=yes ({fraction:.0%})",
    )


def score_c2_rainfall_intensity(catchment_ids: list[str], climatology_df) -> dict:
    """Real concentration signature from `catchment_rainfall_climatology.parquet`
    for whichever catchments the box overlaps: `wet_day_fraction` (how rare
    rain is at all) combined with `p99_all_mm / p50_wet_mm` (how much heavier
    the extreme day is than a typical rain day) — a real proxy for "a year's
    water arriving in hours," not a fabricated intensity score. Deliberately
    `p50_wet_mm` (median of WET days only), not `p50_all_mm`: in a desert
    climate the latter is ~0 (Aqaba's own catchments: 2.3-2.9% wet-day
    fraction), so dividing by it explodes into a meaningless ratio rather than
    a real concentration signal."""
    if climatology_df is None or not catchment_ids:
        return _insufficient("C2", "no per-catchment rainfall climatology overlaps this box")
    rows = climatology_df[climatology_df["catchment_id"].isin(catchment_ids)]
    needed = {"p99_all_mm", "p50_wet_mm", "wet_day_fraction"}
    if rows.empty or not needed.issubset(rows.columns):
        return _insufficient("C2", "climatology exists but is missing p99_all_mm/"
                                    "p50_wet_mm/wet_day_fraction for these catchments")
    p99 = float(rows["p99_all_mm"].mean())
    p50_wet = float(rows["p50_wet_mm"].mean())
    wet_fraction = float(rows["wet_day_fraction"].mean())
    if p50_wet <= 0:
        return _insufficient("C2", "no wet days recorded for these catchments — "
                                    "cannot compute a concentration ratio")
    ratio = p99 / p50_wet
    # Rare (low wet_day_fraction) AND concentrated (high p99/p50_wet) is the
    # real signature the rubric's C2 asks for — Aqaba's own catchments are both
    # (≤3% wet days here) and this scores accordingly, not by assertion.
    is_rare = wet_fraction <= 0.05
    score = (2.0 if (is_rare and ratio >= 5) else
             1.0 if (is_rare or ratio >= 5) else 0.0)
    return _scored(
        "C2", score,
        source_file="data/processed/features/catchment_rainfall_climatology.parquet",
        section=f"catchments {sorted(catchment_ids)}",
        excerpt=f"wet on {wet_fraction:.1%} of days; the wettest 1% of days are "
                f"{ratio:.1f}x a typical wet day (p99={p99:.2f}mm, p50_wet={p50_wet:.2f}mm)",
    )


def score_c3_reef_proximity(bbox, reef_zones_gdf, local_utm_crs_fn) -> dict:
    """Real EPSG-projected distance from the box centroid to the nearest named
    reef zone — Standing Law rule 8 (never degrees), using the same
    `estimate_utm_crs()`-based helper `config.spatial.local_utm_crs` provides
    for exactly this "arbitrary location" case."""
    if reef_zones_gdf is None or reef_zones_gdf.empty:
        return _insufficient("C3", "no reef-zone geometry available for this box")
    w, s, e, n = bbox
    centroid_ll = shapely_box(w, s, e, n).centroid
    import geopandas as gpd

    pt = gpd.GeoSeries([centroid_ll], crs="EPSG:4326")
    utm = local_utm_crs_fn(reef_zones_gdf.to_crs("EPSG:4326"))
    zones_utm = reef_zones_gdf.to_crs(utm)
    pt_utm = pt.to_crs(utm).iloc[0]
    dist_m = float(zones_utm.geometry.distance(pt_utm).min())
    score = 2.0 if dist_m <= 2000 else (1.0 if dist_m <= 10000 else 0.0)
    return _scored(
        "C3", score,
        source_file="data/processed/vectors/reef_zones.gpkg",
        section="nearest reef zone, real projected distance",
        excerpt=f"{dist_m:.0f} m from the box centroid to the nearest named reef zone",
    )


def score_c4_basin_geometry(bathymetry_stats: dict | None) -> dict:
    """Real depth-range stats sampled from `depth_utm36n.tif` within the box —
    a narrow, consistently-shallow range is the measurable proxy for a
    restricted-flushing basin the rubric's C4 describes. `None` when the box
    doesn't overlap the bathymetry raster at all — never a guessed geometry."""
    if not bathymetry_stats or bathymetry_stats.get("n_cells", 0) == 0:
        return _insufficient("C4", "no bathymetry coverage for this box")
    depth_range = bathymetry_stats["max_depth_m"] - bathymetry_stats["min_depth_m"]
    score = 2.0 if depth_range <= 50 else (1.0 if depth_range <= 200 else 0.0)
    return _scored(
        "C4", score,
        source_file="data/processed/bathymetry/depth_utm36n.tif",
        section="real depth sample within the box",
        excerpt=f"depth range {depth_range:.0f} m across {bathymetry_stats['n_cells']} "
                "sampled cells (narrow range is the shallow-basin proxy)",
    )


def score_c5_development(bbox, buildings_gdf) -> dict:
    """Real building count within the box, from the OSM extract — a direct,
    measured development-density proxy, not a category guess."""
    clipped = _clip(buildings_gdf, bbox)
    if clipped is None:
        return _insufficient("C5", "no OSM building-footprint coverage for this box")
    count = len(clipped)
    score = 2.0 if count >= 200 else (1.0 if count > 0 else 0.0)
    return _scored(
        "C5", score,
        source_file="data/processed/vectors/osm_aqaba.gpkg",
        section="buildings layer, real clip to the requested box",
        excerpt=f"{count} real OSM building footprints inside this box",
    )


def score_c6_data_poor() -> dict:
    """Always insufficient_data, everywhere, including Aqaba itself — see this
    module's docstring. No geospatial dataset characterises the ABSENCE of
    monitoring infrastructure; that is a desk-research judgement, and the
    document that makes it for Aqaba is deliberately excluded from the app
    surface."""
    return _insufficient(
        "C6",
        "whether other monitoring/gauge infrastructure exists elsewhere is a "
        "desk-research judgement, not a computable geospatial fact — no "
        "automated evidence source exists for this criterion, for any location",
    )


def _scored(criterion: str, score: float, *, source_file: str, section: str, excerpt: str) -> dict:
    return {
        "criterion": criterion,
        "score": score,
        "status": "scored",
        "evidence": [{"source_file": source_file, "section": section,
                      "excerpt": excerpt, "score": None}],
    }


def _insufficient(criterion: str, reason: str) -> dict:
    return {
        "criterion": criterion,
        "score": None,
        "status": "insufficient_data",
        "evidence": [{"source_file": "docs/data_dictionary.md", "section": criterion,
                      "excerpt": reason, "score": None}],
    }


def narrate_criterion(result: dict) -> str:
    """Deterministic template, same shape as `rag/explain.py::build_explanation`
    — real computed facts wrapped in prose, nothing generated. No LLM call
    anywhere in this module: `rag/answer.py::generate_with_llm` is a permanent
    stub in this codebase, and this feature follows that same convention
    rather than being the first thing to break it."""
    label = CRITERION_LABELS.get(result["criterion"], result["criterion"])
    if result["status"] == "insufficient_data":
        reason = result["evidence"][0]["excerpt"] if result["evidence"] else "no evidence available"
        return f"{result['criterion']} ({label}): insufficient data — {reason}."
    parts = "; ".join(
        f"{e['excerpt']} ({e['source_file']})" for e in result["evidence"]
    )
    return f"{result['criterion']} ({label}): {result['score']:.1f}/2 — {parts}."


def narrate_site(results: list[dict]) -> str:
    return " ".join(narrate_criterion(r) for r in results)
