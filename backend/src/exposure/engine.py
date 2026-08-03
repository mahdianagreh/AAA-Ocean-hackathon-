"""Component D — the exposure engine.

Turns a plume forecast into habitat-specific risk per reef zone.

    Exposure = plume_probability
             x relative_sediment_intensity
             x exposure_duration_weight
             x habitat_sensitivity_weight     (= 1.0, placeholder)
             x confidence_adjustment

TWO RULES THAT ARE NOT STYLE PREFERENCES
----------------------------------------
1. EVERY area and distance is computed in EPSG:32636. This workstream has already
   shipped one bug of exactly this class — culvert distances measured in EPSG:3857
   came out 14.8% too large, because Web Mercator inflates ground distance by
   1/cos(lat). Reprojection happens at the top of `intersect_plume_with_zones`
   before any `.area` is touched, and `_assert_measure_crs` refuses anything else.

2. EVERY score carries its `formula_terms`. A score you cannot reconstruct six
   hours later is a number nobody can defend. When someone asks why R-04 is at 81,
   the answer must be a lookup, not a re-derivation from memory.

WHY `zone_fraction_affected` AND NOT `area_affected_km2`
-------------------------------------------------------
Reef zone widths are a flat 250 m assumption, deliberately not derived from depth
contours because the bathymetry's true resolution (~450 m) cannot resolve the
Gulf's drop-off. So `area_km2` is order-of-magnitude. A fraction of a named zone
inherits that honestly; an absolute km² figure launders it into false precision.
"""

from __future__ import annotations

import math

import geopandas as gpd

CRS_MEASURE = "EPSG:32636"  # UTM 36N

# Concept §14.5. Bands are inclusive of both ends; contiguous integer coverage.
RISK_BANDS: list[tuple[float, float, str]] = [
    (0, 20, "minimal"),
    (20, 40, "low"),
    (40, 60, "moderate"),
    (60, 80, "high"),
    (80, 100, "critical"),
]

# The placeholder. ACA maps habitat, not sensitivity. Not a tunable.
HABITAT_SENSITIVITY_PLACEHOLDER = 1.0

# risk_score = raw * SCORE_SCALE. Documented rather than arbitrary: every factor
# in the product is already dimensionless on [0, 1], so the product is on [0, 1]
# and x100 maps it onto the 0-100 band table without any further reshaping. No
# exponent or logistic is applied, because any curve we invented here would change
# the ranking between zones while looking like a presentation detail.
SCORE_SCALE = 100.0


def risk_level(score: float) -> str:
    """Band a 0-100 score.

    Operational thresholds require marine-scientist input. These bands are a
    reasonable default, not validated policy — say so wherever they are displayed.
    """
    if not (0 <= score <= 100) or math.isnan(score):
        raise ValueError(f"risk score {score!r} is outside 0-100")
    for lo, hi, label in RISK_BANDS:
        if lo <= score <= hi:
            return label
    raise ValueError(f"score {score} matched no band")  # pragma: no cover


def calculate_exposure(
    plume_probability: float,
    relative_sediment_intensity: float,
    exposure_duration_weight: float,
    habitat_sensitivity_weight: float = HABITAT_SENSITIVITY_PLACEHOLDER,
    confidence_adjustment: float = 1.0,
) -> tuple[float, dict]:
    """Return (risk_score, formula_terms).

    Inputs are validated rather than clamped. Silently clamping an out-of-range
    probability would hide an upstream bug behind a plausible-looking score.
    """
    terms = {
        "plume_probability": plume_probability,
        "relative_sediment_intensity": relative_sediment_intensity,
        "exposure_duration_weight": exposure_duration_weight,
        "habitat_sensitivity_weight": habitat_sensitivity_weight,
        "confidence_adjustment": confidence_adjustment,
    }
    for name, value in terms.items():
        if value is None or math.isnan(value):
            raise ValueError(f"{name} is missing — a gap is a gap, not a zero")
        if not (0.0 <= value <= 1.0) and name != "habitat_sensitivity_weight":
            raise ValueError(f"{name}={value} outside [0, 1]")
    if habitat_sensitivity_weight < 0:
        raise ValueError("habitat_sensitivity_weight must be non-negative")

    raw = (
        plume_probability
        * relative_sediment_intensity
        * exposure_duration_weight
        * habitat_sensitivity_weight
        * confidence_adjustment
    )
    score = min(100.0, raw * SCORE_SCALE)

    terms.update({
        "raw_score": raw,
        "score_scale": SCORE_SCALE,
        "risk_score": score,
        "risk_level": risk_level(score),
        "habitat_sensitivity_weight_status": (
            "PLACEHOLDER_PENDING_MARINE_SCIENTIST"
            if habitat_sensitivity_weight == HABITAT_SENSITIVITY_PLACEHOLDER
            else "SCIENTIST_ASSIGNED"
        ),
    })
    return score, terms


def _assert_measure_crs(gdf: gpd.GeoDataFrame, what: str) -> None:
    if gdf.crs is None:
        raise ValueError(f"{what} has no CRS — refusing to measure an unknown frame")
    epsg = gdf.crs.to_epsg()
    if epsg != 32636:
        raise ValueError(
            f"{what} is EPSG:{epsg}, must be 32636 before any area or distance. "
            "Measuring in 4326 gives degrees; measuring in 3857 overstates ground "
            "distance by 1/cos(lat) — 14.8% at this latitude."
        )


