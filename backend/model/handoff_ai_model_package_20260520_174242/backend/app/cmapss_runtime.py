from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path

import pandas as pd


PREDICTIONS_FILE = Path("data/cmapss/cmapss_rul_validated_ensemble_predictions.csv")
BENCHMARK_FILE = Path("data/cmapss/cmapss_validated_gru_tcn_patchtst_benchmark.csv")
FALLBACK_GRU_PREDICTIONS_FILE = Path("data/cmapss/cmapss_rul_gru_predictions.csv")
FALLBACK_GRU_BENCHMARK_FILE = Path("data/cmapss/cmapss_rul_gru_benchmark.csv")
FALLBACK_CONDITION_PREDICTIONS_FILE = Path("data/cmapss/cmapss_rul_condition_normalized_predictions.csv")
FALLBACK_CONDITION_BENCHMARK_FILE = Path("data/cmapss/cmapss_rul_condition_normalized_benchmark.csv")
FALLBACK_PREDICTIONS_FILE = Path("data/cmapss/cmapss_rul_combined_predictions.csv")
FALLBACK_BENCHMARK_FILE = Path("data/cmapss/cmapss_rul_benchmark.csv")


@dataclass(frozen=True)
class CMapssRuntimePrediction:
    asset_id: str
    subset: str
    unit: int
    last_cycle: int
    actual_rul: float
    actual_rul_capped: float
    predicted_rul: float
    risk_label: str
    source_path: str


def get_cmapss_prediction_for_asset(asset_id: str) -> CMapssRuntimePrediction | None:
    frame = _load_predictions()
    if frame.empty:
        return None
    selected = _select_demo_rows(frame)
    row = selected.get(asset_id)
    if row is None:
        return None
    return _prediction_from_row(asset_id, row)


def list_cmapss_demo_predictions() -> list[dict[str, object]]:
    frame = _load_predictions()
    if frame.empty:
        return []
    return [
        asdict(_prediction_from_row(asset_id, row))
        for asset_id, row in _select_demo_rows(frame).items()
    ]


def list_cmapss_benchmark_rows() -> list[dict[str, object]]:
    path = (
        _resolve_data_path(BENCHMARK_FILE)
        or _resolve_data_path(FALLBACK_GRU_BENCHMARK_FILE)
        or _resolve_data_path(FALLBACK_CONDITION_BENCHMARK_FILE)
        or _resolve_data_path(FALLBACK_BENCHMARK_FILE)
    )
    if path is None:
        return []
    return pd.read_csv(path).to_dict(orient="records")


def cmapss_risk_percent(predicted_rul: float) -> float:
    if predicted_rul <= 72:
        return round(min(96.0, 65.0 + (72.0 - predicted_rul) / 72.0 * 31.0), 1)
    return round(max(4.0, 65.0 - (predicted_rul - 72.0) / 53.0 * 45.0), 1)


@lru_cache(maxsize=1)
def _load_predictions() -> pd.DataFrame:
    path = (
        _resolve_data_path(PREDICTIONS_FILE)
        or _resolve_data_path(FALLBACK_GRU_PREDICTIONS_FILE)
        or _resolve_data_path(FALLBACK_CONDITION_PREDICTIONS_FILE)
        or _resolve_data_path(FALLBACK_PREDICTIONS_FILE)
    )
    if path is None:
        return pd.DataFrame()
    frame = pd.read_csv(path)
    required = {
        "subset",
        "unit",
        "last_cycle",
        "actual_rul",
        "actual_rul_capped",
        "predicted_rul",
        "risk_72h",
    }
    if not required.issubset(frame.columns):
        return pd.DataFrame()
    return frame


def _select_demo_rows(frame: pd.DataFrame) -> dict[str, pd.Series]:
    targets = {
        "INJ-01": 125.0,
        "INJ-02": 105.0,
        "INJ-03": 68.0,
        "INJ-04": 45.0,
        "INJ-05": 90.0,
        "INJ-06": 115.0,
        "INJ-07": 78.0,
        "INJ-08": 35.0,
    }
    selected: dict[str, pd.Series] = {}
    used_indexes: set[int] = set()
    for asset_id, target_rul in targets.items():
        candidates = frame.loc[~frame.index.isin(used_indexes)].copy()
        candidates["_distance"] = (candidates["predicted_rul"] - target_rul).abs()
        row = candidates.sort_values(["_distance", "subset", "unit"]).iloc[0].drop(labels=["_distance"])
        selected[asset_id] = row
        used_indexes.add(int(row.name))
    return selected


def _prediction_from_row(asset_id: str, row: pd.Series) -> CMapssRuntimePrediction:
    return CMapssRuntimePrediction(
        asset_id=asset_id,
        subset=str(row["subset"]),
        unit=int(row["unit"]),
        last_cycle=int(row["last_cycle"]),
        actual_rul=float(row["actual_rul"]),
        actual_rul_capped=float(row["actual_rul_capped"]),
        predicted_rul=float(row["predicted_rul"]),
        risk_label=str(row["risk_72h"]),
        source_path=str(_resolve_data_path(PREDICTIONS_FILE) or PREDICTIONS_FILE),
    )


def _resolve_data_path(relative_path: Path) -> Path | None:
    project_root = Path(__file__).resolve().parents[2]
    candidates = [
        Path.cwd() / relative_path,
        project_root / relative_path,
        project_root.parent / relative_path,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None
