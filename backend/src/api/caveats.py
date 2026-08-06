"""Caveats as data, not documentation.

A limitation that lives only in a markdown file is not on screen when someone is
looking at a number and asking how sure we are about it. Everything here is
attached to a response field so the UI can render it beside the value it qualifies.

Each builder is a pure function of the thing being described, so
`tests/test_caveat_coverage.py` can enumerate which conditions fire which caveats
and prove none of them is unreachable — a caveat that exists in code but never
reaches a payload is the same as not having it.
"""

from __future__ import annotations

from .schemas import Caveat

DOC = "docs/pitch_limitations.md"
DD = "docs/data_dictionary.md"

# AQ-O04 is the one outlet whose results must never be shown as representative.
HARBOUR_OUTLETS = {"AQ-O04"}


def harbour_outlet(outlet_id: str) -> list[Caveat]:
    if outlet_id not in HARBOUR_OUTLETS:
        return []
    return [Caveat(
        field="outlet_id",
        message=(
            f"{outlet_id} discharges into an enclosed harbour basin. Sediment released "
            "here settles inside the basin rather than dispersing into the Gulf, so "
            "simulation results from this outlet must not be presented as "
            "representative Gulf exposure."
        ),
        severity="critical",
        source=DOC,
    )]


def sensitivity_placeholder(status: str) -> list[Caveat]:
    if status != "PLACEHOLDER_PENDING_MARINE_SCIENTIST":
        return []
    return [Caveat(
        field="sensitivity_weight",
        message=(
            "This zone's sensitivity weight is a team placeholder (1.0), not a "
            "scientific assessment. Allen Coral Atlas maps habitat, not sensitivity; "
            "real weights require marine-scientist input."
        ),
        severity="warning",
        source=f"{DOC} §5",
    )]


def reef_zone_width() -> list[Caveat]:
    return [Caveat(
        field="area_km2",
        message=(
            "Reef zone width is a flat 250 m assumption, deliberately not derived from "
            "depth contours because the bathymetry's true resolution (~450 m) cannot "
            "resolve the Gulf's drop-off. Treat area as order-of-magnitude and prefer "
            "zone_fraction_affected over any absolute km²."
        ),
        severity="info",
        source=f"{DD} §4",
    )]


def catchment_area_uncertainty() -> list[Caveat]:
    """±4% and the endorheic exclusion.

    Cited to the data dictionary, which is where the figure and its range actually
    live. It is deliberately not cited to 00-contracts.md §2: that file lists the
    areas but not the uncertainty, and a caveat pointing at a file that does not
    contain the claim is worse than no citation at all.
    """
    return [Caveat(
        field="area_km2",
        message=(
            "Wadi Yutum's contributing area is 4,453 km² ±4% (range 4,349–4,690). "
            "Three independent approaches agree: explicit endorheic masking 4,349, "
            "fill=False proxy 4,453, HydroBASINS exorheic 4,690. Roughly 1,800–2,000 "
            "km² of the topographic basin drains to internal sinks and never reaches "
            "the Gulf — that area is excluded on purpose, not missing."
        ),
        severity="info",
        source=f"{DD} — catchment geometry section",
    )]


def reef_area_correction() -> list[Caveat]:
    """Reef area shrank 4.6x when the Atlas replaced the hand-drawn boxes.

    Verified against data/processed/vectors/reef_zones.gpkg on 2026-08-03:
    5.69 km2 of 250 m strips -> 1.235 km2 of ACA 5 m outline. Per-zone ranking
    changed too, not only the totals, so any exposure figure computed against the
    provisional areas is wrong rather than merely imprecise.

    Note what this caveat no longer says. The 250 m width assumption is GONE — the
    outline is the Atlas's own 5 m polygons, so an absolute km2 is now defensible.
    A fraction of a named zone is still the better framing, but for a different
    reason, which reef_shallow_only() carries.
    """
    return [Caveat(
        field="area_km2",
        message=(
            "Reef area comes from Allen Coral Atlas v2.0 at 5 m: 1.235 km² across the 8 "
            "named zones. The earlier provisional geometry claimed 5.69 km² — 4.6x more — "
            "because it assumed a uniform 250 m strip along the whole coastline. Any "
            "number derived from the provisional area is an overestimate, and the per-zone "
            "ranking changed as well as the totals."
        ),
        severity="warning",
        source=f"{DD} §4",
    )]


