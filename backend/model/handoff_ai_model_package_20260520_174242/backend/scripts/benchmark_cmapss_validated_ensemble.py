from __future__ import annotations

import argparse
import copy
import random
import sys
from dataclasses import dataclass
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.cmapss import SUBSETS, add_train_rul, build_sliding_windows, load_split, load_test_rul, phm_score, rmse  # noqa: E402
from app.cmapss_conditioning import condition_feature_columns, fit_condition_normalizer, transform_with_condition_normalization  # noqa: E402
from app.ml_model import (  # noqa: E402
    CNNGRURULRegressor,
    GRURULRegressor,
    ITransformerRULRegressor,
    NormalizedLSTMRULRegressor,
    PatchTSTRULRegressor,
    TCNRULRegressor,
)


MODEL_FACTORIES = {
    "gru": GRURULRegressor,
    "lstm": NormalizedLSTMRULRegressor,
    "tcn": TCNRULRegressor,
    "cnn_gru": CNNGRURULRegressor,
    "patchtst": PatchTSTRULRegressor,
    "itransformer": ITransformerRULRegressor,
}


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
    parser = argparse.ArgumentParser(description="Train sequence models with early stopping and tune ensembles on validation predictions.")
    parser.add_argument("--data-dir", default="data/cmapss")
    parser.add_argument("--models", nargs="+", default=["gru", "tcn", "lstm", "cnn_gru"], choices=sorted(MODEL_FACTORIES))
    parser.add_argument("--subsets", nargs="+", default=list(SUBSETS), choices=list(SUBSETS))
    parser.add_argument("--window-size", type=int, default=50)
    parser.add_argument("--rul-cap", type=int, default=125)
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=1024)
    parser.add_argument("--hidden-size", type=int, default=64)
    parser.add_argument("--layers", type=int, default=1)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--weight-step", type=float, default=0.01)
    parser.add_argument("--output", default="data/cmapss/cmapss_validated_ensemble_benchmark.csv")
    parser.add_argument("--predictions-output", default="data/cmapss/cmapss_validated_ensemble_predictions.csv")
    parser.add_argument("--models-dir", default="data/models/validated_ensemble")
    args = parser.parse_args()

    _seed_everything(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    prepared = [_prepare_subset(Path(args.data_dir), subset, args.window_size, args.rul_cap) for subset in args.subsets]
    train_windows = np.concatenate([item.train_windows for item in prepared], axis=0)
    train_labels = np.concatenate([item.train_labels for item in prepared], axis=0)
    unit_keys = np.concatenate([item.train_unit_keys for item in prepared], axis=0)
    train_mask, val_mask = _unit_holdout_mask(unit_keys, seed=args.seed)
    val_x = torch.tensor(train_windows[val_mask], dtype=torch.float32).to(device)
    val_y = train_labels[val_mask]

    print("[C-MAPSS validated ensemble benchmark]")
    print(
        f"models={','.join(args.models)} device={device} epochs={args.epochs} "
        f"windows={len(train_labels)} train={int(train_mask.sum())} val={int(val_mask.sum())} "
        f"input_size={train_windows.shape[-1]}"
    )

    model_results: dict[str, dict[str, object]] = {}
    benchmark_rows: list[dict[str, object]] = []
    models_dir = Path(args.models_dir)
    models_dir.mkdir(parents=True, exist_ok=True)

    for model_name in args.models:
        print("")
        print(f"[train {model_name}]")
        _seed_everything(args.seed)
        model = _make_model(model_name, train_windows.shape[-1], args.hidden_size, args.layers).to(device)
        optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=1e-4)
        loss_fn = nn.MSELoss()
        train_dataset = TensorDataset(
            torch.tensor(train_windows[train_mask], dtype=torch.float32),
            torch.tensor(train_labels[train_mask] / args.rul_cap, dtype=torch.float32),
        )
        loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True)
        history, best_state = _train_with_early_selection(
            model,
            loader,
            optimizer,
            loss_fn,
            val_x,
            val_y,
            args.rul_cap,
            device,
            args.epochs,
        )
        model.load_state_dict(best_state)
        val_pred = _predict(model, val_x, args.rul_cap, device)
        rows, test_frame = _evaluate_model(model_name, model, prepared, args.rul_cap, device)
        benchmark_rows.extend(rows)
        model_results[model_name] = {
            "model": model,
            "history": history,
            "best_epoch": min(history, key=lambda row: row["val_rmse"])["epoch"],
            "best_val_rmse": min(row["val_rmse"] for row in history),
            "val_pred": val_pred,
            "test_frame": test_frame,
        }
        torch.save(
            {
                "model_state_dict": best_state,
                "model_name": model_name,
                "input_size": train_windows.shape[-1],
                "hidden_size": args.hidden_size,
                "layers": args.layers,
                "window_size": args.window_size,
                "rul_cap": args.rul_cap,
                "epoch_history": history,
                "best_epoch": model_results[model_name]["best_epoch"],
                "best_val_rmse": model_results[model_name]["best_val_rmse"],
            },
            models_dir / f"cmapss_{model_name}_best.pt",
        )
        for row in rows:
            print(_format_result(row))

    ensemble_rows, ensemble_predictions = _evaluate_ensembles(model_results, val_y, args.rul_cap, args.weight_step)
    benchmark_rows.extend(ensemble_rows)

    benchmark = pd.DataFrame(benchmark_rows)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    benchmark.to_csv(output, index=False, encoding="utf-8-sig")

    predictions_output = Path(args.predictions_output)
    predictions_output.parent.mkdir(parents=True, exist_ok=True)
    ensemble_predictions.to_csv(predictions_output, index=False, encoding="utf-8-sig")

    print("")
    print("[leaderboard: ALL]")
    all_rows = benchmark[benchmark["subset"] == "ALL"].sort_values("test_rmse_capped")
    for _, row in all_rows.iterrows():
        print(
            f"{row['name']:>26} "
            f"rmse={float(row['test_rmse_capped']):.3f} "
            f"phm={float(row['test_phm_score_capped']):.1f} "
            f"high_risk={int(row['high_risk_count'])}/{int(row['test_units'])}"
        )
    print(f"benchmark_csv={output}")
    print(f"predictions_csv={predictions_output}")
    print(f"models_dir={models_dir}")


