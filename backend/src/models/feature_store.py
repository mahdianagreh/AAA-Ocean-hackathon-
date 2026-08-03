"""Where the training matrix comes from.

The database does not exist yet, and the model must not care. One interface,
three implementations, chosen by REEFSHIELD_FEATURE_SOURCE:

    stub      synthetic, so the harness can be built and tested today
    parquet   Karam's file, once it lands
    supabase  the same contract against Postgres, later

Swapping the source is a config change. The model code never learns which
one it got, and schema validation happens once, here, for all three.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from pathlib import Path

import numpy as np
import pandas as pd

from . import schema

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PARQUET = ROOT / "data/processed/features/event_catchment_features.parquet"

# The five real catchments. Static values are the published figures from
# data/processed/features/catchment_terrain.parquet - the stub is synthetic
# in its rainfall, not in its geography.
REAL_CATCHMENTS = {
    "AQ-C01": dict(area_km2=4453.08, relief_m=1841.1, slope_mean_deg=10.81,
                   slope_max_deg=75.04, drainage_density_km_km2=0.809,
                   dist_to_coast_max_km=90.71, dist_to_coast_mean_km=48.64,
                   elongation_ratio=0.830, accum_mean_cells=2496.2,
                   accum_p95_cells=210.0),
    "AQ-C02": dict(area_km2=64.85, relief_m=1321.1, slope_mean_deg=16.60,
                   slope_max_deg=51.40, drainage_density_km_km2=0.708,
                   dist_to_coast_max_km=14.52, dist_to_coast_mean_km=9.20,
                   elongation_ratio=0.626, accum_mean_cells=336.7,
                   accum_p95_cells=203.0),
    "AQ-C03": dict(area_km2=59.90, relief_m=1418.4, slope_mean_deg=16.65,
                   slope_max_deg=49.73, drainage_density_km_km2=0.744,
                   dist_to_coast_max_km=17.09, dist_to_coast_mean_km=11.54,
                   elongation_ratio=0.511, accum_mean_cells=411.4,
                   accum_p95_cells=168.0),
    "AQ-C04": dict(area_km2=42.67, relief_m=995.5, slope_mean_deg=8.25,
                   slope_max_deg=41.26, drainage_density_km_km2=1.010,
                   dist_to_coast_max_km=12.22, dist_to_coast_mean_km=6.44,
                   elongation_ratio=0.603, accum_mean_cells=216.1,
                   accum_p95_cells=348.0),
    "AQ-C05": dict(area_km2=35.64, relief_m=1014.9, slope_mean_deg=6.82,
                   slope_max_deg=38.41, drainage_density_km_km2=1.292,
                   dist_to_coast_max_km=13.71, dist_to_coast_mean_km=8.33,
                   elongation_ratio=0.491, accum_mean_cells=253.7,
                   accum_p95_cells=508.0),
}


class FeatureStore(ABC):
    """One method. Everything downstream depends on nothing more."""

    #: True only for sources that fabricate their rows. Callers branch on this
    #: to decide where output may be written - never on string-matching
    #: provenance, which is a description and not a guarantee.
    is_synthetic: bool = False

    @abstractmethod
    def _read(self) -> pd.DataFrame: ...

    @property
    @abstractmethod
    def provenance(self) -> str:
        """Recorded in the model card and the model_versions row."""

    def load_training_matrix(self, include_static: bool = True):
        df = self._read()
        feats = schema.validate(df, include_static)
        return df, feats


class ParquetFeatureStore(FeatureStore):
    def __init__(self, path: Path | str = DEFAULT_PARQUET):
        self.path = Path(path)

    def _read(self) -> pd.DataFrame:
        if not self.path.exists():
            raise FileNotFoundError(
                f"{self.path} does not exist yet. Karam delivers it; until then "
                "run with REEFSHIELD_FEATURE_SOURCE=stub."
            )
        return pd.read_parquet(self.path)

    @property
    def provenance(self) -> str:
        return f"parquet:{self.path.name}"


class SupabaseFeatureStore(FeatureStore):
    """Same contract, Postgres behind it. Not wired until the schema is live."""

    QUERY = """
        select *
        from   event_catchment_features
        where  runoff_label is not null
    """

    def __init__(self, dsn: str | None = None):
        self.dsn = dsn or os.environ.get("SUPABASE_DSN")

    def _read(self) -> pd.DataFrame:
        if not self.dsn:
            raise RuntimeError("SUPABASE_DSN is not set")
        raise NotImplementedError(
            "Supabase schema is not live yet (Nizar, Phase 2 workstream 3). "
            "The query and the contract are settled; only the connection is "
            "missing. Nothing else in the model layer changes when it lands."
        )

    @property
    def provenance(self) -> str:
        return "supabase:event_catchment_features"


class StubFeatureStore(FeatureStore):
    """Synthetic matrix with the real geography and a known generating rule.

    Exists so the harness, the baseline and the metrics can be built and
    tested before the real matrix arrives - the task file is explicit that a
    model trained on 40 events on Day 5 beats one that starts on Day 8.

    The generating rule is deliberately simple and nonlinear: runoff needs
    intense rain AND dry antecedent soil, amplified by slope and bare ground.
    A model that cannot recover a rule we wrote ourselves is broken, so this
    doubles as a test of the harness rather than of hydrology.

    IT IS NOT DATA. Every result from it is labelled synthetic, it can only be
    selected by asking for it by name, and nothing it produces may be written
    to a path that serving or the pitch reads.
    """

    is_synthetic = True

    def __init__(self, n_events: int = 220, seed: int = 20260803,
                 positive_rate: float = 0.12):
        self.n_events = n_events
        self.seed = seed
        self.positive_rate = positive_rate

    def _read(self) -> pd.DataFrame:
        rng = np.random.default_rng(self.seed)
        rows = []
        # events span 2000-2024 so the temporal holdout has both sides
        years = rng.integers(2000, 2025, self.n_events)
        months = rng.choice([1, 2, 3, 10, 11, 12], self.n_events)  # wet season
        days = rng.integers(1, 29, self.n_events)

        for i in range(self.n_events):
            eid = f"SYN-{years[i]}-{months[i]:02d}-{days[i]:02d}-{i:03d}"
            ts = pd.Timestamp(int(years[i]), int(months[i]), int(days[i]), tz="UTC")
            # storm severity shared across catchments in one event, plus
            # per-catchment variation - rain is spatially correlated
            storm = rng.gamma(1.6, 9.0)
            for cid, static in REAL_CATCHMENTS.items():
                r3 = max(0.4, storm * rng.uniform(0.55, 1.45))
                r1 = r3 * rng.uniform(0.35, 0.75)
                r6 = r3 * rng.uniform(1.0, 1.35)
                r24 = r6 * rng.uniform(1.0, 1.30)
                sm = float(np.clip(rng.beta(2, 6) * 0.45, 0.02, 0.42))
                rows.append({
                    "event_id": eid,
                    "catchment_id": cid,
                    "event_time_utc": ts,
                    "rain_1h_mm": round(r1, 2),
                    "rain_3h_mm": round(r3, 2),
                    "rain_6h_mm": round(r6, 2),
                    "rain_24h_mm": round(r24, 2),
                    "rain_3h_percentile": round(float(np.clip(
                        100 * (1 - np.exp(-r3 / 18)), 1, 99.99)), 2),
                    "anomaly_score": round(float((r3 - 14) / 9), 3),
                    "soil_moisture_t24h": round(sm, 4),
                    "soil_moisture_t72h": round(max(0.01, sm * rng.uniform(.7, 1.1)), 4),
                    "precip_prior_72h_mm": round(float(rng.exponential(1.4)), 2),
                    "precip_prior_7d_mm": round(float(rng.exponential(3.2)), 2),
                    "wind_speed_ms": round(float(rng.normal(5.2, 1.8)), 2),
                    "temp_2m_c": round(float(rng.normal(22, 5)), 1),
                    "bare_fraction": round(float(np.clip(
                        rng.normal(0.74, 0.05), 0.5, 0.95)), 3),
                    "built_up_fraction": round(float(np.clip(
                        rng.normal(0.06, 0.03), 0, 0.3)), 3),
                    "clay_pct": round(float(rng.normal(21, 3)), 1),
                    "sand_pct": round(float(rng.normal(58, 5)), 1),
                    "silt_pct": round(float(rng.normal(21, 3)), 1),
                    "soc_g_kg": round(float(abs(rng.normal(3.1, 1.0))), 2),
                    "road_density_km_km2": round(float(abs(rng.normal(0.4, 0.25))), 3),
                    **static,
                })

        df = pd.DataFrame(rows)

        # generating rule: intense rain on DRY soil, amplified by slope and
        # bare ground. Dryness raising runoff is real - a crusted arid surface
        # sheds water - and it is the interaction a linear model cannot see.
        dryness = 1.0 - (df.soil_moisture_t24h / 0.45)
        drive = (
            0.115 * df.rain_3h_mm
            + 0.030 * df.rain_3h_mm * dryness
            + 0.055 * df.slope_mean_deg
            + 1.4 * df.bare_fraction
            + 0.55 * df.drainage_density_km_km2
        )
        noise = rng.normal(0, 0.85, len(df))
        score = drive + noise
        cutoff = np.quantile(score, 1 - self.positive_rate)
        df["runoff_label"] = (score > cutoff).astype(int)
        df["label_tier"] = "silver"
        df["label_basis"] = (
            "SYNTHETIC. Generated by a known rule for harness testing; "
            "carries no hydrological meaning."
        )

        # a few honestly-missing values - the pipeline must carry NaN through
        # rather than zero-fill, per Phase 1 rule 1
        gaps = rng.choice(len(df), size=max(1, len(df) // 40), replace=False)
        df.loc[gaps, "soil_moisture_t72h"] = np.nan
        df.loc[gaps, "quality_flag"] = "PARTIAL_WINDOW"
        df["quality_flag"] = df.get("quality_flag", pd.Series(index=df.index)).fillna("OK")
        return df

    @property
    def provenance(self) -> str:
        return f"stub:synthetic(seed={self.seed},n={self.n_events})"


def get_feature_store(source: str | None = None) -> FeatureStore:
    """Resolve a feature source. Synthetic is never chosen implicitly.

    `auto` used to fall back to the stub when the real matrix was absent, which
    meant running the trainer before Karam delivered produced a synthetic model
    and no error. A model trained on fabricated rows is worse than no model,
    because it looks exactly like one that works. So auto now resolves to the
    real matrix or fails, and the stub has to be asked for by name.
    """
    source = (source or os.environ.get("REEFSHIELD_FEATURE_SOURCE") or "auto").lower()
    if source == "auto":
        if not DEFAULT_PARQUET.exists():
            raise FileNotFoundError(
                f"The real feature matrix is not here yet:\n"
                f"  {DEFAULT_PARQUET}\n\n"
                "Karam delivers it (Phase 2, rainfall stream). Until then there is\n"
                "nothing legitimate to train on, and auto will not substitute\n"
                "synthetic rows for it.\n\n"
                "To exercise the harness deliberately:\n"
                "    REEFSHIELD_FEATURE_SOURCE=stub  or  --source stub\n"
                "Synthetic runs cannot write docs/model_card.md or a servable\n"
                "artifact - see scripts/11_train_runoff_model.py."
            )
        source = "parquet"
    if source == "parquet":
        return ParquetFeatureStore()
    if source == "supabase":
        return SupabaseFeatureStore()
    if source == "stub":
        return StubFeatureStore()
    raise ValueError(f"unknown feature source {source!r}")
