from __future__ import annotations

import argparse
import random
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.cmapss import (  # noqa: E402
    SUBSETS,
    add_train_rul,
    build_sliding_windows,
    load_split,
    load_test_rul,
    phm_score,
    rmse,
)
from app.cmapss_conditioning import (  # noqa: E402
    condition_feature_columns,
    fit_condition_normalizer,
    transform_with_condition_normalization,
)
from app.ml_model import GRURULRegressor  # noqa: E402


@dataclass(frozen=True)
class PreparedSubset:
    subset: str
    train_windows: np.ndarray
    train_labels: np.ndarray
    train_unit_keys: np.ndarray
    test_windows: np.ndarray
    test_true: np.ndarray
    test_true_capped: np.ndarray
    test_units: np.ndarray
    test_last_cycles: np.ndarray


def main() -> None:
    parser = argparse.ArgumentParser(description="Train/evaluate a GRU sequence RUL model on condition-normalized C-MAPSS.")
    parser.add_argument("--data-dir", default="data/cmapss")
    parser.add_argument("--subsets", nargs="+", default=list(SUBSETS), choices=list(SUBSETS))
    parser.add_argument("--window-size", type=int, default=50)
    parser.add_argument("--rul-cap", type=int, default=125)
    parser.add_argument("--epochs", type=int, default=6)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--hidden-size", type=int, default=64)
    parser.add_argument("--layers", type=int, default=1)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--output", default="data/cmapss/cmapss_rul_gru_benchmark.csv")
    parser.add_argument("--predictions-output", default="data/cmapss/cmapss_rul_gru_predictions.csv")
    parser.add_argument("--model-output", default="data/models/cmapss_condition_normalized_gru.pt")
    args = parser.parse_args()

    _seed_everything(42)
    data_dir = Path(args.data_dir)
    prepared = [_prepare_subset(data_dir, subset, args.window_size, args.rul_cap) for subset in args.subsets]

    train_windows = np.concatenate([item.train_windows for item in prepared], axis=0)
    train_labels = np.concatenate([item.train_labels for item in prepared], axis=0)
    unit_keys = np.concatenate([item.train_unit_keys for item in prepared], axis=0)
    train_mask, val_mask = _unit_holdout_mask(unit_keys)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = GRURULRegressor(
        input_size=train_windows.shape[-1],
        hidden_size=args.hidden_size,
        layers=args.layers,
    ).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=1e-4)
    loss_fn = nn.MSELoss()

    train_dataset = TensorDataset(
        torch.tensor(train_windows[train_mask], dtype=torch.float32),
        torch.tensor(train_labels[train_mask] / args.rul_cap, dtype=torch.float32),
    )
    val_x = torch.tensor(train_windows[val_mask], dtype=torch.float32).to(device)
    val_y = train_labels[val_mask]
    loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True)

    print("[C-MAPSS GRU sequence benchmark]")
    print(
        f"subsets={','.join(args.subsets)} device={device} "
        f"windows={len(train_labels)} train={int(train_mask.sum())} val={int(val_mask.sum())} "
        f"input_size={train_windows.shape[-1]}"
    )
    for epoch in range(1, args.epochs + 1):
        model.train()
        losses: list[float] = []
        for batch_x, batch_y in loader:
            batch_x = batch_x.to(device)
            batch_y = batch_y.to(device)
            optimizer.zero_grad()
            prediction = model(batch_x)
            loss = loss_fn(prediction, batch_y)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            losses.append(float(loss.detach().cpu()))
        val_pred = _predict(model, val_x, args.rul_cap, device)
        print(f"epoch={epoch} train_loss={np.mean(losses):.5f} val_rmse={rmse(val_y, val_pred):.3f}")

    rows, prediction_frame = _evaluate(model, prepared, args.rul_cap, device)
    benchmark = pd.DataFrame(rows)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    benchmark.to_csv(output, index=False, encoding="utf-8-sig")

    predictions_output = Path(args.predictions_output)
    predictions_output.parent.mkdir(parents=True, exist_ok=True)
    prediction_frame.to_csv(predictions_output, index=False, encoding="utf-8-sig")

    model_output = Path(args.model_output)
    model_output.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "input_size": train_windows.shape[-1],
            "hidden_size": args.hidden_size,
            "layers": args.layers,
            "window_size": args.window_size,
            "rul_cap": args.rul_cap,
            "feature_note": "condition-normalized sensors + condition one-hot + subset one-hot",
        },
        model_output,
    )

    print("")
    for row in rows:
        print(_format_result(row))
    print(f"benchmark_csv={output}")
    print(f"predictions_csv={predictions_output}")
    print(f"model_file={model_output}")
    _print_comparison(Path("data/cmapss/cmapss_rul_condition_normalized_benchmark.csv"), benchmark)


