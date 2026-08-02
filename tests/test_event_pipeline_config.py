"""Validation tests for the config-driven event pipeline.

Pure configuration logic — no data files, no network.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend" / "src"))

from config.event_pipeline import (  # noqa: E402
    ConfigError,
    EventPipelineConfig,
    load_event_pipeline_config,
)

EXAMPLE = PROJECT_ROOT / "configs" / "event_pipeline.example.yaml"
DEMO = PROJECT_ROOT / "configs" / "october_2016_demo.yaml"

BASE = {
    "event_id": "TEST-EVENT-01",
    "spatial": {"west": 34.80, "south": 29.25, "east": 35.15, "north": 29.70},
    "imerg": {
        "enabled": True,
        "run_type": "final",
        "start_time": "2016-10-25T00:00:00Z",
        "end_time": "2016-10-28T05:59:59Z",
        "rolling_windows_hours": [1, 3, 6, 24],
    },
    "era5_land": {
        "enabled": True,
        "start_time": "2016-10-26T00:00:00Z",
        "end_time": "2016-10-28T00:00:00Z",
        "variables": ["total_precipitation", "soil_moisture"],
        "antecedent": {"event_time": "2016-10-28T00:00:00Z"},
    },
}


def build(**overrides) -> EventPipelineConfig:
    payload = copy.deepcopy(BASE)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(payload.get(key), dict):
            payload[key].update(value)
        else:
            payload[key] = value
    return EventPipelineConfig(**payload)


# --- shipped configs -------------------------------------------------------


def test_example_config_is_valid() -> None:
    config = load_event_pipeline_config(EXAMPLE)
    assert config.event_id == "EXAMPLE-EVENT-01"
    assert config.imerg.run_type == "final"


def test_demo_config_is_valid() -> None:
    config = load_event_pipeline_config(DEMO)
    assert config.event_id == "AQ-2016-10-28"
    assert config.imerg.expected_granules == 156
    assert config.era5_land.expected_timestamps == 49


def test_demo_config_is_data_not_code() -> None:
    """The October event must live only in YAML, never in the source."""
    payload = yaml.safe_load(DEMO.read_text())
    assert payload["event_id"] == "AQ-2016-10-28"

    source = (PROJECT_ROOT / "backend" / "src" / "config"
              / "event_pipeline.py").read_text()
    assert "AQ-2016-10-28" not in source
    assert "2016-10-28" not in source


def test_same_code_runs_a_different_event() -> None:
    other = build(
        event_id="XX-2020-01-02",
        spatial={"west": -10.0, "south": 40.0, "east": -9.0, "north": 41.0},
        imerg={"start_time": "2020-01-01T00:00:00Z",
               "end_time": "2020-01-01T05:59:59Z"},
        era5_land={"start_time": "2020-01-01T00:00:00Z",
                   "end_time": "2020-01-01T05:00:00Z",
                   "antecedent": {"event_time": "2020-01-01T05:00:00Z"}},
    )
    plan = other.execution_plan()
    assert plan["event_id"] == "XX-2020-01-02"
    assert plan["bbox_west_south_east_north"] == [-10.0, 40.0, -9.0, 41.0]
    assert plan["sources"]["imerg"]["expected_granules"] == 12
    assert plan["sources"]["era5_land"]["expected_timestamps"] == 6


# --- spatial ---------------------------------------------------------------


@pytest.mark.parametrize(
    "spatial",
    [
        {"west": 34.8, "south": 29.7, "east": 35.15, "north": 29.25},  # flipped
        {"west": 35.15, "south": 29.25, "east": 34.8, "north": 29.7},  # flipped
        {"west": 34.8, "south": -91.0, "east": 35.15, "north": 29.7},
        {"west": -181.0, "south": 29.25, "east": 35.15, "north": 29.7},
    ],
)
def test_invalid_bbox_rejected(spatial) -> None:
    with pytest.raises(ConfigError):
        build(spatial=spatial)


def test_bbox_order_conversion() -> None:
    config = build()
    assert config.spatial.imerg_bbox == (34.80, 29.25, 35.15, 29.70)
    assert config.spatial.cds_area == [29.70, 34.80, 29.25, 35.15]


# --- time ------------------------------------------------------------------


@pytest.mark.parametrize(
    "start", ["2016-10-25T00:00:00", "2016-10-25 00:00:00+03:00",
              "2016-10-25T00:00:00+02:00"],
)
def test_non_utc_timestamps_rejected(start) -> None:
    with pytest.raises(ConfigError, match="UTC"):
        build(imerg={"start_time": start})


def test_reversed_imerg_range_rejected() -> None:
    with pytest.raises(ConfigError, match="precedes"):
        build(imerg={"start_time": "2016-10-28T00:00:00Z",
                     "end_time": "2016-10-25T00:00:00Z"})


def test_reversed_era5_range_rejected() -> None:
    with pytest.raises(ConfigError, match="precedes"):
        build(era5_land={"start_time": "2016-10-28T00:00:00Z",
                         "end_time": "2016-10-26T00:00:00Z"})


def test_event_time_outside_era5_window_rejected() -> None:
    with pytest.raises(ConfigError, match="outside the ERA5-Land window"):
        build(era5_land={"antecedent": {"event_time": "2020-01-01T00:00:00Z"}})


def test_event_time_must_be_hour_aligned() -> None:
    with pytest.raises(ConfigError, match="hour-aligned"):
        build(era5_land={"antecedent": {"event_time": "2016-10-27T00:30:00Z"}})


# --- rolling windows -------------------------------------------------------


@pytest.mark.parametrize("windows", [[0.25], [0.4], [1, 0.1]])
def test_unsupported_rolling_windows_rejected(windows) -> None:
    with pytest.raises(ConfigError):
        build(imerg={"rolling_windows_hours": windows})


def test_empty_rolling_windows_rejected() -> None:
    with pytest.raises(ConfigError, match="must not be empty"):
        build(imerg={"rolling_windows_hours": []})


def test_half_hour_window_accepted() -> None:
    config = build(imerg={"rolling_windows_hours": [0.5, 1]})
    assert config.imerg.rolling_windows_hours == [0.5, 1]


# --- products --------------------------------------------------------------


def test_early_run_type_accepted_and_marked() -> None:
    config = build(imerg={"run_type": "early"})
    plan = config.execution_plan()
    assert plan["sources"]["imerg"]["run_type"] == "early"
    assert plan["sources"]["imerg"]["short_name"] == "GPM_3IMERGHHE"
    assert plan["sources"]["imerg"]["suitable_for_training"] is False


def test_final_marked_training_safe() -> None:
    plan = build().execution_plan()
    assert plan["sources"]["imerg"]["suitable_for_training"] is True


def test_unknown_run_type_rejected() -> None:
    with pytest.raises(ConfigError):
        build(imerg={"run_type": "late"})


def test_run_type_is_single_valued_no_mixing() -> None:
    """One config yields exactly one run type — mixing is unrepresentable."""
    config = build(imerg={"run_type": "early"})
    assert config.imerg.run_type == "early"
    with pytest.raises(ConfigError):
        build(imerg={"run_type": ["final", "early"]})


# --- variables -------------------------------------------------------------


def test_unknown_variable_rejected() -> None:
    with pytest.raises(ConfigError, match="unknown era5_land.variables"):
        build(era5_land={"variables": ["rainfall"]})


def test_empty_variable_list_rejected() -> None:
    with pytest.raises(ConfigError, match="must not be empty"):
        build(era5_land={"variables": []})


def test_variable_aliases_accepted() -> None:
    config = build(era5_land={
        "variables": ["soil_moisture", "volumetric_soil_water_layer_1", "tp"]
    })
    assert len(config.era5_land.variables) == 3


# --- outputs and misc ------------------------------------------------------


def test_external_output_path_rejected() -> None:
    with pytest.raises(ConfigError, match="outside the project"):
        build(outputs={"root_dir": "/tmp/reefshield-escape"})


def test_external_output_path_allowed_when_opted_in() -> None:
    config = build(outputs={"root_dir": "/tmp/reefshield-escape",
                            "allow_external_paths": True})
    assert str(config.outputs_dir).startswith("/tmp/")


def test_event_id_must_be_path_safe() -> None:
    for bad in ("has space", "has/slash", ""):
        with pytest.raises(ConfigError):
            build(event_id=bad)


def test_paths_are_namespaced_by_event() -> None:
    config = build()
    for path in (config.imerg_raw_dir, config.era5_raw_dir,
                 config.processed_dir, config.outputs_dir):
        assert path.name == "TEST-EVENT-01"


def test_at_least_one_source_required() -> None:
    payload = copy.deepcopy(BASE)
    payload["imerg"]["enabled"] = False
    payload["era5_land"]["enabled"] = False
    with pytest.raises(ConfigError, match="at least one data source|At least one"):
        EventPipelineConfig(**payload)


def test_unknown_key_rejected() -> None:
    payload = copy.deepcopy(BASE)
    payload["unexpected_section"] = {"a": 1}
    with pytest.raises(Exception):
        EventPipelineConfig(**payload)


def test_missing_file_raises() -> None:
    with pytest.raises(ConfigError, match="not found"):
        load_event_pipeline_config(PROJECT_ROOT / "configs" / "nope.yaml")


def test_plan_contains_no_credentials() -> None:
    plan = build().execution_plan()
    blob = repr(plan).lower()
    for secret in ("password", "token", "authorization", "bearer", "key="):
        assert secret not in blob


def test_plan_estimates_before_download() -> None:
    plan = build().execution_plan()
    assert plan["sources"]["imerg"]["expected_granules"] == 156
    assert plan["sources"]["imerg"]["estimated_harmony_jobs"] == 4
    assert plan["sources"]["era5_land"]["expected_timestamps"] == 49
    assert plan["sources"]["era5_land"]["estimated_cds_requests"] == 3


def test_granule_limit_flagged_in_plan() -> None:
    config = build(imerg={"max_granules": 10})
    assert config.execution_plan()["sources"]["imerg"]["within_limit"] is False
