"""Pydantic contracts for the ReefShield API.

THIS FILE IS THE DELIVERABLE. The frontend is blocked without shapes, so the
schema matters more than the implementation behind it: a stub returning the right
shape unblocks the UI, a real implementation with the wrong shape does not.

Anything that changes here must be announced the same day. A schema that drifts
mid-sprint is worse for the consumer than one that is honestly incomplete but
stable.

THE CAVEAT RULE
---------------
Every response that carries a limitation ships it as structured data. Caveats
that live only in `docs/pitch_limitations.md` are not on screen when someone is
looking at a number and asking how sure we are about it. Shipping them in the
payload means the UI can render them next to the number they qualify, without
anyone remembering to check a document.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["info", "warning", "critical"]
RiskLevel = Literal["minimal", "low", "moderate", "high", "critical"]
Confidence = Literal["low", "moderate", "high"]
Language = Literal["en", "ar"]
SensitivityStatus = Literal["PLACEHOLDER_PENDING_MARINE_SCIENTIST", "SCIENTIST_ASSIGNED"]


class Caveat(BaseModel):
    """A limitation attached to a specific field of a specific response."""

    field: str = Field(description="Which response field this qualifies")
    message: str = Field(description="Human-readable; safe to render verbatim")
    severity: Severity
    source: str | None = Field(
        default=None,
        description="Where this caveat is documented, so the UI can deep-link to it",
    )


class Provenance(BaseModel):
    """Source vs derived, made explicit. Standing law #5."""

    kind: Literal["source", "derived", "assumed", "stub"]
    detail: str


# The frontend's OWN vocabulary for this, transcribed from
# frontend/src/api/types.ts:16 exactly — NOT this file's `Provenance{kind,detail}`
# class above, which is a different, pre-existing concept (a list of source notes
# on catchments/runoff/etc.) already used elsewhere and out of scope to touch here.
# Data-quality classification, distinct from source-vs-derived.
ValueProvenance = Literal["measured", "reported", "converted", "modelled"]


class Value(BaseModel):
    """A number, its unit, and where it came from — travelling together.

    Issue #14: units must never be baked into a formatted string like "2.18 g/L",
    because RTL reorders it into "g/L 2.18" and because a client that wants the
    number has to regex it back out. `unit` and `provenance` are both required
    (not `| None`), which is the point — OPEN-ISSUES.md #6 frames it as "a Value
    without provenance fails type-check, so an unlabelled number cannot reach the
    screen." `value` alone is optional: a gap (e.g. Component A's
    predicted_runoff_m3) still has a definite unit and a definite reason it is
    absent, so the unit and provenance survive even when the number does not.

    THIS SHAPE IS NOT INVENTED HERE. `frontend/src/api/types.ts` already declares
    `interface Value { value: number; unit: string; provenance: Provenance; ... }`
    with `Provenance = 'measured'|'reported'|'converted'|'modelled'`, and
    `frontend/src/components/ValueWithUnit.tsx` already renders it (`ValueField`).
    An earlier version of this class used `provenance: Provenance` (this file's
    `{kind, detail}` class) — a plausible-looking but WRONG shape that would have
    silently failed to render (`FORM[provenance]` indexing a lookup table with an
    object, not a string) the moment any endpoint actually returned one. Caught
    before push by reading the frontend code this was supposed to satisfy, not
    assumed compatible.

    New fields should use this from the start. Existing bare-float fields already
    consumed by the frontend (area_km2, lon/lat, risk_score, ...) are deliberately
    NOT retrofitted here — that would be an unannounced breaking change to an
    already-built, feature-complete UI, which is exactly the kind of contract
    drift this file's own header warns against. Retrofitting those is a separate,
    coordinated pass.
    """

    value: float | None
    unit: str
    provenance: ValueProvenance
    # Matches frontend/src/api/types.ts's `uncertainty?: {lower,upper}|{sigma}` exactly
    # — added for the mooring endpoint's salinity_anomaly (Phase 4), which needs
    # {"sigma": 19}. Optional and additive: no existing Value-typed field populates
    # this today, so nothing already shipped changes shape.
    uncertainty: dict[str, float] | None = None


# --------------------------------------------------------------------- health