def _train_with_early_selection(
    model: torch.nn.Module,
    loader: DataLoader,
    optimizer: torch.optim.Optimizer,
    loss_fn: torch.nn.Module,
    val_x: torch.Tensor,
    val_y: np.ndarray,
    rul_cap: int,
    device: torch.device,
    epochs: int,
) -> tuple[list[dict[str, float]], dict[str, torch.Tensor]]:
    history: list[dict[str, float]] = []
    best_state = copy.deepcopy(model.state_dict())
    best_val = float("inf")
    for epoch in range(1, epochs + 1):
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
        val_pred = _predict(model, val_x, rul_cap, device)
        val_rmse = rmse(val_y, val_pred)
        row = {"epoch": float(epoch), "train_loss": float(np.mean(losses)), "val_rmse": val_rmse}
        history.append(row)
        if val_rmse < best_val:
            best_val = val_rmse
            best_state = copy.deepcopy(model.state_dict())
            marker = "*"
        else:
            marker = ""
        print(f"epoch={epoch} train_loss={row['train_loss']:.5f} val_rmse={val_rmse:.3f}{marker}")
    return history, best_state


def _evaluate_ensembles(
    model_results: dict[str, dict[str, object]],
    val_y: np.ndarray,
    rul_cap: int,
    weight_step: float,
) -> tuple[list[dict[str, object]], pd.DataFrame]:
    names = list(model_results)
    base_frame = next(iter(model_results.values()))["test_frame"].copy()  # type: ignore[union-attr]
    for name, result in model_results.items():
        test_frame = result["test_frame"]  # type: ignore[assignment]
        base_frame[name] = test_frame["predicted_rul"].to_numpy(dtype=np.float32)

    candidate_weights: dict[str, dict[str, float]] = {}
    candidate_weights["ensemble_equal_all"] = {name: 1.0 / len(names) for name in names}
    if {"gru", "tcn"}.issubset(names):
        candidate_weights["ensemble_equal_gru_tcn"] = {"gru": 0.5, "tcn": 0.5}
        candidate_weights["ensemble_grid_gru_tcn_val"] = _grid_search_on_validation(model_results, val_y, ["gru", "tcn"], weight_step)
    if {"gru", "patchtst"}.issubset(names):
        candidate_weights["ensemble_equal_gru_patchtst"] = {"gru": 0.5, "patchtst": 0.5}
        candidate_weights["ensemble_grid_gru_patchtst_val"] = _grid_search_on_validation(model_results, val_y, ["gru", "patchtst"], weight_step)
    if {"gru", "tcn", "patchtst"}.issubset(names):
        candidate_weights["ensemble_equal_gru_tcn_patchtst"] = {"gru": 1.0 / 3.0, "tcn": 1.0 / 3.0, "patchtst": 1.0 / 3.0}
        candidate_weights["ensemble_grid_gru_tcn_patchtst_val"] = _grid_search_on_validation(model_results, val_y, ["gru", "tcn", "patchtst"], weight_step)
    candidate_weights["ensemble_inverse_val_rmse"] = _inverse_val_weights(model_results)
    candidate_weights["ensemble_constrained_ls_val"] = _constrained_least_squares_weights(model_results, val_y)

    rows: list[dict[str, object]] = []
    prediction_output = base_frame[["subset", "unit", "last_cycle", "actual_rul", "actual_rul_capped"]].copy()
    for name, weights in candidate_weights.items():
        prediction = _weighted_prediction(base_frame, weights, rul_cap)
        base_frame[name] = prediction
        prediction_output[name] = prediction
        prediction_output[f"{name}_risk_72h"] = np.where(prediction <= 72, "HIGH", "LOW")
        rows.extend(_evaluate_prediction_column(base_frame, name, name, weights))
        print(f"{name} weights={weights}")
    return rows, prediction_output


