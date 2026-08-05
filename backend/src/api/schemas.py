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
    position_confidence: Literal["low", "plausible", "good"]
    caveat: str | None = None


class EventOut(BaseModel):
    event_id: str = Field(description='"AQ-YYYY-MM-DD"')
    start: str | None = None
    end: str | None = None
    label: str | None = None
    source: str | None = None
    caveats: list[Caveat] = []


# -------------------------------------------------------------------- runoff

class RunoffRequest(BaseModel):
    catchment_id: str
    rainfall_mm_3h: float = Field(ge=0)
    antecedent_index: float | None = None
    event_id: str | None = None


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
    caveats: list[Caveat] = []


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


# ------------------------------------------------------------------- explain

class ExplainRequest(BaseModel):
    catchment_id: str
    language: Language = "en"
    shap_drivers: list[dict] = Field(
        default_factory=list,
        description='e.g. [{"feature": "rainfall_3h_mm", "value": 41.2, '
                    '"contribution": 0.31}] — passed through verbatim',
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
