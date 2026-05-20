from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.cmapss import (  # noqa: E402
    SENSOR_COLUMNS,
    SETTING_COLUMNS,
    add_train_rul,
    build_sliding_windows,
    load_split,
    load_test_rul,
    phm_score,
    rmse,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Train a fast C-MAPSS RUL demo model and print RUL predictions.")
    parser.add_argument("--data-dir", default="data/cmapss")
    parser.add_argument("--subset", default="FD001", choices=["FD001", "FD002", "FD003", "FD004"])
    parser.add_argument("--window-size", type=int, default=50)
    parser.add_argument("--rul-cap", type=int, default=125)
    parser.add_argument("--max-iter", type=int, default=180)
    parser.add_argument("--output", default="", help="Optional CSV output path for test predictions.")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    feature_columns = [*SETTING_COLUMNS, *SENSOR_COLUMNS]

    train = add_train_rul(load_split(data_dir, subset=args.subset, split="train"), cap=args.rul_cap)
    test = load_split(data_dir, subset=args.subset, split="test")
    test_rul = load_test_rul(data_dir, subset=args.subset)

    windows, labels, window_units = build_sliding_windows(
        train,
        window_size=args.window_size,
        feature_columns=feature_columns,
    )
    features = _window_stats(windows)
    train_mask, val_mask = _unit_holdout_mask(window_units)

    model = HistGradientBoostingRegressor(
        loss="squared_error",
        max_iter=args.max_iter,
        learning_rate=0.06,
        l2_regularization=0.01,
        random_state=42,
    )
    model.fit(features[train_mask], labels[train_mask])

    val_pred = _clip_rul(model.predict(features[val_mask]), args.rul_cap)
    val_true = labels[val_mask]

    test_windows, test_units, last_cycles = _last_test_windows(test, args.window_size, feature_columns)
    test_features = _window_stats(test_windows)
    test_pred = _clip_rul(model.predict(test_features), args.rul_cap)
    test_true = test_rul.to_numpy(dtype=np.float32)[test_units - 1]
    test_true_capped = np.clip(test_true, 0, args.rul_cap)

    prediction_frame = pd.DataFrame(
        {
            "unit": test_units,
            "last_cycle": last_cycles,
            "actual_rul": test_true,
            "actual_rul_capped": test_true_capped,
            "predicted_rul": np.round(test_pred, 1),
            "risk_72h": np.where(test_pred <= 72, "HIGH", "LOW"),
        }
    )
    output = Path(args.output) if args.output else data_dir / f"cmapss_{args.subset.lower()}_rul_predictions.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    prediction_frame.to_csv(output, index=False, encoding="utf-8-sig")

    trajectory = _sample_train_trajectory(train, unit=1)

    print("[C-MAPSS RUL demo]")
    print(f"subset={args.subset} window_size={args.window_size} rul_cap={args.rul_cap}")
    print(f"train_windows={len(labels)} train_units={train['unit'].nunique()} test_units={test['unit'].nunique()}")
    print(f"holdout_units={sorted(set(window_units[val_mask].tolist()))[:10]} total={len(set(window_units[val_mask].tolist()))}")
    print(f"validation_rmse_capped={rmse(val_true, val_pred):.3f}")
    print(f"test_rmse_uncapped={rmse(test_true, test_pred):.3f}")
    print(f"test_rmse_capped={rmse(test_true_capped, test_pred):.3f}")
    print(f"test_phm_score_capped={phm_score(test_true_capped, test_pred):.3f}")
    print(f"predictions_csv={output}")
    print("")
    print("[RUL label trajectory sample: train unit 1]")
    for row in trajectory:
        print(f"unit={row['unit']:>3} cycle={row['cycle']:>3} labeled_rul={row['rul']:>6.1f}")
    print("")
    print("[Final-cycle test predictions]")
    display_frame = prediction_frame.head(15).copy()
    display_frame["actual_rul"] = display_frame["actual_rul"].map("{:.1f}".format)
    display_frame["actual_rul_capped"] = display_frame["actual_rul_capped"].map("{:.1f}".format)
    display_frame["predicted_rul"] = display_frame["predicted_rul"].map("{:.1f}".format)
    print(display_frame.to_string(index=False))


def _window_stats(windows: np.ndarray) -> np.ndarray:
    first = windows[:, 0, :]
    last = windows[:, -1, :]
    mean = windows.mean(axis=1)
    std = windows.std(axis=1)
    minimum = windows.min(axis=1)
    maximum = windows.max(axis=1)
    trend = last - first
    return np.concatenate([last, mean, std, minimum, maximum, trend], axis=1).astype(np.float32)


def _unit_holdout_mask(units: np.ndarray, validation_ratio: float = 0.2) -> tuple[np.ndarray, np.ndarray]:
    unique_units = np.asarray(sorted(set(units.tolist())))
    rng = np.random.default_rng(42)
    shuffled = unique_units.copy()
    rng.shuffle(shuffled)
    val_count = max(1, int(round(len(unique_units) * validation_ratio)))
    validation_units = set(shuffled[:val_count].tolist())
    val_mask = np.asarray([int(unit) in validation_units for unit in units], dtype=bool)
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


def _sample_train_trajectory(frame: pd.DataFrame, unit: int) -> list[dict[str, float]]:
    unit_frame = frame[frame["unit"] == unit].sort_values("cycle")
    checkpoints = sorted({1, 50, 100, int(unit_frame["cycle"].max())})
    rows = unit_frame[unit_frame["cycle"].isin(checkpoints)][["unit", "cycle", "rul"]]
    return rows.to_dict(orient="records")


def _clip_rul(values: np.ndarray, cap: int) -> np.ndarray:
    return np.clip(values.astype(np.float32), 0, cap)


if __name__ == "__main__":
    main()