def _prepare_subset(data_dir: Path, subset: str, window_size: int, rul_cap: int) -> PreparedSubset:
    subset_id = SUBSETS.index(subset)
    feature_columns = condition_feature_columns(include_raw_settings=False)
    train_raw = load_split(data_dir, subset=subset, split="train")  # type: ignore[arg-type]
    test_raw = load_split(data_dir, subset=subset, split="test")  # type: ignore[arg-type]
    normalizer = fit_condition_normalizer(train_raw, subset)
    train = add_train_rul(
        transform_with_condition_normalization(train_raw, normalizer, include_raw_settings=False),
        cap=rul_cap,
    )
    train_windows, train_labels, train_units = build_sliding_windows(
        train,
        window_size=window_size,
        feature_columns=feature_columns,
    )
    train_windows = _append_subset_one_hot(train_windows, subset_id)
    train_unit_keys = np.asarray([_unit_key(subset_id, int(unit)) for unit in train_units], dtype=np.int32)

    test = transform_with_condition_normalization(test_raw, normalizer, include_raw_settings=False)
    test_windows, test_units, test_last_cycles = _last_test_windows(test, window_size, feature_columns)
    test_windows = _append_subset_one_hot(test_windows, subset_id)
    test_rul = load_test_rul(data_dir, subset=subset)  # type: ignore[arg-type]
    test_true = test_rul.to_numpy(dtype=np.float32)[test_units - 1]
    test_true_capped = np.clip(test_true, 0, rul_cap)

    return PreparedSubset(
        subset=subset,
        train_windows=train_windows,
        train_labels=train_labels.astype(np.float32),
        train_unit_keys=train_unit_keys,
        test_windows=test_windows,
        test_true=test_true,
        test_true_capped=test_true_capped,
        test_units=test_units,
        test_last_cycles=test_last_cycles,
    )


def _evaluate(
    model: torch.nn.Module,
    prepared: list[PreparedSubset],
    rul_cap: int,
    device: torch.device,
) -> tuple[list[dict[str, object]], pd.DataFrame]:
    rows: list[dict[str, object]] = []
    prediction_frames: list[pd.DataFrame] = []
    all_true: list[np.ndarray] = []
    all_true_capped: list[np.ndarray] = []
    all_pred: list[np.ndarray] = []
    for item in prepared:
        test_x = torch.tensor(item.test_windows, dtype=torch.float32).to(device)
        pred = _predict(model, test_x, rul_cap, device)
        rows.append(
            _metric_row(
                model_type="gru_sequence",
                subset=item.subset,
                test_units=len(item.test_units),
                test_true=item.test_true,
                test_true_capped=item.test_true_capped,
                test_pred=pred,
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
                    "predicted_rul": np.round(pred, 1),
                    "risk_72h": np.where(pred <= 72, "HIGH", "LOW"),
                }
            )
        )
        all_true.append(item.test_true)
        all_true_capped.append(item.test_true_capped)
        all_pred.append(pred)

    rows.append(
        _metric_row(
            model_type="gru_sequence",
            subset="ALL",
            test_units=sum(len(item.test_units) for item in prepared),
            test_true=np.concatenate(all_true),
            test_true_capped=np.concatenate(all_true_capped),
            test_pred=np.concatenate(all_pred),
        )
    )
    return rows, pd.concat(prediction_frames, ignore_index=True)


