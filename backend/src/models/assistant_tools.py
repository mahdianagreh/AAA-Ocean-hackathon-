"""Read-only tool catalog + pure data-shaping for the AI Assistant's tool-calling
loop (`models/assistant_agent.py`).

No `api.data_access`/`exposure.store`/`rag.index` import here — this project's
`models/` package never imports from `api/` (see `severity_brief.py`,
`report_assembly.py`, `site_scoring.py`: "`main.py` fetches, this module only
shapes"). The wrinkle versus those modules is that which fetch runs is chosen by
the model mid-conversation, not known in advance — `main.py`'s `_assistant_dispatch`
closure is the one place that actually calls a `da.*`/`store.*`/`rag_index.retrieve`
function, keyed by the tool name the model picked; everything below is a pure
function of already-fetched data.

READ-ONLY, ON PURPOSE. Nothing here wraps a POST/PATCH endpoint (trigger a swarm,
generate a report, approve a sensitivity weight, submit feedback, upload a photo).
The model can look things up; it never takes an action on the user's behalf.
"""

from __future__ import annotations

RISK_ORDER = ["minimal", "low", "moderate", "high", "critical"]

TOOL_CATALOG: dict[str, dict] = {
    "get_alerts": {
        "description": (
            "Current alerts derived from the latest stored exposure run, one per "
            "reef zone that reached at least the given risk level."
        ),
        "params": {"min_level": f"one of {RISK_ORDER}, default 'minimal'"},
    },
    "get_reef_zone": {
        "description": (
            "Detail for one named reef zone: habitat, area, sensitivity weight, "
            "marine park overlap, depth."
        ),
        "params": {"zone_id": "e.g. 'R-03'"},
    },
    "get_event": {
        "description": "A documented flood event's date and label.",
        "params": {"event_id": "e.g. 'AQ-2016-10-28'"},
    },
    "get_exposure_run": {
        "description": (
            "A specific stored exposure run by id: per-zone risk scores, arrival "
            "windows, formula terms."
        ),
        "params": {"run_id": "e.g. 'sim_...'"},
    },
    "get_data_sources": {
        "description": (
            "The provenance ledger: every input dataset, its version, access "
            "date, licence and known limitations."
        ),
        "params": {},
    },
    "search_docs": {
        "description": (
            "Lexical search over this project's technical documentation corpus. "
            "Use for method/limitation/definition questions, not for live data."
        ),
        "params": {"query": "the search text", "k": "max results, default 5"},
    },
}


def tool_catalog_prompt() -> str:
    """Renders TOOL_CATALOG as prompt text — one line per tool."""
    lines = []
    for name, spec in TOOL_CATALOG.items():
        params = ", ".join(f"{k} ({v})" for k, v in spec["params"].items()) or "no arguments"
        lines.append(f"- {name}({params}): {spec['description']}")
    return "\n".join(lines)


# ---------------------------------------------------------------- route guidance
#
# Hand-maintained, mirroring `DashboardChrome.tsx`'s own NAV table and
# `useRoute.ts`'s own ROUTES table on the frontend — there is no single source of
# truth to import across the language boundary, so re-derive this from those two
# files if either changes. Only destinations worth suggesting mid-conversation:
# excludes marketing/auth/account/specimen pages and the assistant itself.
ROUTE_WHITELIST: dict[str, dict[str, str]] = {
    "/dashboard": {"en": "Overview", "ar": "نظرة عامة"},
    "/events": {"en": "Events", "ar": "الأحداث"},
    "/dashboard/replay": {"en": "Storm Replay", "ar": "إعادة العاصفة"},
    "/reef-zones": {"en": "Reef Zones", "ar": "مناطق الشعاب"},
    "/alerts": {"en": "Alerts", "ar": "التنبيهات"},
    "/dashboard/recommendations": {"en": "Response Swarm", "ar": "مجموعة الاستجابة"},
    "/reports": {"en": "Reports", "ar": "التقارير"},
    "/dashboard/validation": {"en": "Validation", "ar": "التحقق"},
    "/dashboard/provenance": {"en": "Provenance", "ar": "مصادر البيانات"},
    "/sites/score": {"en": "Site Scoring", "ar": "تقييم المواقع"},
    "/limitations": {"en": "Honest Limits", "ar": "حدود صادقة"},
    "/backtests": {"en": "Backtests", "ar": "الاختبارات الخلفية"},
    "/system-health": {"en": "System Health", "ar": "حالة النظام"},
    "/data-explorer": {"en": "Data Explorer", "ar": "مستكشف البيانات"},
}


def route_whitelist_prompt() -> str:
    lines = [f"- {path} — {labels['en']}" for path, labels in ROUTE_WHITELIST.items()]
    lines.append(
        "- /reef-zones/{zone_id} — a specific reef zone's page, only if "
        "zone_id is a real id you already saw from get_reef_zone or get_alerts"
    )
    return "\n".join(lines)


# ------------------------------------------------------------------- shaping

def shape_alerts(results: list[dict], zone_meta: dict[str, dict], min_level: str) -> dict:
    floor = RISK_ORDER.index(min_level) if min_level in RISK_ORDER else 0
    out = []
    for r in results:
        if RISK_ORDER.index(r["risk_level"]) < floor:
            continue
        zid = r["reef_zone_id"]
        zone_name = (zone_meta.get(zid) or {}).get("zone_name") or zid
        out.append({
            "reef_zone_id": zid,
            "zone_name": zone_name,
            "risk_level": r["risk_level"],
            "risk_score": r["risk_score"],
            "arrival_window_hours": r.get("arrival_window_hours"),
        })
    out.sort(key=lambda a: a["risk_score"], reverse=True)
    return {"alerts": out}


def shape_reef_zone(zones: list[dict], zone_id: str) -> dict | None:
    for z in zones:
        if z["reef_zone_id"] == zone_id:
            return z
    return None


def shape_event(events: list[dict], event_id: str) -> dict | None:
    for e in events:
        if e["event_id"] == event_id:
            return e
    return None


def shape_exposure_run(run: dict | None) -> dict | None:
    return run


def shape_data_sources(sources: list[dict]) -> list[dict]:
    # qa_figures is filenames for a human QA reviewer, not conversational content.
    return [{k: v for k, v in s.items() if k != "qa_figures"} for s in sources]


def shape_search_docs(chunks: list[dict]) -> dict:
    return {"chunks": chunks}