def reef_shallow_only() -> list[Caveat]:
    """Why a fraction still beats an absolute area, now that the width is real."""
    return [Caveat(
        field="zone_fraction_affected",
        message=(
            "Allen Coral Atlas maps optically shallow reef only, so deeper habitat inside "
            "a zone is unrepresented. An absolute 'km² affected' therefore understates the "
            "habitat actually at risk; a fraction of a named zone is the safer framing."
        ),
        severity="info",
        source=f"{DD} §4",
    )]


def reef_scope_is_jordan() -> list[Caveat]:
    """What the risk map covers, stated so nobody over-reads it."""
    return [Caveat(
        field="reef_zone_id",
        message=(
            "Scope is Jordan's coast. The Atlas export covers the full padded box, and "
            "6.09 km² of the 7.32 km² it maps lies in Egyptian, Saudi and Israeli water — "
            "deliberately discarded, all of it more than 5 km from the Jordanian zone "
            "chain. Risk shown here is risk to the named Jordanian zones, not to all reef "
            "in the Gulf of Aqaba."
        ),
        severity="info",
        source=f"{DD} §4",
    )]


def depth_is_land_dominated(zone_id: str, land_pct, depth_median) -> list[Caveat]:
    """Depth is now the weakest field in the reef table, not the geometry.

    The bathymetry is 50 m while the reef strip is 20-50 m wide, so 39-100% of the
    cells under a zone read as land. Karam's handoff is explicit: check
    depth_land_cell_pct before any depth reaches a formula or a screen. R-02 has no
    water cell at all and is NaN — not 0, and not the +10 m the raw cells would give.
    """
    out: list[Caveat] = []
    if depth_median is None:
        out.append(Caveat(
            field="depth_median_m",
            message=(
                f"{zone_id} has no water cell in the 50 m bathymetry at all, so depth is "
                "unavailable. Reported as null, never as 0 — a gap is a gap."
            ),
            severity="warning",
            source=f"{DD} §4",
        ))
    elif land_pct is not None and land_pct >= 50:
        out.append(Caveat(
            field="depth_median_m",
            message=(
                f"{land_pct:.0f}% of the bathymetry cells under {zone_id} read as land, "
                "because the grid is 50 m and the reef strip is 20-50 m wide. The median "
                "is taken over water cells only and rests on few of them; treat it as "
                "indicative, not measured."
            ),
            severity="warning",
            source=f"{DD} §4",
        ))
    return out


def provisional_reef_zones() -> list[Caveat]:
    return [Caveat(
        field="reef_zone_id",
        message=(
            "Reef zone geometry is still the provisional set. Along-shore position is "
            "derived from the water mask and is reliable to about 50 m; the seaward "
            "edge is the 250 m assumption. The Allen Coral Atlas swap is pending Earth "
            "Engine authentication, and zone IDs will not change when it lands."
        ),
        severity="warning",
        source=f"{DD} §4",
    )]


def stub_model(component: str) -> list[Caveat]:
    return [Caveat(
        field="is_stub",
        message=(
            f"{component} is a stub returning shaped placeholder values so the "
            "interface can be built against it. These numbers are not predictions and "
            "must not reach the RAG corpus, a slide, or an alert."
        ),
        severity="critical",
        source="tasks/phase2/04-pulga.md §1",
    )]


