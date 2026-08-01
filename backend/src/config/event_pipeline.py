"""Typed configuration for the event-agnostic ReefShield pipeline.

A pipeline run is fully described by one YAML file: which event, which box,
which time ranges, which products and which outputs. Changing only the YAML
runs the same code for a different event — nothing about October 2016 lives in
the source.

Validation is deliberately strict. A configuration that would silently produce
misleading science is rejected up front rather than halfway through a download:
non-UTC timestamps, reversed ranges, impossible boxes, unknown variables,
Final/Early mixing, and output paths escaping the project all fail fast.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "backend" / "src"))

from ingestion.era5_land import ERA5_SHORT_NAMES, ERA5_VARIABLES  # noqa: E402
from ingestion.imerg import IMERG_PRODUCTS  # noqa: E402

#: Rolling windows must be whole multiples of the 30-minute IMERG interval.
MINIMUM_ROLLING_HOURS = 0.5


class ConfigError(ValueError):
    """Raised when a pipeline configuration is invalid."""


def _parse_utc(value: Any, label: str) -> datetime:
    """Accept ISO-8601 with an explicit UTC marker; reject anything else."""
    if isinstance(value, datetime):
        moment = value
        if moment.tzinfo is None:
            raise ConfigError(
                f"{label} must state a timezone; use a trailing 'Z' for UTC."
            )
    else:
        text = str(value).strip()
        if not (text.endswith("Z") or text.endswith("+00:00")):
            raise ConfigError(
                f"{label}={text!r} must be UTC — end it with 'Z' or '+00:00'. "
                "Local times silently shift events across day boundaries."
            )
        try:
            moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ConfigError(f"{label}={text!r} is not ISO-8601.") from exc

    if moment.utcoffset() != timedelta(0):
        raise ConfigError(
            f"{label} must be UTC, got offset {moment.utcoffset()}."
        )
    return moment.astimezone(timezone.utc)


class Spatial(BaseModel):
    """Bounding box in plain west/south/east/north degrees."""

    model_config = ConfigDict(extra="forbid")

    west: float
    south: float
    east: float
    north: float

    @model_validator(mode="after")
    def _check_box(self) -> "Spatial":
        if self.north <= self.south:
            raise ConfigError(
                f"north ({self.north}) must exceed south ({self.south})."
            )
        if self.east <= self.west:
            raise ConfigError(
                f"east ({self.east}) must exceed west ({self.west})."
            )
        if not (-90 <= self.south < self.north <= 90):
            raise ConfigError("latitudes must lie within [-90, 90].")
        if not (-180 <= self.west < self.east <= 180):
            raise ConfigError("longitudes must lie within [-180, 180].")
        return self

    @property
    def imerg_bbox(self) -> tuple[float, float, float, float]:
        """(west, south, east, north) — Harmony order."""
        return (self.west, self.south, self.east, self.north)

    @property
    def cds_area(self) -> list[float]:
        """[North, West, South, East] — CDS order."""
        return [self.north, self.west, self.south, self.east]


class ImergConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    run_type: Literal["final", "early"] = "final"
    start_time: datetime | str
    end_time: datetime | str
    rolling_windows_hours: list[float] = Field(default_factory=lambda: [1, 3, 6, 24])
    max_granules: int = 500
    chunk_granules: int = 48

    @model_validator(mode="after")
    def _check(self) -> "ImergConfig":
        self.start_time = _parse_utc(self.start_time, "imerg.start_time")
        self.end_time = _parse_utc(self.end_time, "imerg.end_time")
        if self.end_time < self.start_time:
            raise ConfigError("imerg.end_time precedes imerg.start_time.")
        if self.run_type not in IMERG_PRODUCTS:
            raise ConfigError(f"unknown imerg.run_type {self.run_type!r}")
        if not IMERG_PRODUCTS[self.run_type].get("capabilities_verified"):
            raise ConfigError(
                f"imerg.run_type {self.run_type!r} has not been capability-"
                "verified."
            )
        if not self.rolling_windows_hours:
            raise ConfigError("imerg.rolling_windows_hours must not be empty.")
        for hours in self.rolling_windows_hours:
            if hours < MINIMUM_ROLLING_HOURS:
                raise ConfigError(
                    f"rolling window {hours} h is shorter than the "
                    f"{MINIMUM_ROLLING_HOURS} h granule interval."
                )
            if abs((hours / MINIMUM_ROLLING_HOURS) % 1) > 1e-9:
                raise ConfigError(
                    f"rolling window {hours} h is not a whole multiple of the "
                    f"{MINIMUM_ROLLING_HOURS} h granule interval."
                )
        if self.max_granules < 1:
            raise ConfigError("imerg.max_granules must be positive.")
        if self.chunk_granules < 1:
            raise ConfigError("imerg.chunk_granules must be positive.")
        return self

    @property
    def expected_granules(self) -> int:
        span = (self.end_time - self.start_time).total_seconds()
        return int(span // 1800) + 1


class AntecedentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_time: datetime | str
    soil_moisture_offsets_hours: list[int] = Field(default_factory=lambda: [24, 72])
    precipitation_windows_hours: list[int] = Field(
        default_factory=lambda: [24, 72, 168])
    runoff_windows_hours: list[int] = Field(default_factory=lambda: [24, 72, 168])
    state_window_hours: int = 6

    @model_validator(mode="after")
    def _check(self) -> "AntecedentConfig":
        self.event_time = _parse_utc(
            self.event_time, "era5_land.antecedent.event_time"
        )
        if self.event_time.minute or self.event_time.second:
            raise ConfigError("antecedent.event_time must be hour-aligned.")
        for label, values in (
            ("soil_moisture_offsets_hours", self.soil_moisture_offsets_hours),
            ("precipitation_windows_hours", self.precipitation_windows_hours),
            ("runoff_windows_hours", self.runoff_windows_hours),
        ):
            if any(v <= 0 for v in values):
                raise ConfigError(f"antecedent.{label} must all be positive.")
        if self.state_window_hours <= 0:
            raise ConfigError("antecedent.state_window_hours must be positive.")
        return self


class Era5LandConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    start_time: datetime | str
    end_time: datetime | str
    variables: list[str]
    temporal_semantics_mode: Literal["auto", "hourly", "cumulative"] = "auto"
    chunk_mode: Literal["daily", "monthly"] = "daily"
    max_expected_timestamps: int = 2000
    negative_tolerance_m: float = 1e-7
    antecedent: AntecedentConfig | None = None

    @model_validator(mode="after")
    def _check(self) -> "Era5LandConfig":
        self.start_time = _parse_utc(self.start_time, "era5_land.start_time")
        self.end_time = _parse_utc(self.end_time, "era5_land.end_time")
        if self.end_time < self.start_time:
            raise ConfigError("era5_land.end_time precedes start_time.")
        if not self.variables:
            raise ConfigError("era5_land.variables must not be empty.")

        known = set(ERA5_VARIABLES) | set(ERA5_VARIABLES.values()) | set(
            ERA5_SHORT_NAMES)
        unknown = [v for v in self.variables if v not in known]
        if unknown:
            raise ConfigError(
                f"unknown era5_land.variables {unknown}; known keys: "
                f"{sorted(ERA5_VARIABLES)}"
            )
        if self.antecedent is not None:
            event = self.antecedent.event_time
            if not (self.start_time <= event <= self.end_time):
                raise ConfigError(
                    f"antecedent.event_time {event.isoformat()} lies outside "
                    f"the ERA5-Land window {self.start_time.isoformat()} .. "
                    f"{self.end_time.isoformat()}."
                )
        return self

    @property
    def expected_timestamps(self) -> int:
        span = (self.end_time - self.start_time).total_seconds()
        return int(span // 3600) + 1


class OutputsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    root_dir: str = "data"
    save_netcdf: bool = True
    save_json: bool = True
    save_parquet: bool = True
    allow_external_paths: bool = False

    @model_validator(mode="after")
    def _check(self) -> "OutputsConfig":
        resolved = (PROJECT_ROOT / self.root_dir).resolve() \
            if not Path(self.root_dir).is_absolute() \
            else Path(self.root_dir).resolve()
        if not self.allow_external_paths:
            try:
                resolved.relative_to(PROJECT_ROOT.resolve())
            except ValueError as exc:
                raise ConfigError(
                    f"outputs.root_dir {resolved} is outside the project. Set "
                    "allow_external_paths: true to permit it deliberately."
                ) from exc
        return self


class ValidationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    minimum_data_completeness: float = 95.0
    fail_on_missing_timestamps: bool = True
    require_full_antecedent_windows: bool = True
    minimum_valid_fraction: float = 1.0

    @model_validator(mode="after")
    def _check(self) -> "ValidationConfig":
        if not 0 <= self.minimum_data_completeness <= 100:
            raise ConfigError(
                "validation.minimum_data_completeness must be a percentage."
            )
        if not 0 <= self.minimum_valid_fraction <= 1:
            raise ConfigError(
                "validation.minimum_valid_fraction must be within [0, 1]."
            )
        return self


class EventPipelineConfig(BaseModel):
    """A complete, self-describing pipeline run.

    Pydantic wraps validator exceptions in ``ValidationError``. Since every
    rule here raises :class:`ConfigError` deliberately, the wrapper is undone
    at construction so callers see one exception type with a readable message.
    """

    model_config = ConfigDict(extra="forbid")

    def __init__(self, **data: Any) -> None:
        try:
            super().__init__(**data)
        except ConfigError:
            raise
        except Exception as exc:
            raise ConfigError(str(exc)) from exc

    event_id: str
    description: str = ""
    spatial: Spatial
    imerg: ImergConfig | None = None
    era5_land: Era5LandConfig | None = None
    outputs: OutputsConfig = Field(default_factory=OutputsConfig)
    validation: ValidationConfig = Field(default_factory=ValidationConfig)

    @field_validator("event_id")
    @classmethod
    def _check_event_id(cls, value: str) -> str:
        if not value or not value.strip():
            raise ConfigError("event_id must not be empty.")
        if any(character in value for character in "/\\ "):
            raise ConfigError(
                f"event_id {value!r} must not contain path separators or "
                "spaces; it becomes a directory name."
            )
        return value

    @model_validator(mode="after")
    def _check(self) -> "EventPipelineConfig":
        if self.imerg is None and self.era5_land is None:
            raise ConfigError("Enable at least one data source.")
        active = [
            source for source in (self.imerg, self.era5_land)
            if source is not None and source.enabled
        ]
        if not active:
            raise ConfigError("At least one data source must be enabled.")
        return self

    # --- derived paths ---------------------------------------------------

    def _root(self) -> Path:
        root = Path(self.outputs.root_dir)
        return root if root.is_absolute() else PROJECT_ROOT / root

    @property
    def imerg_raw_dir(self) -> Path:
        return self._root() / "raw" / "imerg" / "events" / self.event_id

    @property
    def era5_raw_dir(self) -> Path:
        return self._root() / "raw" / "era5_land" / "events" / self.event_id

    @property
    def processed_dir(self) -> Path:
        return self._root() / "processed" / "events" / self.event_id

    @property
    def outputs_dir(self) -> Path:
        return self._root() / "outputs" / self.event_id

    def execution_plan(self) -> dict:
        """A safe, credential-free description of what a run would do."""
        plan: dict[str, Any] = {
            "event_id": self.event_id,
            "description": self.description,
            "bbox_west_south_east_north": list(self.spatial.imerg_bbox),
            "cds_area_north_west_south_east": self.spatial.cds_area,
            "sources": {},
            "paths": {
                "imerg_raw": str(self.imerg_raw_dir),
                "era5_raw": str(self.era5_raw_dir),
                "processed": str(self.processed_dir),
                "outputs": str(self.outputs_dir),
            },
            "validation": self.validation.model_dump(),
        }
        if self.imerg is not None and self.imerg.enabled:
            product = IMERG_PRODUCTS[self.imerg.run_type]
            plan["sources"]["imerg"] = {
                "run_type": self.imerg.run_type,
                "short_name": product["short_name"],
                "collection_id": product["collection_id"],
                "suitable_for_training": product["suitable_for_training"],
                "start_utc": self.imerg.start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "end_utc": self.imerg.end_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "expected_granules": self.imerg.expected_granules,
                "max_granules": self.imerg.max_granules,
                "chunk_granules": self.imerg.chunk_granules,
                "estimated_harmony_jobs": max(
                    1,
                    -(-self.imerg.expected_granules // self.imerg.chunk_granules),
                ),
                "rolling_windows_hours": self.imerg.rolling_windows_hours,
                "within_limit": (
                    self.imerg.expected_granules <= self.imerg.max_granules
                ),
            }
        if self.era5_land is not None and self.era5_land.enabled:
            days = len({
                (self.era5_land.start_time + timedelta(hours=h)).date()
                for h in range(self.era5_land.expected_timestamps)
            })
            plan["sources"]["era5_land"] = {
                "start_utc": self.era5_land.start_time.strftime(
                    "%Y-%m-%dT%H:%M:%SZ"),
                "end_utc": self.era5_land.end_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "expected_timestamps": self.era5_land.expected_timestamps,
                "variables": self.era5_land.variables,
                "temporal_semantics_mode": self.era5_land.temporal_semantics_mode,
                "chunk_mode": self.era5_land.chunk_mode,
                "estimated_cds_requests": days,
                "within_limit": (
                    self.era5_land.expected_timestamps
                    <= self.era5_land.max_expected_timestamps
                ),
            }
            if self.era5_land.antecedent is not None:
                plan["sources"]["era5_land"]["antecedent"] = {
                    "event_time_utc": self.era5_land.antecedent.event_time
                    .strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "soil_moisture_offsets_hours":
                        self.era5_land.antecedent.soil_moisture_offsets_hours,
                    "precipitation_windows_hours":
                        self.era5_land.antecedent.precipitation_windows_hours,
                    "runoff_windows_hours":
                        self.era5_land.antecedent.runoff_windows_hours,
                    "state_window_hours":
                        self.era5_land.antecedent.state_window_hours,
                }
        return plan


def load_event_pipeline_config(path: Path) -> EventPipelineConfig:
    """Load and validate a pipeline YAML file."""
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")
    try:
        payload = yaml.safe_load(path.read_text())
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path} is not valid YAML: {exc}") from exc
    if not isinstance(payload, dict):
        raise ConfigError(f"{path} must contain a YAML mapping.")
    try:
        return EventPipelineConfig(**payload)
    except ConfigError:
        raise
    except Exception as exc:  # pydantic ValidationError
        raise ConfigError(f"Invalid configuration in {path}:\n{exc}") from exc


__all__ = [
    "AntecedentConfig",
    "ConfigError",
    "Era5LandConfig",
    "EventPipelineConfig",
    "ImergConfig",
    "OutputsConfig",
    "Spatial",
    "ValidationConfig",
    "load_event_pipeline_config",
]
