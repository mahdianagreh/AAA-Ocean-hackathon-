"""Phase 9 role 0 — the Severity Briefer. Templated, not generative: converts a
stored exposure run's own numbers into the one structured brief every specialist,
the judge, and the gaps agent read. Deliberately no LLM call in this module — per
`tasks/phase9/00-phase9-plan.md` §5, this is "the one place a hallucinated number
poisons everything downstream."

Same division of labour as `report_assembly.py`: takes already-fetched data as
plain arguments rather than importing `exposure.store`/`api.data_access` itself.
`main.py` fetches, this module only assembles.
"""

from __future__ import annotations

# Mirrors exposure/engine.py's RISK_BANDS ordering — kept as a literal list here
# rather than importing exposure.engine, matching this module's "plain arguments
# only" convention; the ordering itself is not a tunable, it is the band table.
RISK_ORDER = ["minimal", "low", "moderate", "high", "critical"]

DEMO_EVENT_ID = "AQ-2016-10-28"


def _max_risk_level(results: list[dict]) -> str | None:
    if not results:
        return None
    return max(results, key=lambda r: RISK_ORDER.index(r["risk_level"]))["risk_level"]


def build_severity_brief(
    run: dict,
    zones_meta: dict[str, dict],
    outlets_meta: dict[str, dict],
    mooring: dict | None = None,
) -> dict:
    """`run` is `exposure.store.get_run()`'s return shape. `zones_meta`/`outlets_meta`
    are keyed by id, from `data_access.reef_zones()`/`data_access.outlets()`.
    `mooring` is `data_access.mooring_for(event_id)` or None — only
    `AQ-2016-10-28` has one; every other event gets no tonnage claim, not a
    guessed one (same rule `report_assembly.py` already applies).

    Returns a plain dict, JSON-serialisable, with every field traceable to a
    formula_terms key, a stored reef-zone/outlet field, or the mooring record —
    never a value this function computed itself.
    """
    results = run["results"]
    outlet = outlets_meta.get(run["outlet_id"], {})

    zones = []
    for r in sorted(results, key=lambda r: r["risk_score"], reverse=True):
        zid = r["reef_zone_id"]
        meta = zones_meta.get(zid, {})
        terms = r["formula_terms"]
        zones.append({
            "reef_zone_id": zid,
            "zone_name": meta.get("zone_name") or zid,
            "risk_level": r["risk_level"],
            "risk_score": r["risk_score"],
            "arrival_window_hours": r["arrival_window_hours"],
            "max_exposure_probability": r["max_exposure_probability"],
            "confidence": r["confidence"],
            "sediment_class": terms.get("sediment_class"),
            "relative_sediment_intensity": terms.get("relative_sediment_intensity"),
            "transmission_loss": terms.get("transmission_loss"),
            "marine_park_overlap_pct": meta.get("marine_park_overlap_pct"),
            "sensitivity_weight_status": meta.get("sensitivity_weight_status"),
        })

    sediment_mass_note = None
    if mooring is not None:
        mass = mooring.get("magnitude", {}).get("sediment_mass_total_t")
        if mass is not None:
            sediment_mass_note = {
                "sediment_mass_total_t": mass,
                "source": mooring.get("source_citation"),
            }
    elif run["event_id"] != DEMO_EVENT_ID:
        sediment_mass_note = {
            "sediment_mass_total_t": None,
            "note": f"No mooring record exists for {run['event_id']} — "
                    f"only {DEMO_EVENT_ID} has one. Tonnage is unrepresentable "
                    "for this event, not omitted.",
        }

    return {
        "run_id": run["run_id"],
        "event_id": run["event_id"],
        "outlet_id": run["outlet_id"],
        "outlet_caveat": outlet.get("source_caveat"),
        "created_at": run["created_at"],
        "max_risk_level": _max_risk_level(results),
        "zones": zones,
        "sediment_mass": sediment_mass_note,
    }
