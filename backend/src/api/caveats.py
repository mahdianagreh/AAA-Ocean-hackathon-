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
    """The real reef is far smaller than the provisional strips implied.

    Measured 3 Aug 2026 against the Allen Coral Atlas export:

        living reef in MARINE_AOI          4.192 km²
          on Jordan's coastal corridor     0.855 km²
          in Egyptian / Israeli waters     3.338 km²  (80% of the AOI total)
        scored across the 8 named zones    0.742 km²  (86.8% of Jordan's corridor)
        provisional strips claimed         5.69  km²  (7.7x the real figure)

    An earlier draft of this caveat said the zones covered "only 40%" of the reef.
    That was wrong and alarmist: it measured against every reef in the marine box,
    four fifths of which is in another country's water and was never in scope. The
    honest statement is that coverage of Jordan's reef is good, and that the
    provisional AREA was a large overestimate.
    """
    return [Caveat(
        field="area_km2",
        message=(
            "Reef area comes from Allen Coral Atlas v2.0 at 5 m: 0.742 km² across the "
            "8 named zones, which is 86.8% of the living reef the Atlas maps on "
            "Jordan's coast. The earlier provisional geometry claimed 5.69 km² — about "
            "7.7x more — because it assumed a uniform 250 m-wide strip along the whole "
            "coastline. Any figure derived from the provisional area is an "
            "overestimate."
        ),
        severity="warning",
        source=f"{DD} §4",
    )]


def reef_scope_is_jordan() -> list[Caveat]:
    """What the risk map covers, stated so nobody over-reads it."""
    return [Caveat(
        field="reef_zone_id",
        message=(
            "Scope is Jordan's coast. The Atlas maps a further 3.338 km² of living reef "
            "inside the same marine bounding box, on the Egyptian and Israeli shores; "
            "those reefs are not zoned and not scored. Risk shown here is risk to the "
            "named Jordanian zones, not to all reef in the Gulf of Aqaba."
        ),
        severity="info",
        source=f"{DD} §4",
    )]


def reef_depth_disagreement() -> list[Caveat]:
    """Two of our own artefacts disagree, and the disagreement is the signal.

    ACA maps reef at 5 m where our 450 m-effective bathymetry says land: R-02 and
    R-08 come out with a positive median elevation. ACA is purpose-built for shallow
    reef at 5 m, so it wins — but the disagreement is worth surfacing rather than
    resolving silently in favour of whichever file was read last.
    """
    return [Caveat(
        field="depth_median_m",
        message=(
            "Depth is sampled from a bathymetry grid with ~450 m effective resolution, "
            "while reef extent comes from Allen Coral Atlas at 5 m. Where the two "
            "disagree — two zones report a positive median elevation, i.e. 'land' — "
            "trust the Atlas for reef presence and treat the depth as indicative only."
        ),
        severity="warning",
        source=f"{DD} §5",
    )]


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


def build_exposure_caveats(outlet_id: str, zone=None) -> list[Caveat]:
    """Every caveat that applies to one exposure result.

    `zone` may be a ReefZoneOut, a plain dict, or None — the routes read zones from
    a GeoPackage in one place and from a Pydantic model in another, and this is not
    worth forcing into one type at the call sites.
    """
    if zone is None:
        status = "PLACEHOLDER_PENDING_MARINE_SCIENTIST"
    elif isinstance(zone, dict):
        status = zone.get("sensitivity_weight_status", "")
    else:
        status = getattr(zone, "sensitivity_weight_status", "")

    return [
        *harbour_outlet(outlet_id),
        *sensitivity_placeholder(status),
        *reef_zone_width(),
        *risk_band_thresholds(),
    ]
