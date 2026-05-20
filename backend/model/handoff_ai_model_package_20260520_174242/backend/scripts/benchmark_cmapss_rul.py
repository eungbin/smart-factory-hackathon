from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.cmapss import (  # noqa: E402
    SENSOR_COLUMNS,
    SETTING_COLUMNS,
    SUBSETS,
    add_train_rul,
    build_sliding_windows,
    load_split,
    load_test_rul,
    phm_score,
    rmse,
)


@dataclass(frozen=True)
class PreparedSubset:
    subset: str
    train_features: np.ndarray
    train_labels: np.ndarray
    train_unit_keys: np.ndarray
    test_features: np.ndarray
    test_true: np.ndarray
    test_true_capped: np.ndarray
    test_units: np.ndarray
    test_last_cycles: np.ndarray


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark C-MAPSS RUL models across FD001-FD004.")
    parser.add_argument("--data-dir", default="data/cmapss")
    parser.add_argument("--subsets", nargs="+", default=list(SUBSETS), choices=list(SUBSETS))
    parser.add_argument("--window-size", type=int, default=50)
    parser.add_argument("--rul-cap", type=int, default=125)
    parser.add_argument("--max-iter", type=int, default=180)
    parser.add_argument("--output", default="data/cmapss/cmapss_rul_benchmark.csv")
    parser.add_argument("--predictions-output", default="data/cmapss/cmapss_rul_combined_predictions.csv")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    prepared = [
        _prepare_subset(data_dir, subset, args.window_size, args.rul_cap)
        for subset in args.subsets
    ]

    rows: list[dict[str, object]] = []
    print("[C-MAPSS RUL benchmark]")
    print(f"subsets={','.join(args.subsets)} window_size={args.window_size} rul_cap={args.rul_cap}")
    print("")

    for item in prepared:
        result = _fit_and_evaluate_individual(item, args.max_iter, args.rul_cap)
        rows.append(result)
        print(_format_result(result))

    combined_rows, combined_predictions = _fit_and_evaluate_combined(prepared, args.max_iter, args.rul_cap)
    rows.extend(combined_rows)
    for result in combined_rows:
        print(_format_result(result))

    benchmark = pd.DataFrame(rows)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    benchmark.to_csv(output, index=False, encoding="utf-8-sig")

    predictions_output = Path(args.predictions_output)
    predictions_output.parent.mkdir(parents=True, exist_ok=True)
    combined_predictions.to_csv(predictions_output, index=False, encoding="utf-8-sig")

    print("")
    print(f"benchmark_csv={output}")
    print(f"combined_predictions_csv={predictions_output}")


def _prepare_subset(data_dir: Path, subset: str, window_size: int, rul_cap: int) -> PreparedSubset:
    feature_columns = [*SETTING_COLUMNS, *SENSOR_COLUMNS]
    subset_id = SUBSETS.index(subset)

    train = add_train_rul(load_split(data_dir, subset=subset, split="train"), cap=rul_cap)
    train_windows, train_labels, train_units = build_sliding_windows(
        train,
        window_size=window_size,
        feature_columns=feature_columns,
    )
    train_features = _with_subset_features(_window_stats(train_windows), subset_id)
    train_unit_keys = np.asarray([_unit_key(subset_id, int(unit)) for unit in train_units], dtype=np.int32)

    test = load_split(data_dir, subset=subset, split="test")
    test_rul = load_test_rul(data_dir, subset=subset)
    test_windows, test_units, test_last_cycles = _last_test_windows(test, window_size, feature_columns)
    test_features = _with_subset_features(_window_stats(test_windows), subset_id)
    test_true = test_rul.to_numpy(dtype=np.float32)[test_units - 1]
    test_true_capped = np.clip(test_true, 0, rul_cap)

    return PreparedSubset(
        subset=subset,
        train_features=train_features,
        train_labels=train_labels,
        train_unit_keys=train_unit_keys,
        test_features=test_features,
        test_true=test_true,
        test_true_capped=test_true_capped,
        test_units=test_units,
        test_last_cycles=test_last_cycles,
    )