def particle_engine_forcing(current_source: str, *, forcing_is_placeholder: bool,
                             calibrated: bool) -> list[Caveat]:
    """The real particle engine's own limitations -- distinct from `stub_model()`,
    which is for the synthetic-circle placeholder this replaced. Real transport
    physics (advection, diffusion, coastline reflection, settling) still runs on
    forcing that is not fully real, so the caveat travels with the run rather
    than only with the fact that it is not a stub.
    """
    caveats = [Caveat(
        field="is_stub",
        message=(
            "Real particle transport (advection, diffusion, coastline reflection, "
            "depth-dependent settling), not the synthetic sqrt(t) circles -- but "
            f"still bounded by its forcing. Currents: {current_source}. Wind: "
            "ConstantWindField(0, 0) -- no historical marine wind source exists in "
            "this repo (GFS/GEFS/ECMWF here are forecast-only, not a 2016 archive)."
        ),
        severity="warning" if forcing_is_placeholder else "info",
        source="backend/src/models/particle_engine.py",
    ), Caveat(
        field="contours",
        message=(
            "Contour levels are peak-normalized kernel-density thresholds of the "
            "simulated particle cloud (relative density), not a calibrated arrival "
            "probability. The best free ocean current model resolves ~9 km cells "
            "across a gulf 15-25 km wide -- two or three cells span the whole basin."
        ),
        severity="warning",
        source="backend/src/models/particle_engine.py:kernel_density_contours",
    )]
    if not calibrated:
        caveats.append(Caveat(
            field="model_version",
            message=(
                "Uncalibrated: diffusion/windage/settling are the particle engine's "
                "documented defaults, not fitted against the Kalman et al. (2025) "
                "mooring. Only AQ-2016-10-28 (via scripts/28_calibrate_plume_engine.py) "
                "has a calibrated parameter set."
            ),
            severity="info",
            source="scripts/28_calibrate_plume_engine.py",
        ))
    return caveats


def bathymetry_substitution() -> list[Caveat]:
    return [Caveat(
        field="geometry",
        message=(
            "Bathymetry is GMRT, substituted for GEBCO because every programmatic GEBCO "
            "route is closed. Cross-checked against NOAA NCEI (0.2 m on the basin "
            "minimum) and against OSM's independent coastline (62 m median). Effective "
            "resolution is ~450 m regardless of the 50 m grid spacing."
        ),
        severity="info",
        source=f"{DD} §5",
    )]


def risk_band_thresholds() -> list[Caveat]:
    return [Caveat(
        field="risk_level",
        message=(
            "Risk bands (0–20 minimal … 80–100 critical) are a reasonable default, not "
            "validated policy. Operational thresholds require marine-scientist input."
        ),
        severity="warning",
        source="concept §14.5",
    )]


def landcover_epoch() -> list[Caveat]:
    return [Caveat(
        field="landcover",
        message=(
            "Land cover is the ESA WorldCover 2021 epoch with no time series, so the "
            "2013 and 2016 events are both modelled against 2021 conditions. Aqaba "
            "developed across that decade, in the direction that increases runoff."
        ),
        severity="info",
        source=f"{DD} §1",
    )]


def soil_is_modelled() -> list[Caveat]:
    return [Caveat(
        field="soil",
        message=(
            "Soil properties come from SoilGrids, a global model, not from local "
            "sampling. Use them as a relative erodibility ranking between catchments; "
            "no value here is a measured local soil property."
        ),
        severity="warning",
        source=f"{DOC} §2",
    )]


def build_exposure_caveats(outlet_id: str, zone=None, *, provisional: bool) -> list[Caveat]:
    """Every caveat that applies to one exposure result.

    `zone` may be a ReefZoneOut, a plain dict, or None — the routes read zones from
    a GeoPackage in one place and from a Pydantic model in another, and this is not
    worth forcing into one type at the call sites.

    `provisional` is KEYWORD-ONLY AND HAS NO DEFAULT, deliberately. This function
    used to emit reef_zone_width() unconditionally, so after the Allen Coral Atlas
    swap /exposure/calculate kept asserting "reef zone width is a flat 250 m
    assumption" about geometry that is now the Atlas's own 5 m outline —
    a false statement about a 5 m product, shipped as a caveat, which is the one
    kind of text a reader is entitled to trust. /reef-zones had been fixed and this
    path had not. A default would have let the same omission recur silently at the
    next call site; requiring the argument makes the caller state which geometry
    they are describing.
    """
    if zone is None:
        status = "PLACEHOLDER_PENDING_MARINE_SCIENTIST"
    elif isinstance(zone, dict):
        status = zone.get("sensitivity_weight_status", "")
    else:
        status = getattr(zone, "sensitivity_weight_status", "")

    # The width assumption belongs to the hand-placed geometry only. With real ACA
    # outlines the honest reason to prefer a fraction over an absolute km2 is that
    # the Atlas maps optically shallow reef only — which is what reef_shallow_only
    # says, and it is not interchangeable with the width caveat.
    geometry_caveats = reef_zone_width() if provisional else reef_shallow_only()

    return [
        *harbour_outlet(outlet_id),
        *sensitivity_placeholder(status),
        *geometry_caveats,
        *risk_band_thresholds(),
    ]
