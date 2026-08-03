"""Tests for Component A.

These cover the invariants that are easy to break in a hurry on Day 9 and
that fail silently when broken - label leakage, split contamination, and
zero-filling missing data.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend/src"))

from models import schema, validation                      # noqa: E402
from models.feature_store import StubFeatureStore          # noqa: E402
from models.predictors import CalibratedGBM, RuleBaseline  # noqa: E402


@pytest.fixture(scope="module")
def matrix():
    df, feats = StubFeatureStore(n_events=90, seed=7).load_training_matrix()
    return df.reset_index(drop=True), feats


# ---------------------------------------------------------------- leakage

@pytest.mark.parametrize("col", ["sro", "ssro", "sro_24h_mm", "ssro_max",
                                 "runoff_label", "label_tier"])
def test_runoff_columns_rejected_as_features(col):
    """The single most important check in the project."""
    with pytest.raises(schema.SchemaError, match="leakage"):
        schema.assert_no_label_leakage(["rain_3h_mm", col])


def test_clean_feature_list_passes():
    schema.assert_no_label_leakage(["rain_3h_mm", "soil_moisture_t24h", "area_km2"])


def test_stub_matrix_has_no_leaking_features(matrix):
    df, feats = matrix
    schema.assert_no_label_leakage(feats)
    assert "runoff_label" not in feats


# ---------------------------------------------------------------- schema

def test_bad_catchment_id_rejected(matrix):
    df, _ = matrix
    bad = df.copy()
    bad.loc[0, "catchment_id"] = "AQC1"
    with pytest.raises(schema.SchemaError, match="AQ-C"):
        schema.validate(bad)


def test_non_binary_label_rejected(matrix):
    df, _ = matrix
    bad = df.copy()
    bad.loc[0, "runoff_label"] = 2
    with pytest.raises(schema.SchemaError, match="binary"):
        schema.validate(bad)


def test_null_label_rejected(matrix):
    df, _ = matrix
    bad = df.copy()
    bad.loc[0, "runoff_label"] = np.nan
    with pytest.raises(schema.SchemaError, match="null"):
        schema.validate(bad)


def test_missing_required_column_rejected(matrix):
    df, _ = matrix
    with pytest.raises(schema.SchemaError, match="missing required"):
        schema.validate(df.drop(columns=["rain_3h_mm"]))


# ---------------------------------------------------------------- splits

def test_loco_never_shares_a_catchment_between_train_and_test(matrix):
    df, feats = matrix
    for c in df.catchment_id.unique():
        tr = df.index[df.catchment_id != c]
        te = df.index[df.catchment_id == c]
        assert set(df.loc[tr, "catchment_id"]).isdisjoint({c})
        assert set(df.loc[te, "catchment_id"]) == {c}
        assert len(tr) + len(te) == len(df)


def test_loco_produces_one_fold_per_catchment(matrix):
    df, feats = matrix
    rep = validation.leave_one_catchment_out(RuleBaseline, df, feats)
    assert len(rep.folds) == df.catchment_id.nunique()
    assert {f.fold for f in rep.folds} == set(df.catchment_id.unique())


def test_temporal_split_is_strictly_ordered(matrix):
    df, feats = matrix
    yr = pd.to_datetime(df.event_time_utc, utc=True).dt.year
    tr, te = df.index[yr < 2015], df.index[yr >= 2015]
    assert yr.loc[tr].max() < 2015 <= yr.loc[te].min()


def test_fold_with_too_few_positives_is_flagged():
    f = validation.FoldResult("x", 100, 20, 2, 0.9, 0.9, 0.05, 0.1)
    assert not f.trustworthy
    assert validation.FoldResult("x", 100, 20, 9, 0.9, 0.9, 0.05, 0.1).trustworthy


def test_pooled_ignores_untrustworthy_folds():
    rep = validation.Report("m", "loco", folds=[
        validation.FoldResult("a", 100, 20, 1, 1.0, 1.0, 0.0, 0.05),
        validation.FoldResult("b", 100, 20, 10, 0.5, 0.5, 0.10, 0.50),
    ])
    assert rep.pooled()["n_folds"] == 1
    assert rep.pooled()["ap"] == 0.5


# ---------------------------------------------------------------- predictors

def test_both_predictors_share_the_interface(matrix):
    df, feats = matrix
    y = df.runoff_label.to_numpy()
    for cls in (RuleBaseline, CalibratedGBM):
        p = cls().fit(df[feats], y).predict_proba(df[feats])
        assert p.shape == (len(df),)
        assert np.all((p >= 0) & (p <= 1)), f"{cls.name} left [0,1]"


def test_baseline_needs_no_training_data_to_be_deterministic(matrix):
    df, feats = matrix
    y = df.runoff_label.to_numpy()
    a = RuleBaseline().fit(df[feats], y).predict_proba(df[feats])
    b = RuleBaseline().fit(df[feats], y).predict_proba(df[feats])
    np.testing.assert_array_equal(a, b)


def test_baseline_runoff_rises_with_rainfall(matrix):
    """The formula must be monotone in P or it is not a curve number."""
    df, feats = matrix
    base = df[feats].iloc[[0]].copy()
    depths = []
    for p in (5, 25, 60, 120):
        row = base.copy()
        row["rain_24h_mm"] = p
        depths.append(RuleBaseline().runoff_depth(row)[0])
    assert depths == sorted(depths)


def test_gbm_reports_whether_it_calibrated(matrix):
    df, feats = matrix
    m = CalibratedGBM().fit(df[feats], df.runoff_label.to_numpy())
    assert isinstance(m.is_calibrated, bool)


# ---------------------------------------------------------------- data rules

def test_missing_values_are_carried_not_filled(matrix):
    """Phase 1 rule 1: missing is never zero."""
    df, _ = matrix
    assert df.soil_moisture_t72h.isna().any(), "stub should contain honest gaps"
    assert (df.loc[df.soil_moisture_t72h.isna(), "quality_flag"]
            == "PARTIAL_WINDOW").all()


def test_gbm_trains_with_missing_values_present(matrix):
    df, feats = matrix
    assert df[feats].isna().any().any()
    p = CalibratedGBM().fit(df[feats], df.runoff_label.to_numpy()).predict_proba(df[feats])
    assert np.isfinite(p).all()


def test_stub_is_labelled_synthetic(matrix):
    """A synthetic row must never be mistakable for data."""
    df, _ = matrix
    assert df.label_basis.str.contains("SYNTHETIC").all()


# ══════════════════════════════════════════ Component D · sediment proxy

from models.sediment_proxy import (  # noqa: E402
    ANCHOR_MASS_T, CLASSES, TAU_DEFAULT, TAU_NEGEV, SedimentParams,
    SedimentProxy, erodibility)


@pytest.fixture(scope="module")
def sediment_inputs(matrix):
    df, feats = matrix
    q = RuleBaseline().fit(df[feats], df.runoff_label.to_numpy()).runoff_depth(df[feats])
    return df, feats, q


def test_default_tau_sits_inside_the_negev_range():
    """The default must be defensible, not arbitrary."""
    assert TAU_NEGEV[0] <= TAU_DEFAULT <= TAU_NEGEV[1]
    assert SedimentParams().tau_in_negev_range


def test_tau_outside_zero_one_is_rejected():
    for bad in (-0.1, 1.0, 1.5):
        with pytest.raises(ValueError, match="transmission_loss"):
            SedimentParams(transmission_loss=bad).validate()


def test_tau_enters_linearly(sediment_inputs):
    """(1 - tau) is a plain factor; the scenario slider depends on it."""
    df, feats, q = sediment_inputs
    base = SedimentProxy(SedimentParams(transmission_loss=0.0)).index(df[feats], q)
    half = SedimentProxy(SedimentParams(transmission_loss=0.5)).index(df[feats], q)
    np.testing.assert_allclose(half, base * 0.5, rtol=1e-9)


def test_zero_tau_is_the_optimistic_extreme(sediment_inputs):
    """tau = 0 was the old implicit assumption. It must be the maximum."""
    df, feats, q = sediment_inputs
    idx0 = SedimentProxy(SedimentParams(transmission_loss=0.0)).index(df[feats], q)
    for t in (0.2, 0.525, 0.85):
        assert SedimentProxy(SedimentParams(transmission_loss=t)).index(
            df[feats], q).sum() < idx0.sum()


def test_index_rises_with_runoff_bare_slope_and_density(sediment_inputs):
    """Each term must move the index the direction the physics says."""
    df, feats, q = sediment_inputs
    sp = SedimentProxy()
    row = df[feats].iloc[[0]].copy()
    base = sp.index(row, [10.0])[0]
    assert sp.index(row, [20.0])[0] > base                      # more runoff
    for col, bump in [("bare_fraction", 0.15), ("slope_mean_deg", 6.0),
                      ("drainage_density_km_km2", 0.4)]:
        up = row.copy()
        up[col] = up[col] + bump
        assert sp.index(up, [10.0])[0] > base, f"{col} did not raise the index"


def test_clay_reduces_erodibility_and_organic_carbon_too():
    e_low_clay = erodibility([10.0], [58.0], [32.0], [3.0])[0]
    e_high_clay = erodibility([45.0], [58.0], [32.0], [3.0])[0]
    assert e_high_clay < e_low_clay
    assert erodibility([21.0], [58.0], [21.0], [40.0])[0] < \
           erodibility([21.0], [58.0], [21.0], [1.0])[0]


def test_mass_requires_anchoring(sediment_inputs):
    """A mass without the anchor is a number nobody can defend."""
    df, feats, q = sediment_inputs
    sp = SedimentProxy()
    assert not sp.is_anchored
    with pytest.raises(RuntimeError, match="not anchored"):
        sp.mass_estimate_t(df[feats], q)


def test_anchoring_reproduces_the_published_mass(sediment_inputs):
    df, feats, q = sediment_inputs
    sp = SedimentProxy()
    one = df[feats].iloc[[0]]
    idx = float(sp.index(one, [q[0]])[0])
    sp.calibrate_to_anchor(idx)
    assert sp.is_anchored
    np.testing.assert_allclose(sp.mass_estimate_t(one, [q[0]])[0], ANCHOR_MASS_T, rtol=1e-6)


def test_unanchored_classification_declares_itself_relative(sediment_inputs):
    """A within-dataset class is a different claim and must say so."""
    df, feats, q = sediment_inputs
    out = SedimentProxy().classify(df[feats], q)
    assert "QUANTILES" in out.class_basis.iloc[0]
    assert set(out.sediment_class) <= set(CLASSES)


def test_anchored_classification_names_the_anchor(sediment_inputs):
    df, feats, q = sediment_inputs
    sp = SedimentProxy().calibrate_to_anchor(1.0e8)
    out = sp.classify(df[feats], q)
    assert "AQ-2016-10-28" in out.class_basis.iloc[0]


def test_classify_records_the_tau_used(sediment_inputs):
    """The assumption travels with every row, not just the docs."""
    df, feats, q = sediment_inputs
    out = SedimentProxy(SedimentParams(transmission_loss=0.7)).classify(df[feats], q)
    assert (out.transmission_loss == 0.7).all()


def test_scenario_does_not_mutate_the_original(sediment_inputs):
    df, feats, q = sediment_inputs
    sp = SedimentProxy()
    scenario = sp.with_transmission_loss(0.9)
    assert sp.params.transmission_loss == TAU_DEFAULT
    assert scenario.params.transmission_loss == 0.9


def test_sensitivity_table_spans_and_flags_the_negev_range(sediment_inputs):
    df, feats, q = sediment_inputs
    t = SedimentProxy().sensitivity_to_tau(df[feats], q)
    assert t.transmission_loss.min() == 0.0
    assert t.is_default.sum() == 1
    assert t.in_negev_range.any() and not t.in_negev_range.all()
    assert t.mean_index.is_monotonic_decreasing