def _fit_and_evaluate_individual(item: PreparedSubset, max_iter: int, rul_cap: int) -> dict[str, object]:
    train_mask, val_mask = _unit_holdout_mask(item.train_unit_keys)
    model = _make_model(max_iter)
    model.fit(item.train_features[train_mask], item.train_labels[train_mask])
    val_pred = _clip_rul(model.predict(item.train_features[val_mask]), rul_cap)
    test_pred = _clip_rul(model.predict(item.test_features), rul_cap)
    return _metric_row(
        model_type="individual",
        subset=item.subset,
        train_windows=int(train_mask.sum()),
        validation_windows=int(val_mask.sum()),
        test_units=len(item.test_units),
        val_true=item.train_labels[val_mask],
        val_pred=val_pred,
        test_true=item.test_true,
        test_true_capped=item.test_true_capped,
        test_pred=test_pred,
    )


def _fit_and_evaluate_combined(
    prepared: list[PreparedSubset],
    max_iter: int,
    rul_cap: int,
) -> tuple[list[dict[str, object]], pd.DataFrame]:
    features = np.concatenate([item.train_features for item in prepared], axis=0)
    labels = np.concatenate([item.train_labels for item in prepared], axis=0)
    unit_keys = np.concatenate([item.train_unit_keys for item in prepared], axis=0)
    train_mask, val_mask = _unit_holdout_mask(unit_keys)
    model = _make_model(max_iter)
    model.fit(features[train_mask], labels[train_mask])

    rows: list[dict[str, object]] = []
    prediction_frames: list[pd.DataFrame] = []
    for item in prepared:
        val_subset_mask = val_mask & np.isin(unit_keys, np.unique(item.train_unit_keys))
        val_pred = _clip_rul(model.predict(features[val_subset_mask]), rul_cap)
        test_pred = _clip_rul(model.predict(item.test_features), rul_cap)
        rows.append(
            _metric_row(
                model_type="combined",
                subset=item.subset,
                train_windows=int(train_mask.sum()),
                validation_windows=int(val_subset_mask.sum()),
                test_units=len(item.test_units),
                val_true=labels[val_subset_mask],
                val_pred=val_pred,
                test_true=item.test_true,
                test_true_capped=item.test_true_capped,
                test_pred=test_pred,
            )
        )
        prediction_frames.append(
            pd.DataFrame(
                {
                    "subset": item.subset,
                    "unit": item.test_units,
                    "last_cycle": item.test_last_cycles,
                    "actual_rul": item.test_true,
                    "actual_rul_capped": item.test_true_capped,
                    "predicted_rul": np.round(test_pred, 1),
                    "risk_72h": np.where(test_pred <= 72, "HIGH", "LOW"),
                }
            )
        )

    test_true = np.concatenate([item.test_true for item in prepared])
    test_true_capped = np.concatenate([item.test_true_capped for item in prepared])
    test_pred = np.concatenate([
        _clip_rul(model.predict(item.test_features), rul_cap)
        for item in prepared
    ])
    val_pred = _clip_rul(model.predict(features[val_mask]), rul_cap)
    rows.append(
        _metric_row(
            model_type="combined",
            subset="ALL",
            train_windows=int(train_mask.sum()),
            validation_windows=int(val_mask.sum()),
            test_units=sum(len(item.test_units) for item in prepared),
            val_true=labels[val_mask],
            val_pred=val_pred,
            test_true=test_true,
            test_true_capped=test_true_capped,
            test_pred=test_pred,
        )
    )
    return rows, pd.concat(prediction_frames, ignore_index=True)


