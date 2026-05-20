from __future__ import annotations

import argparse
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd

import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.cmapss import phm_score, rmse  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate ensembles from C-MAPSS model-zoo prediction CSVs.")
    parser.add_argument("--predictions-dir", default="data/cmapss/model_zoo_predictions")
    parser.add_argument("--models", nargs="+", default=["gru", "tcn", "lstm", "cnn_gru"])
    parser.add_argument("--step", type=float, default=0.05, help="Grid step for non-negative weights that sum to 1.")
    parser.add_argument("--output", default="data/cmapss/cmapss_ensemble_benchmark.csv")
    parser.add_argument("--predictions-output", default="data/cmapss/cmapss_ensemble_predictions.csv")
    args = parser.parse_args()

    prediction_frames = _load_predictions(Path(args.predictions_dir), args.models)
    merged = _merge_predictions(prediction_frames)

    rows: list[dict[str, object]] = []
    for model in args.models:
        rows.extend(_evaluate_prediction_column(merged, model, f"single_{model}"))

    equal_weights = {model: 1.0 / len(args.models) for model in args.models}
    merged["ensemble_equal_all"] = _weighted_prediction(merged, equal_weights)
    rows.extend(_evaluate_prediction_column(merged, "ensemble_equal_all", "ensemble_equal_all"))

    candidate_groups = [
        ("gru", "tcn"),
        ("gru", "lstm"),
        ("gru", "patchtst"),
        ("gru", "tcn", "lstm"),
        ("gru", "tcn", "patchtst"),
    ]
    for pair in candidate_groups:
        if not set(pair).issubset(args.models):
            continue
        weights = {model: 1.0 / len(pair) for model in pair}
        column = "ensemble_equal_" + "_".join(pair)
        merged[column] = _weighted_prediction(merged, weights)
        rows.extend(_evaluate_prediction_column(merged, column, column))

    best_weight_result = _grid_search_weights(merged, args.models, args.step)
    best_column = "ensemble_grid_best"
    merged[best_column] = _weighted_prediction(merged, best_weight_result["weights"])
    rows.extend(_evaluate_prediction_column(merged, best_column, "ensemble_grid_best"))

    best_pair_column = ""
    best_patch_pair_column = ""
    best_patch_trio_column = ""
    best_pair_result = None
    best_patch_pair_result = None
    best_patch_trio_result = None
    if {"gru", "tcn"}.issubset(args.models):
        best_pair_result = _grid_search_weights(merged, ["gru", "tcn"], args.step)
        best_pair_column = "ensemble_grid_gru_tcn"
        merged[best_pair_column] = _weighted_prediction(merged, best_pair_result["weights"])
        rows.extend(_evaluate_prediction_column(merged, best_pair_column, "ensemble_grid_gru_tcn"))
    if {"gru", "patchtst"}.issubset(args.models):
        best_patch_pair_result = _grid_search_weights(merged, ["gru", "patchtst"], args.step)
        best_patch_pair_column = "ensemble_grid_gru_patchtst"
        merged[best_patch_pair_column] = _weighted_prediction(merged, best_patch_pair_result["weights"])
        rows.extend(_evaluate_prediction_column(merged, best_patch_pair_column, "ensemble_grid_gru_patchtst"))
    if {"gru", "tcn", "patchtst"}.issubset(args.models):
        best_patch_trio_result = _grid_search_weights(merged, ["gru", "tcn", "patchtst"], args.step)
        best_patch_trio_column = "ensemble_grid_gru_tcn_patchtst"
        merged[best_patch_trio_column] = _weighted_prediction(merged, best_patch_trio_result["weights"])
        rows.extend(_evaluate_prediction_column(merged, best_patch_trio_column, "ensemble_grid_gru_tcn_patchtst"))

    benchmark = pd.DataFrame(rows)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    benchmark.to_csv(output, index=False, encoding="utf-8-sig")

    prediction_output = Path(args.predictions_output)
    prediction_output.parent.mkdir(parents=True, exist_ok=True)
    final_predictions = merged[
        [
            "subset",
            "unit",
            "last_cycle",
            "actual_rul",
            "actual_rul_capped",
            best_column,
            *([best_pair_column] if best_pair_column else []),
            *([best_patch_pair_column] if best_patch_pair_column else []),
            *([best_patch_trio_column] if best_patch_trio_column else []),
        ]
    ].copy()
    rename_columns = {best_column: "predicted_rul_best_all"}
    if best_pair_column:
        rename_columns[best_pair_column] = "predicted_rul_gru_tcn"
    if best_patch_pair_column:
        rename_columns[best_patch_pair_column] = "predicted_rul_gru_patchtst"
    if best_patch_trio_column:
        rename_columns[best_patch_trio_column] = "predicted_rul_gru_tcn_patchtst"
    final_predictions = final_predictions.rename(columns=rename_columns)
    final_predictions["risk_72h_best_all"] = np.where(final_predictions["predicted_rul_best_all"] <= 72, "HIGH", "LOW")
    for column in ["predicted_rul_gru_tcn", "predicted_rul_gru_patchtst", "predicted_rul_gru_tcn_patchtst"]:
        if column in final_predictions.columns:
            suffix = column.removeprefix("predicted_rul_")
            final_predictions[f"risk_72h_{suffix}"] = np.where(final_predictions[column] <= 72, "HIGH", "LOW")
    final_predictions.to_csv(prediction_output, index=False, encoding="utf-8-sig")

    print("[C-MAPSS ensemble benchmark]")
    print(f"models={','.join(args.models)} rows={len(merged)}")
    print(f"best_all_weights={best_weight_result['weights']} rmse={best_weight_result['rmse']:.3f}")
    if best_pair_result is not None:
        print(f"best_gru_tcn_weights={best_pair_result['weights']} rmse={best_pair_result['rmse']:.3f}")
    if best_patch_pair_result is not None:
        print(f"best_gru_patchtst_weights={best_patch_pair_result['weights']} rmse={best_patch_pair_result['rmse']:.3f}")
    if best_patch_trio_result is not None:
        print(f"best_gru_tcn_patchtst_weights={best_patch_trio_result['weights']} rmse={best_patch_trio_result['rmse']:.3f}")
    print("")
    all_rows = benchmark[benchmark["subset"] == "ALL"].sort_values("test_rmse_capped")
    for _, row in all_rows.iterrows():
        print(
            f"{row['name']:>24} "
            f"rmse={float(row['test_rmse_capped']):.3f} "
            f"phm={float(row['test_phm_score_capped']):.1f} "
            f"high_risk={int(row['high_risk_count'])}/{int(row['test_units'])}"
        )
    print(f"benchmark_csv={output}")
    print(f"predictions_csv={prediction_output}")