def _predict(model: torch.nn.Module, x: torch.Tensor, rul_cap: int, device: torch.device) -> np.ndarray:
    model.eval()
    predictions: list[np.ndarray] = []
    with torch.no_grad():
        for start in range(0, len(x), 2048):
            batch = x[start : start + 2048].to(device)
            pred = model(batch).detach().cpu().numpy() * rul_cap
            predictions.append(pred.astype(np.float32))
    return np.clip(np.concatenate(predictions), 0, rul_cap)


def _metric_row(
    model_type: str,
    subset: str,
    test_units: int,
    test_true: np.ndarray,
    test_true_capped: np.ndarray,
    test_pred: np.ndarray,
) -> dict[str, object]:
    return {
        "model_type": model_type,
        "subset": subset,
        "test_units": test_units,
        "test_rmse_uncapped": rmse(test_true, test_pred),
        "test_rmse_capped": rmse(test_true_capped, test_pred),
        "test_phm_score_capped": phm_score(test_true_capped, test_pred),
        "high_risk_count": int((test_pred <= 72).sum()),
    }


def _format_result(row: dict[str, object]) -> str:
    return (
        f"{row['model_type']:>12} {row['subset']:>5} "
        f"test_rmse={float(row['test_rmse_capped']):>7.3f} "
        f"phm={float(row['test_phm_score_capped']):>10.1f} "
        f"high_risk={int(row['high_risk_count']):>3}/{int(row['test_units'])}"
    )


def _print_comparison(baseline_path: Path, benchmark: pd.DataFrame) -> None:
    if not baseline_path.exists():
        return
    baseline = pd.read_csv(baseline_path)
    base_all = baseline[
        (baseline["model_type"] == "condition_combined")
        & (baseline["subset"] == "ALL")
    ]
    seq_all = benchmark[(benchmark["model_type"] == "gru_sequence") & (benchmark["subset"] == "ALL")]
    if base_all.empty or seq_all.empty:
        return
    base_rmse = float(base_all.iloc[0]["test_rmse_capped"])
    seq_rmse = float(seq_all.iloc[0]["test_rmse_capped"])
    base_phm = float(base_all.iloc[0]["test_phm_score_capped"])
    seq_phm = float(seq_all.iloc[0]["test_phm_score_capped"])
    print("")
    print("[comparison vs condition-normalized HGBR]")
    print(f"ALL test_rmse_capped: {base_rmse:.3f} -> {seq_rmse:.3f} delta={seq_rmse - base_rmse:+.3f}")
    print(f"ALL phm_score_capped: {base_phm:.1f} -> {seq_phm:.1f} delta={seq_phm - base_phm:+.1f}")


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


def _append_subset_one_hot(windows: np.ndarray, subset_id: int) -> np.ndarray:
    one_hot = np.zeros((windows.shape[0], windows.shape[1], len(SUBSETS)), dtype=np.float32)
    one_hot[:, :, subset_id] = 1.0
    return np.concatenate([windows, one_hot], axis=2).astype(np.float32)


def _unit_holdout_mask(unit_keys: np.ndarray, validation_ratio: float = 0.2) -> tuple[np.ndarray, np.ndarray]:
    unique_units = np.asarray(sorted(set(unit_keys.tolist())))
    rng = np.random.default_rng(42)
    shuffled = unique_units.copy()
    rng.shuffle(shuffled)
    val_count = max(1, int(round(len(unique_units) * validation_ratio)))
    validation_units = set(shuffled[:val_count].tolist())
    val_mask = np.asarray([int(unit) in validation_units for unit in unit_keys], dtype=bool)
    return ~val_mask, val_mask


def _unit_key(subset_id: int, unit: int) -> int:
    return (subset_id + 1) * 1000 + unit


def _seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


if __name__ == "__main__":
    main()