def _metric_row(
    model_type: str,
    subset: str,
    train_windows: int,
    validation_windows: int,
    test_units: int,
    val_true: np.ndarray,
    val_pred: np.ndarray,
    test_true: np.ndarray,
    test_true_capped: np.ndarray,
    test_pred: np.ndarray,
) -> dict[str, object]:
    return {
        "model_type": model_type,
        "subset": subset,
        "train_windows": train_windows,
        "validation_windows": validation_windows,
        "test_units": test_units,
        "validation_rmse_capped": rmse(val_true, val_pred),
        "test_rmse_uncapped": rmse(test_true, test_pred),
        "test_rmse_capped": rmse(test_true_capped, test_pred),
        "test_phm_score_capped": phm_score(test_true_capped, test_pred),
        "high_risk_count": int((test_pred <= 72).sum()),
    }


def _format_result(row: dict[str, object]) -> str:
    return (
        f"{row['model_type']:>10} {row['subset']:>5} "
        f"val_rmse={float(row['validation_rmse_capped']):>7.3f} "
        f"test_rmse={float(row['test_rmse_capped']):>7.3f} "
        f"phm={float(row['test_phm_score_capped']):>10.1f} "
        f"high_risk={int(row['high_risk_count']):>3}/{int(row['test_units'])}"
    )


def _make_model(max_iter: int) -> HistGradientBoostingRegressor:
    return HistGradientBoostingRegressor(
        loss="squared_error",
        max_iter=max_iter,
        learning_rate=0.06,
        l2_regularization=0.01,
        random_state=42,
    )


def _window_stats(windows: np.ndarray) -> np.ndarray:
    first = windows[:, 0, :]
    last = windows[:, -1, :]
    mean = windows.mean(axis=1)
    std = windows.std(axis=1)
    minimum = windows.min(axis=1)
    maximum = windows.max(axis=1)
    trend = last - first
    return np.concatenate([last, mean, std, minimum, maximum, trend], axis=1).astype(np.float32)


def _with_subset_features(features: np.ndarray, subset_id: int) -> np.ndarray:
    one_hot = np.zeros((features.shape[0], len(SUBSETS)), dtype=np.float32)
    one_hot[:, subset_id] = 1.0
    return np.concatenate([features, one_hot], axis=1).astype(np.float32)


def _unit_holdout_mask(unit_keys: np.ndarray, validation_ratio: float = 0.2) -> tuple[np.ndarray, np.ndarray]:
    unique_units = np.asarray(sorted(set(unit_keys.tolist())))
    rng = np.random.default_rng(42)
    shuffled = unique_units.copy()
    rng.shuffle(shuffled)
    val_count = max(1, int(round(len(unique_units) * validation_ratio)))
    validation_units = set(shuffled[:val_count].tolist())
    val_mask = np.asarray([int(unit) in validation_units for unit in unit_keys], dtype=bool)
    return ~val_mask, val_mask


def _last_test_windows(
    frame: pd.DataFrame,
    window_size: int,
    feature_columns: list[str],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    windows: list[np.ndarray] = []
    units: list[int] = []
    last_cycles: list[int] = []
    for unit, unit_frame in frame.groupby("unit"):
        unit_frame = unit_frame.sort_values("cycle")
        values = unit_frame[feature_columns].to_numpy(dtype=np.float32)
        if len(values) < window_size:
            pad = np.repeat(values[:1], window_size - len(values), axis=0)
            values = np.vstack([pad, values])
        windows.append(values[-window_size:])
        units.append(int(unit))
        last_cycles.append(int(unit_frame["cycle"].iloc[-1]))
    return (
        np.stack(windows).astype(np.float32),
        np.asarray(units, dtype=np.int32),
        np.asarray(last_cycles, dtype=np.int32),
    )


def _unit_key(subset_id: int, unit: int) -> int:
    return (subset_id + 1) * 1000 + unit


def _clip_rul(values: np.ndarray, cap: int) -> np.ndarray:
    return np.clip(values.astype(np.float32), 0, cap)


if __name__ == "__main__":
    main()