def _prepare_subset(data_dir: Path, subset: str, window_size: int, rul_cap: int) -> PreparedSubset:
    subset_id = SUBSETS.index(subset)
    feature_columns = condition_feature_columns(include_raw_settings=False)
    train_raw = load_split(data_dir, subset=subset, split="train")  # type: ignore[arg-type]
    test_raw = load_split(data_dir, subset=subset, split="test")  # type: ignore[arg-type]
    normalizer = fit_condition_normalizer(train_raw, subset)
    train = add_train_rul(transform_with_condition_normalization(train_raw, normalizer, include_raw_settings=False), cap=rul_cap)
    train_windows, train_labels, train_units = build_sliding_windows(train, window_size=window_size, feature_columns=feature_columns)
    train_windows = _append_subset_one_hot(train_windows, subset_id)
    train_unit_keys = np.asarray([_unit_key(subset_id, int(unit)) for unit in train_units], dtype=np.int32)

    test = transform_with_condition_normalization(test_raw, normalizer, include_raw_settings=False)
    test_windows, test_units, test_last_cycles = _last_test_windows(test, window_size, feature_columns)
    test_windows = _append_subset_one_hot(test_windows, subset_id)
    test_rul = load_test_rul(data_dir, subset=subset)  # type: ignore[arg-type]
    test_true = test_rul.to_numpy(dtype=np.float32)[test_units - 1]
    test_true_capped = np.clip(test_true, 0, rul_cap)
    return PreparedSubset(subset, train_windows, train_labels.astype(np.float32), train_unit_keys, test_windows, test_true, test_true_capped, test_units, test_last_cycles)