def intersect_plume_with_zones(
    plume_contours: gpd.GeoDataFrame,
    reef_zones: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """Overlay time-stepped probability contours on reef zones, in UTM 36N.

    `plume_contours` needs `probability` and (for arrival windows) `t_hours`.
    `reef_zones` needs `reef_zone_id`.

    Zone area is recomputed here from the projected geometry rather than trusted
    from an `area_km2` column: a stale column and a live geometry disagreeing is
    exactly the silent divergence the standing cross-check rule targets.
    """
    if plume_contours.empty or reef_zones.empty:
        return gpd.GeoDataFrame(
            columns=["reef_zone_id", "t_hours", "probability",
                     "intersection_area_km2", "zone_area_km2", "zone_fraction_affected"],
            geometry=[], crs=CRS_MEASURE,
        )

    plume_utm = plume_contours.to_crs(CRS_MEASURE)
    zones_utm = reef_zones.to_crs(CRS_MEASURE)
    _assert_measure_crs(plume_utm, "plume_contours")
    _assert_measure_crs(zones_utm, "reef_zones")

    zones_utm = zones_utm.copy()
    zones_utm["zone_area_km2"] = zones_utm.geometry.area / 1e6

    keep_zone = [c for c in ("reef_zone_id", "zone_name", "sensitivity_weight",
                             "zone_area_km2", "geometry") if c in zones_utm.columns]
    keep_plume = [c for c in ("t_hours", "probability", "geometry")
                  if c in plume_utm.columns]

    out = gpd.overlay(zones_utm[keep_zone], plume_utm[keep_plume], how="intersection")
    if out.empty:
        out["intersection_area_km2"] = []
        out["zone_fraction_affected"] = []
        return out

    out["intersection_area_km2"] = out.geometry.area / 1e6
    out["zone_fraction_affected"] = (
        out["intersection_area_km2"] / out["zone_area_km2"]
    ).clip(upper=1.0)
    return out


def summarise_zone(
    zone_id: str,
    overlay: gpd.GeoDataFrame,
    relative_sediment_intensity: float,
    confidence_adjustment: float,
    horizon_hours: float,
    sensitivity_weight: float = HABITAT_SENSITIVITY_PLACEHOLDER,
) -> dict | None:
    """Collapse one zone's overlay rows into a single scored result.

    Returns None when the plume never reaches the zone — a zone that was not hit
    is reported as not hit, never as a zero-risk hit. Standing law #1.
    """
    rows = overlay[overlay["reef_zone_id"] == zone_id]
    if rows.empty:
        return None

    hit = rows[rows["probability"] > 0]
    if hit.empty:
        return None

    max_prob = float(hit["probability"].max())
    frac = float(hit["zone_fraction_affected"].max())

    # Duration weight: how much of the forecast horizon this zone is under a
    # non-zero plume, from the discrete contour timestamps actually present.
    if "t_hours" in hit.columns and hit["t_hours"].notna().any():
        times = sorted(hit["t_hours"].dropna().unique())
        arrival = (float(min(times)), float(max(times)))
        span = max(times) - min(times)
        # One timestamp means one snapshot, not zero duration. Weight it by a
        # single step rather than collapsing the score to zero.
        if span <= 0:
            all_times = sorted(overlay["t_hours"].dropna().unique())
            step = (all_times[1] - all_times[0]) if len(all_times) > 1 else 1.0
            span = step
        duration_weight = min(1.0, span / horizon_hours) if horizon_hours > 0 else 0.0
    else:
        arrival = None
        duration_weight = 1.0

    score, terms = calculate_exposure(
        plume_probability=max_prob,
        relative_sediment_intensity=relative_sediment_intensity,
        exposure_duration_weight=duration_weight,
        habitat_sensitivity_weight=sensitivity_weight,
        confidence_adjustment=confidence_adjustment,
    )

    # Audit context beyond the five factors: enough to reconstruct the inputs, not
    # just replay the arithmetic.
    terms.update({
        "zone_fraction_affected": frac,
        "max_exposure_probability": max_prob,
        "arrival_window_hours": list(arrival) if arrival else None,
        "horizon_hours": horizon_hours,
        "n_overlay_rows": int(len(rows)),
        "contour_times_hit": [float(t) for t in sorted(hit["t_hours"].dropna().unique())]
        if "t_hours" in hit.columns else [],
        "measure_crs": CRS_MEASURE,
    })

    return {
        "reef_zone_id": zone_id,
        "risk_score": score,
        "risk_level": risk_level(score),
        "arrival_window_hours": arrival,
        "max_exposure_probability": max_prob,
        "zone_fraction_affected": frac,
        "formula_terms": terms,
    }


def confidence_label(confidence_adjustment: float) -> str:
    """Map the numeric adjustment onto the three reported levels."""
    if confidence_adjustment >= 0.8:
        return "high"
    if confidence_adjustment >= 0.5:
        return "moderate"
    return "low"