class HealthOut(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    artifacts_present: dict[str, bool]
    degraded_reason: list[str] = []


class DataSourceOut(BaseModel):
    """Drives the UI's Data Sources panel. Standing law #6."""

    name: str
    product_version: str
    access_date: str
    access_method: str
    spatial_resolution: str | None = None
    licence: str
    limitations: list[str]
    qa_figures: list[str] = []
    substituted: bool = False
    substitution_note: str | None = None


# ----------------------------------------------------------------- geometry

class CatchmentOut(BaseModel):
    catchment_id: str = Field(description='"AQ-C01".."AQ-C05"')
    outlet_id: str | None
    area_km2: float
    geometry: dict | None = Field(default=None, description="GeoJSON geometry")
    landcover: dict[str, float] | None = None
    soil: dict[str, float] | None = None
    urban: dict[str, float] | None = None
    provenance: list[Provenance] = []
    caveats: list[Caveat] = []


class ReefZoneOut(BaseModel):
    reef_zone_id: str = Field(description='"R-01".."R-08"')
    zone_name: str | None = None
    habitat_class: str | None
    area_km2: float
    sensitivity_weight: float
    sensitivity_weight_status: SensitivityStatus
    marine_park_overlap_pct: float | None = None
    depth_median_m: float | None = Field(
        default=None,
        description="Median over WATER cells only. Null where a zone has no water cell "
                    "at all (R-02). Never coerce null to 0 — read depth_land_cell_pct.",
    )
    depth_land_cell_pct: float | None = Field(
        default=None,
        description="Share of 50 m bathymetry cells under the zone that read as land. "
                    "39-100% in practice; check it before using depth_median_m.",
    )
    habitat_class_code: int | None = None
    habitat_class_mix: str | None = Field(
        default=None, description='Composition by AREA, e.g. "Coral/Algae:89%;Rock:11%"'
    )
    geomorphic_class: str | None = None
    geometry: dict | None = None
    caveats: list[Caveat] = []


class OutletOut(BaseModel):
    outlet_id: str = Field(description='"AQ-O01".."AQ-O05"')
    catchment_id: str | None = None
    lon: float
    lat: float
    # The canonical vocabulary, pinned by tests/test_position_confidence_vocabulary.py.
    # "unchecked" is a real, distinct state — not a synonym for "low" — for any
    # outlet the geometry cross-check has not yet covered.
    position_confidence: Literal["high", "low", "unchecked"]
    position_confidence_note: str | None = Field(
        default=None,
        description="Why position_confidence is what it is, e.g. 'routes through "
                    "the container terminal and reclaimed land'.",
    )
    culvert_verdict: str | None = Field(
        default=None,
        description="Outcome of the DEM-vs-OSM culvert cross-check for this outlet.",
    )
    # Bare floats, NOT Value — frontend/src/api/types.ts:99-110 already declares
    # `Outlet.upstream_km2?: number` and `nearest_culvert_m?: number`, and
    # SideRail.tsx:147 already reads `o.upstream_km2` as a number today. Ali's type
    # predates this pass and anticipated these exact field names; matching it is
    # the contract, not a choice. An earlier version of this file wrapped these two
    # in Value, which would have broken that render the moment live mode (rather
    # than fixtures) actually populated them — caught before push.
    upstream_km2: float | None = None
    nearest_culvert_m: float | None = None
    culverts_within_2500m: int | None = None
    unmodelled_coastal_culverts: int | None = None
    caveat: str | None = None


class EventOut(BaseModel):
    event_id: str = Field(description='"AQ-YYYY-MM-DD"')
    start: str | None = None
    end: str | None = None
    label: str | None = None
    source: str | None = None
    caveats: list[Caveat] = []

    # From the real 675-event catalogue (data/processed/events/events.parquet),
    # via data_access.event_catalogue() -- None for an event that exists only in
    # docs/event_dates.md's literature list and not in the rainfall-detected
    # catalogue (should not happen for a real event, but never assumed).
    rank: int | None = Field(
        default=None, description="1 = highest max_daily_mm of all 675 candidate "
                                   "events. THE canonical ranking -- see max_daily_mm.")
    max_daily_mm: float | None = None
    mean_daily_mm: float | None = None
    max_anomaly_ratio: float | None = Field(
        default=None, description="Not the ranking column -- max_daily_mm/rank is. "
                                   "This ranks storms differently; exposed for reference, "
                                   "not as an alternate ranking to pick between.")
    catchments_exceeding_p99: int | None = None
    wettest_catchment: str | None = None
    storm_days: int | None = None
    is_exhaustive: bool | None = Field(
        default=None, description="True once the full ~28-year daily record has been "
                                   "screened and ranked (build_event_catalogue.py).")
    intensity_top_percent: float | None = Field(
        default=None, description='Empirical "top N%": this event\'s max_daily_mm '
                                   "is in the top N% of all days in wettest_catchment's "
                                   "~28-year record. A real percentile of the record, "
                                   "NOT max_anomaly_ratio. None if the daily record or "
                                   "the wettest catchment is absent.")


class MooringMarker(BaseModel):
    key: str
    t: datetime
    provenance: ValueProvenance


class MooringOut(BaseModel):
    """A thin read-through of data/processed/marine/mooring_target_{event_id}.json —
    Phase 4, feature 10 (Real Sensor Proof Overlay). Shape matches
    frontend/public/fixtures/event.json's already-shipped `mooring` object
    field-for-field, so swapping fixture -> live needs no frontend change."""

    event_id: str
    source_citation: str
    source_doi: str
    source_file: str
    position: dict
    markers: list[MooringMarker]
    elevated_duration_hours: Value
    peak_suspended_sediment: Value
    salinity_minimum: Value
    salinity_anomaly: Value
    sediment_mass_total: Value
    series_available: bool = False
    caveats: list[Caveat] = []


class DiveSiteOut(BaseModel):
    """A dive-site POI joined to its nearest reef zone — Phase 4, feature B
    (Dive Site Safety Status). `osm_id` is the stable join key (Karam's 6 Aug
    handoff). `distance_m` is a real EPSG:32636 measurement, always reported —
    the source OSM category ("kind: dive") also carries Wadi Rum desert
    attractions tens of km inland, and a large distance here is exactly how a
    caller tells those apart from an actual coastal dive site, rather than the
    API silently dropping or silently including them."""

    osm_id: str
    name_en: str | None = None
    name_ar: str | None = None
    lon: float
    lat: float
    nearest_reef_zone_id: str | None = None
    distance_m: float | None = None
    caveats: list[Caveat] = []


class SeasonalMonthOut(BaseModel):
    """One calendar month of the seasonal rainfall-intensity calendar
    (scripts/29_seasonal_risk_calendar.py). Buckets by RAINFALL INTENSITY, not
    exposure score — the frontend must frame it that way, since the sediment model
    is anchored to a single October event and an exposure calendar would read flat
    everywhere else. `worst_event_id` links the month to its heaviest storm."""

    month: int = Field(description="1 = January … 12 = December")
    month_name: str
    event_count: int
    max_daily_mm: float | None = None
    mean_daily_mm: float | None = None
    worst_event_id: str | None = None


# -------------------------------------------------------------------- runoff

class RunoffRequest(BaseModel):
    catchment_id: str
    rainfall_mm_3h: float = Field(ge=0)
    antecedent_index: float | None = None
    event_id: str | None = None
    # What-if scenario controls — Phase 4. Bounds are not invented: they are
    # ScenarioDrawer.tsx's own existing slider ranges (rainfallScale 50-200%,
    # unvalidated tau range from SedimentParams.validate()), so the API can only ever
    # be asked for what the UI can actually produce.
    rainfall_multiplier: float = Field(
        default=1.0, ge=0.5, le=2.0,
        description="Scales raw rainfall-depth features only, never percentile-rank "
                    "features — see main.py's RAINFALL_MM_COLUMNS.",
    )
    transmission_loss_override: float | None = Field(
        default=None, ge=0.20, le=0.85,
        description="Substitutes SedimentParams.transmission_loss for this request "
                    "only, via SedimentProxy.with_transmission_loss(). None leaves the "
                    "anchored default (0.525) in place. Bounded to TAU_NEGEV "
                    "(0.20-0.85) — the nearest studied desert analog to Aqaba's "
                    "wadis — per docs/HANDOFF_transmission_loss_2026-08-06.md, "
                    "deliberately narrower than SedimentParams.validate()'s "
                    "technical [0, 1) sanity check, which is not a claim of "
                    "physical plausibility for this environment.",
    )


class DriverOut(BaseModel):
    """One SHAP driver, renamed at the API boundary to match the frontend's already-
    shipped PredictionDriver (frontend/src/api/predictions.ts) — `feature`/`shap` are
    the model's own names (runoff_model.py), `key`/`contribution` are what
    DriverBars.tsx already renders."""

    key: str
    contribution: float
    value: float | None


class RunoffPrediction(BaseModel):
    catchment_id: str

    # `None`, not 0.0. Component A is a runoff CLASSIFIER — it predicts whether runoff
    # occurs, not how many cubic metres. There is no volume to report, and a 0.0 here
    # renders on a risk card as "0 m3 of runoff", which is a fabricated number wearing
    # the authority of a model output. The field stays so the shape does not change if a
    # volume regressor is trained later.
    predicted_runoff_m3: float | None = Field(
        default=None,
        description="None while Component A is occurrence-only. A gap, never a zero.",
    )
    relative_sediment_intensity: float = Field(
        ge=0, le=1, description="Normalised 0-1; feeds the exposure formula"
    )

    # What the classifier actually produces. Carried explicitly rather than squeezed
    # into relative_sediment_intensity, which is a sediment quantity and was silently
    # being served the runoff probability instead.
    runoff_probability: float | None = Field(
        default=None, ge=0, le=1,
        description="Probability that runoff occurs. None when no model is registered.",
    )
    severity: str | None = Field(
        default=None, description="Model's own severity band for the probability."
    )
    confidence: float | None = Field(
        default=None, ge=0, le=1,
        description="Derived, with its components in the model's confidence_terms.",
    )
    # Vocabulary is `low|medium|high|extreme`, lowercase, and `None` when the sediment
    # proxy has not run for this row.
    #
    # This field was `low|moderate|high|extreme`, which three modules disagreed about:
    # sediment_proxy.CLASSES emits ("Low","Medium","High","Extreme"),
    # particle_engine.SEDIMENT_CLASS_PARTICLE_SCALE keys on lowercase "medium", and this
    # schema mandated "moderate". So the only value the schema allowed in that slot
    # raised ValueError in the particle engine, and the value the proxy actually produces
    # failed validation here. `medium` is the spelling that works end to end.
    #
    # `None` is permitted rather than defaulted, because runoff_model.py returns None for
    # sediment_class when the proxy has not run, and `sediment_basis` carries the reason.
    # Substituting a class there would invent a sediment severity nobody computed — the
    # rule is that a gap is reported, never filled in.
    sediment_class: Literal["low", "medium", "high", "extreme"] | None = Field(
        default=None,
        description="None when the sediment proxy has not run; read sediment_basis for why.",
    )
    model_version: str
    is_stub: bool = Field(
        description="True while wired to a stub. Never ingest stub output into the "
                    "RAG corpus or a slide."
    )
    # Real SHAP driver attributions — Phase 4. The model has computed these since
    # Phase 2 (runoff_model.py's TreeSHAP path); this schema never had a field for
    # them. `key`/`contribution` names match frontend/src/api/predictions.ts's
    # PredictionDriver exactly, so no further rename is needed downstream —
    # `feature`/`shap` (the model's own names) are remapped to `key`/`contribution` at
    # this boundary, in main.py.
    drivers: list[DriverOut] = []
    feature_attributions_status: str | None = Field(
        default=None,
        description="Non-null only when TreeSHAP failed for this row — an explicit "
                    "gap, never a silent zero-fill. See runoff_model.py's "
                    "shap_unavailable.",
    )
    # Scenario echo — Phase 4. The caller must be able to see what was actually used,
    # not just what was requested; RunoffRequest.rainfall_multiplier and
    # .transmission_loss_override are echoed back here regardless of whether they
    # were the default.
    rainfall_multiplier: float = 1.0
    transmission_loss: float | None = Field(
        default=None,
        description="The model's own computed transmission_loss for this row (real "
                    "path only) — 0.525 unless transmission_loss_override was set.",
    )
    # Phase 5, B2. "learned" has no implementation yet — see
    # docs/HANDOFF_abd_2026-08-07_b2_data.md. Every transmission_loss value in the
    # system today, default or slider-overridden, is a point on the borrowed Negev
    # range, never a per-catchment estimate — so this is "negev_proxy" whenever
    # transmission_loss is set, and None (not "negev_proxy") when it isn't, same as
    # the field it describes.
    transmission_loss_basis: Literal["learned", "negev_proxy"] | None = Field(
        default=None,
        description="Which source produced transmission_loss. 'learned' does not "
                    "exist yet — always 'negev_proxy' on the real path today.",
    )
    provenance: list[Provenance] = []
    caveats: list[Caveat] = []


# --------------------------------------------------------------------- plume

class PlumeRequest(BaseModel):
    event_id: str
    outlet_id: str
    horizon_hours: int = Field(default=24, ge=1, le=120)
    n_particles: int = Field(default=2000, ge=100, le=100_000)
    diffusion_m2_s: float | None = None
    windage: float | None = None


class PlumeContour(BaseModel):
    t_hours: float
    probability: float = Field(ge=0, le=1)
    geometry: dict


class PlumeResult(BaseModel):
    run_id: str
    event_id: str
    outlet_id: str
    contours: list[PlumeContour]
    model_version: str
    is_stub: bool
    provenance: list[Provenance] = []
    caveats: list[Caveat] = []


# ------------------------------------------------------------------ exposure

class ExposureRequest(BaseModel):
    event_id: str
    outlet_id: str
    catchment_id: str | None = None
    horizon_hours: int = Field(default=24, ge=1, le=120)
    reef_zone_ids: list[str] | None = Field(
        default=None, description="Defaults to every zone"
    )
    # Same two what-if fields as RunoffRequest, same bounds, same rationale — see
    # RunoffRequest's docstring. Applied to the real feature row before predict_one()
    # in exposure_calculate's real-row branch (main.py).
    rainfall_multiplier: float = Field(default=1.0, ge=0.5, le=2.0)
    transmission_loss_override: float | None = Field(default=None, ge=0.20, le=0.85)


class ExposureResult(BaseModel):
    reef_zone_id: str
    risk_score: float = Field(ge=0, le=100)
    risk_level: RiskLevel
    arrival_window_hours: tuple[float, float] | None
    max_exposure_probability: float = Field(ge=0, le=1)
    zone_fraction_affected: float = Field(
        ge=0, le=1,
        description="Fraction of the NAMED zone area. Preferred over an absolute "
                    "km2, which would imply precision the 250 m width assumption "
                    "does not support.",
    )
    confidence: Confidence
    formula_terms: dict = Field(
        description="Every input that produced risk_score. Non-negotiable: a score "
                    "you cannot reconstruct six hours later is a number nobody can "
                    "defend."
    )
    # Phase 5, B7 — additive, never a change to risk_score itself.
    # exposure/engine.py's own docstring warns against folding a new term into
    # the formula ("would change the ranking... while looking like a
    # presentation detail"), so this is a separate field that DEFAULTS to
    # risk_score exactly when a zone has no real sampling feedback yet.
    adjusted_priority: float = Field(
        description="Equals risk_score exactly until "
                    "sampling_feedback.MIN_FEEDBACK_FOR_ADJUSTMENT real outcomes "
                    "exist for this zone — the fallback is the literal default, "
                    "not a special case."
    )
    adjusted_priority_status: Literal["NO_FEEDBACK_YET", "FEEDBACK_APPLIED"]
    caveats: list[Caveat] = []


class SamplingFeedbackRequest(BaseModel):
    """Phase 5, B7 — did a real sample confirm the exposure run's prediction
    for this zone? `run_id` must be a real, already-stored exposure run — this
    is logged feedback on an actual prediction, not a free-floating opinion."""

    run_id: str
    outcome: Literal["confirmed", "not_confirmed"]


class ExposureRun(BaseModel):
    run_id: str
    event_id: str
    outlet_id: str
    created_at: datetime
    results: list[ExposureResult]
    model_versions: dict[str, str]
    caveats: list[Caveat] = []


# ----------------------------------------------------------------- backtests

class BacktestRequest(BaseModel):
    event_id: str
    outlet_id: str | None = None
    baseline: Literal["circular_buffer", "none"] = "circular_buffer"


class BacktestResult(BaseModel):
    run_id: str
    event_id: str
    status: Literal["queued", "running", "complete", "failed", "not_possible"]
    metrics: dict[str, float] | None = None
    baseline_metrics: dict[str, float] | None = None
    note: str | None = None
    caveats: list[Caveat] = []


# -------------------------------------------------------------------- alerts

class AlertOut(BaseModel):
    alert_id: str
    source_run_id: str = Field(
        description="The exposure run this alert was derived from, so an alert on "
                    "screen is always traceable to a stored formula_terms trail."
    )
    reef_zone_id: str
    risk_level: RiskLevel
    risk_score: float
    issued_at: datetime
    arrival_window_hours: tuple[float, float] | None
    headline_en: str
    headline_ar: str
    caveats: list[Caveat] = []


# ------------------------------------------------------ response recommendations

class RecommendationTriggerRequest(BaseModel):
    run_id: str
    min_risk_level_override: RiskLevel | None = Field(
        default=None,
        description="Human-in-the-loop escape hatch: forces a swarm run below the "
                    "default high/critical gate. Requires authentication — the "
                    "override itself is part of the audit trail, never a silent "
                    "bypass (tasks/phase9/00-phase9-plan.md §2).",
    )


class RecommendationTurnOut(BaseModel):
    round: int
    agent_role: str
    content: str
    evidence_cited: list[str]
    created_at: datetime


class RecommendationVerdictOut(BaseModel):
    verdict: Literal["approved", "rejected"]
    evidence_cited: list[str]
    reasoning: str
    created_at: datetime


class RecommendationGapOut(BaseModel):
    gap_description: str
    severity: Literal["low", "medium", "high"] | None
    created_at: datetime


class ResponseRecommendationOut(BaseModel):
    id: str
    run_id: str
    event_id: str | None
    triggered_by: Literal["auto", "human_override"]
    triggered_by_user: str | None
    min_risk_level_override: str | None
    severity_brief: dict
    final_recommendation: str | None
    status: Literal["running", "proposed", "judge_approved", "judge_rejected", "finalized"]
    rounds_used: int | None
    converged: bool | None
    model: str
    created_at: datetime
    completed_at: datetime | None
    turns: list[RecommendationTurnOut] = []
    verdicts: list[RecommendationVerdictOut] = []
    gaps: list[RecommendationGapOut] = []


# ------------------------------------------------------------------- explain

class ExplainRequest(BaseModel):
    catchment_id: str
    language: Language = "en"
    shap_drivers: list[dict] = Field(
        default_factory=list,
        description='e.g. [{"feature": "rainfall_3h_mm", "value": 41.2, '
                    '"contribution": 0.31}] — passed through verbatim. `/runoff/predict`\'s '
                    'own `drivers` field names this the same way except "key" instead of '
                    '"feature" (DriverOut); rag.explain accepts either, so that response '
                    'can be forwarded here unmodified.',
    )
    plume_probability: float | None = Field(default=None, ge=0, le=1)
    arrival_window_hours: tuple[float, float] | None = None
    confidence: Confidence | None = None
    reef_zone_id: str | None = None
    rainfall_percentile: float | None = None


class ExplainResponse(BaseModel):
    text: str
    language: Language
    source_numbers: dict = Field(
        description="Exactly the numbers handed in. The generator phrases these and "
                    "computes nothing; tests assert every one appears unaltered."
    )
    generator: Literal["deterministic_template", "llm"]
    caveats: list[Caveat] = []


# ----------------------------------------------------------------------- ask

class Citation(BaseModel):
    source_file: str
    section: str
    excerpt: str
    score: float | None = None


class AskRequest(BaseModel):
    question: str = Field(min_length=1)
    language: Language = "en"
    k: int = Field(default=5, ge=1, le=20)


class AskResponse(BaseModel):
    answer: str
    citations: list[Citation] = Field(
        description="An uncited answer is not shippable; the route asserts this."
    )
    language: Language
    corpus_files_searched: int


# ------------------------------------------------------------ assistant chat

class AssistantChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    text: str


class AssistantChatRequest(BaseModel):
    message: str = Field(min_length=1)
    history: list[AssistantChatMessage] = Field(default_factory=list, max_length=12)
    language: Language = "en"


class AssistantToolCall(BaseModel):
    tool: str
    args: dict
    summary: str = Field(description="Short human-readable note of what was fetched")


class AssistantChatResponse(BaseModel):
    text: str
    tools_used: list[AssistantToolCall] = []
    citations: list[Citation] = Field(
        default=[], description="Populated only when search_docs was used this turn"
    )
    suggested_route: str | None = Field(
        default=None, description="Validated against a known route; never the model's raw string"
    )
    caveats: list[Caveat] = []
    model: str


# ------------------------------------------------------- site scoring (Phase 5, B4)

class SiteScoreRequest(BaseModel):
    bbox: tuple[float, float, float, float] = Field(
        description="(west, south, east, north) — EPSG:4326, same ordering as "
                    "config.spatial.BBox.wsen. Not restricted to the Aqaba AOI; "
                    "criteria outside this project's real data coverage report "
                    "status='insufficient_data' rather than a fabricated score."
    )
    site_name: str | None = None


class CriterionScore(BaseModel):
    criterion: Literal["C1", "C2", "C3", "C4", "C5", "C6"]
    score: float | None = Field(
        default=None, ge=0, le=2,
        description="None, not 0.0, when evidence is absent — a gap is a gap.",
    )
    status: Literal["scored", "insufficient_data"]
    evidence: list[Citation] = Field(
        description="Reuses the /ask citation shape verbatim — never a second "
                    "citation format. Non-empty even when status is "
                    "insufficient_data: the absence itself is cited."
    )


class SiteScoreResponse(BaseModel):
    site_id: str = Field(description='"site_{ULID}" — never a squatted AQ-* id')
    site_name: str | None
    bbox: tuple[float, float, float, float]
    criteria: list[CriterionScore]
    narrative: str = Field(
        description="Deterministic template over the real per-criterion evidence "
                    "above — no generative model call anywhere in this path."
    )
    caveats: list[Caveat] = Field(
        description="Always carries the 'validated on exactly one site' caveat, "
                    "regardless of which box was scored."
    )


# -------------------------------------------------- forensic reports (Phase 5, B5)

class ReportClaim(BaseModel):
    text: str
    source: str | None = Field(
        default=None,
        description="A real formula_terms/citation key, or None when the "
                    "underlying data genuinely doesn't exist — never fabricated.",
    )


class ReportSection(BaseModel):
    title: str
    claims: list[ReportClaim]


class GenerateReportRequest(BaseModel):
    event_id: str


class ReviewReportRequest(BaseModel):
    reviewed_by: str = Field(min_length=1, description="Required, not optional — "
                             "a report cannot silently review itself.")


class ReportOut(BaseModel):
    report_id: str = Field(description='"report_{ULID}"')
    event_id: str
    status: Literal["ai_drafted", "human_reviewed"]
    generated_at: datetime
    reviewed_at: datetime | None = None
    reviewed_by: str | None = None
    sections: list[ReportSection]


# --------------------------------------------------- coral health vision (Phase 5, B8)

class ReefZonePhotoOut(BaseModel):
    photo_id: str = Field(description='"photo_{ULID}"')
    reef_zone_id: str
    uploaded_at: datetime
    predicted_class: Literal["healthy", "stressed", "bleached"]
    confidence: float = Field(ge=0, le=1)
    model_basis: Literal["heuristic_rule_v1", "trained_classifier"] = Field(
        description="'heuristic_rule_v1' is the honest default with zero real "
                    "training data — travels on every classification, never "
                    "presented as a validated model result."
    )
    model_version: str | None = None


class ProposedSensitivityWeightOut(BaseModel):
    reef_zone_id: str
    proposed_value: float | None = Field(
        default=None,
        description="None until MIN_PHOTOS_FOR_PROPOSAL real classifications "
                    "exist for this zone — never computed from too little "
                    "evidence to mean anything.",
    )
    status: Literal["INSUFFICIENT_PHOTOS", "PROPOSED_PENDING_REVIEW"]
    n_photos: int
    live_sensitivity_weight: float = Field(
        description="The value the exposure engine actually reads right now, "
                    "for comparison — this endpoint never changes it.",
    )
    live_sensitivity_weight_status: SensitivityStatus


class ApproveSensitivityWeightRequest(BaseModel):
    """The one and only way `sensitivity_weight` can move — Standing Law rule
    13. `reviewer`/`reasoning` are required, not optional: a report cannot
    review itself, and this field cannot approve itself either."""

    reviewer: str = Field(min_length=1)
    reasoning: str = Field(min_length=1)
    approved_value: float = Field(
        ge=0, description="The value a human is choosing to apply — may differ "
                          "from the proposed value; this is a decision, not a rubber stamp."
    )


class ApproveSensitivityWeightResponse(BaseModel):
    reef_zone_id: str
    approval_id: str
    approved_value: float
    approved_at: datetime
    reviewer: str