def _evaluate_model(
    model_name: str,
    model: torch.nn.Module,
    prepared: list[PreparedSubset],
    rul_cap: int,
    device: torch.device,
) -> tuple[list[dict[str, object]], pd.DataFrame]:
    rows: list[dict[str, object]] = []
    frames: list[pd.DataFrame] = []
    all_true: list[np.ndarray] = []
    all_true_capped: list[np.ndarray] = []
    all_pred: list[np.ndarray] = []
    for item in prepared:
        pred = _predict(model, torch.tensor(item.test_windows, dtype=torch.float32).to(device), rul_cap, device)
        rows.append(_metric_row(f"single_{model_name}", item.subset, len(item.test_units), item.test_true, item.test_true_capped, pred, {}))
        frames.append(
            pd.DataFrame(
                {
                    "subset": item.subset,
                    "unit": item.test_units,
                    "last_cycle": item.test_last_cycles,
                    "actual_rul": item.test_true,
                    "actual_rul_capped": item.test_true_capped,
                    "predicted_rul": pred,
                }
            )
        )
        all_true.append(item.test_true)
        all_true_capped.append(item.test_true_capped)
        all_pred.append(pred)
    rows.append(_metric_row(f"single_{model_name}", "ALL", sum(len(item.test_units) for item in prepared), np.concatenate(all_true), np.concatenate(all_true_capped), np.concatenate(all_pred), {}))
    return rows, pd.concat(frames, ignore_index=True)


def _evaluate_prediction_column(frame: pd.DataFrame, prediction_column: str, name: str, weights: dict[str, float]) -> list[dict[str, object]]:
    rows = []
    for subset, subset_frame in list(frame.groupby("subset")) + [("ALL", frame)]:
        rows.append(
            _metric_row(
                name,
                subset,
                int(len(subset_frame)),
                subset_frame["actual_rul"].to_numpy(dtype=np.float32),
                subset_frame["actual_rul_capped"].to_numpy(dtype=np.float32),
                subset_frame[prediction_column].to_numpy(dtype=np.float32),
                weights,
            )
        )
    return rows


def _metric_row(
    name: str,
    subset: str,
    test_units: int,
    test_true: np.ndarray,
    test_true_capped: np.ndarray,
    prediction: np.ndarray,
    weights: dict[str, float],
) -> dict[str, object]:
    return {
        "name": name,
        "subset": subset,
        "test_units": test_units,
        "test_rmse_uncapped": rmse(test_true, prediction),
        "test_rmse_capped": rmse(test_true_capped, prediction),
        "test_phm_score_capped": phm_score(test_true_capped, prediction),
        "high_risk_count": int((prediction <= 72).sum()),
        "weights": weights,
    }


def _predict(model: torch.nn.Module, x: torch.Tensor, rul_cap: int, device: torch.device) -> np.ndarray:
    model.eval()
    predictions: list[np.ndarray] = []
    with torch.no_grad():
        for start in range(0, len(x), 2048):
            batch = x[start : start + 2048].to(device)
            predictions.append((model(batch).detach().cpu().numpy() * rul_cap).astype(np.float32))
    return np.clip(np.concatenate(predictions), 0, rul_cap)


def _make_model(model_name: str, input_size: int, hidden_size: int, layers: int) -> torch.nn.Module:
    factory = MODEL_FACTORIES[model_name]
    if model_name == "tcn":
        return factory(input_size=input_size, hidden_size=hidden_size, layers=max(3, layers + 3))
    if model_name in {"patchtst", "itransformer"}:
        return factory(input_size=input_size, hidden_size=hidden_size, layers=max(2, layers + 1))
    return factory(input_size=input_size, hidden_size=hidden_size, layers=layers)


def _inverse_val_weights(model_results: dict[str, dict[str, object]]) -> dict[str, float]:
    raw = {name: 1.0 / max(float(result["best_val_rmse"]), 1e-6) ** 2 for name, result in model_results.items()}
    total = sum(raw.values())
    return {name: value / total for name, value in raw.items()}