def _load_predictions(predictions_dir: Path, models: list[str]) -> dict[str, pd.DataFrame]:
    frames: dict[str, pd.DataFrame] = {}
    for model in models:
        path = predictions_dir / f"{model}_predictions.csv"
        if not path.exists():
            raise FileNotFoundError(f"Missing prediction CSV for {model}: {path}")
        frame = pd.read_csv(path)
        frames[model] = frame.rename(columns={"predicted_rul": model})
    return frames


def _merge_predictions(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    key_columns = ["subset", "unit", "last_cycle", "actual_rul", "actual_rul_capped"]
    merged: pd.DataFrame | None = None
    for model, frame in frames.items():
        selected = frame[key_columns + [model]]
        if merged is None:
            merged = selected
        else:
            merged = merged.merge(selected, on=key_columns, how="inner")
    if merged is None:
        raise ValueError("No prediction frames provided.")
    return merged


def _evaluate_prediction_column(frame: pd.DataFrame, prediction_column: str, name: str) -> list[dict[str, object]]:
    rows = []
    for subset, subset_frame in list(frame.groupby("subset")) + [("ALL", frame)]:
        y_true = subset_frame["actual_rul"].to_numpy(dtype=np.float32)
        y_true_capped = subset_frame["actual_rul_capped"].to_numpy(dtype=np.float32)
        prediction = subset_frame[prediction_column].to_numpy(dtype=np.float32)
        rows.append(
            {
                "name": name,
                "subset": subset,
                "test_units": int(len(subset_frame)),
                "test_rmse_uncapped": rmse(y_true, prediction),
                "test_rmse_capped": rmse(y_true_capped, prediction),
                "test_phm_score_capped": phm_score(y_true_capped, prediction),
                "high_risk_count": int((prediction <= 72).sum()),
            }
        )
    return rows


def _weighted_prediction(frame: pd.DataFrame, weights: dict[str, float]) -> np.ndarray:
    prediction = np.zeros(len(frame), dtype=np.float32)
    for model, weight in weights.items():
        prediction += frame[model].to_numpy(dtype=np.float32) * float(weight)
    return np.clip(prediction, 0, 125)


def _grid_search_weights(frame: pd.DataFrame, models: list[str], step: float) -> dict[str, object]:
    y_true = frame["actual_rul_capped"].to_numpy(dtype=np.float32)
    best = {"rmse": float("inf"), "weights": {models[0]: 1.0}}
    ticks = np.arange(0.0, 1.0 + step / 2.0, step)
    for values in product(ticks, repeat=len(models)):
        total = float(sum(values))
        if abs(total - 1.0) > step / 3.0:
            continue
        weights = {model: float(value) for model, value in zip(models, values)}
        prediction = _weighted_prediction(frame, weights)
        score = rmse(y_true, prediction)
        if score < best["rmse"]:
            best = {"rmse": score, "weights": weights}
    return best


if __name__ == "__main__":
    main()