def _grid_search_on_validation(
    model_results: dict[str, dict[str, object]],
    val_y: np.ndarray,
    names: list[str],
    step: float,
) -> dict[str, float]:
    best_rmse = float("inf")
    best_weights = {names[0]: 1.0}
    ticks = np.arange(0.0, 1.0 + step / 2.0, step)
    for values in _weight_grid(len(names), ticks, step):
        weights = {name: float(value) for name, value in zip(names, values)}
        pred = np.zeros_like(val_y, dtype=np.float32)
        for name, weight in weights.items():
            pred += model_results[name]["val_pred"] * weight
        score = rmse(val_y, np.clip(pred, 0, 125))
        if score < best_rmse:
            best_rmse = score
            best_weights = weights
    return best_weights


def _weight_grid(count: int, ticks: np.ndarray, step: float):
    for values in product(ticks, repeat=count):
        if abs(float(sum(values)) - 1.0) <= step / 3.0:
            yield tuple(float(value) for value in values)


def _constrained_least_squares_weights(
    model_results: dict[str, dict[str, object]],
    val_y: np.ndarray,
) -> dict[str, float]:
    names = list(model_results)
    x = np.column_stack([model_results[name]["val_pred"] for name in names]).astype(np.float64)
    y = val_y.astype(np.float64)
    xtx = x.T @ x + np.eye(len(names)) * 1e-6
    ones = np.ones((len(names), 1))
    kkt = np.block([[xtx, ones], [ones.T, np.zeros((1, 1))]])
    rhs = np.concatenate([x.T @ y, np.asarray([1.0])])
    solution = np.linalg.solve(kkt, rhs)[: len(names)]
    solution = np.clip(solution, 0.0, None)
    if solution.sum() <= 1e-12:
        solution = np.ones(len(names)) / len(names)
    else:
        solution = solution / solution.sum()
    return {name: float(weight) for name, weight in zip(names, solution)}


def _weighted_prediction(frame: pd.DataFrame, weights: dict[str, float], rul_cap: int) -> np.ndarray:
    prediction = np.zeros(len(frame), dtype=np.float32)
    for name, weight in weights.items():
        prediction += frame[name].to_numpy(dtype=np.float32) * float(weight)
    return np.clip(prediction, 0, rul_cap)


def _format_result(row: dict[str, object]) -> str:
    return (
        f"{row['name']:>16} {row['subset']:>5} "
        f"test_rmse={float(row['test_rmse_capped']):>7.3f} "
        f"phm={float(row['test_phm_score_capped']):>10.1f} "
        f"high_risk={int(row['high_risk_count']):>3}/{int(row['test_units'])}"
    )


def _last_test_windows(frame: pd.DataFrame, window_size: int, feature_columns: list[str]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    windows: list[np.ndarray] = []
    units: list[int] = []
    last_cycles: list[int] = []
    for unit, unit_frame in frame.groupby("unit"):
        unit_frame = unit_frame.sort_values("cycle")
        values = unit_frame[feature_columns].to_numpy(dtype=np.float32)
        if len(values) < window_size:
            values = np.vstack([np.repeat(values[:1], window_size - len(values), axis=0), values])
        windows.append(values[-window_size:])
        units.append(int(unit))
        last_cycles.append(int(unit_frame["cycle"].iloc[-1]))
    return np.stack(windows).astype(np.float32), np.asarray(units, dtype=np.int32), np.asarray(last_cycles, dtype=np.int32)


def _append_subset_one_hot(windows: np.ndarray, subset_id: int) -> np.ndarray:
    one_hot = np.zeros((windows.shape[0], windows.shape[1], len(SUBSETS)), dtype=np.float32)
    one_hot[:, :, subset_id] = 1.0
    return np.concatenate([windows, one_hot], axis=2).astype(np.float32)


def _unit_holdout_mask(unit_keys: np.ndarray, validation_ratio: float = 0.2, seed: int = 42) -> tuple[np.ndarray, np.ndarray]:
    unique_units = np.asarray(sorted(set(unit_keys.tolist())))
    rng = np.random.default_rng(seed)
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
