from __future__ import annotations

import argparse
import csv
import io
import json
import math
import random
import sys
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import torch
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from torch import nn
from torch.utils.data import DataLoader, Dataset

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.aihub import (  # noqa: E402
    AIHUB_LABELS,
    build_aihub_feature_table,
    find_default_aihub_current_zip,
    find_default_aihub_vibration_zip,
    load_aihub_current_zip,
    load_aihub_vibration_zip,
)


LABEL_ORDER = ["00", "01", "02", "03", "04"]


@dataclass(frozen=True)
class WaveformRecord:
    member: str
    label: str
    group: str
    motor_kw: float | None
    sample_rate: float | None
    waveform: np.ndarray


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    parser = argparse.ArgumentParser(description="AI-Hub raw waveform 1D-CNN/TCN classification benchmark.")
    parser.add_argument("--signal-kind", choices=["current", "vibration"], default="vibration")
    parser.add_argument("--zip-path", default="")
    parser.add_argument("--max-files", type=int, default=3000)
    parser.add_argument("--max-per-path-label", type=int, default=600)
    parser.add_argument("--target-length", type=int, default=1024)
    parser.add_argument("--epochs", type=int, default=6)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--cv-folds", type=int, default=1, help="Use grouped CV when greater than 1.")
    parser.add_argument("--skip-tabular-reference", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--tasks", default="multiclass_fault_type,fault_type_only")
    parser.add_argument("--models", default="cnn,tcn")
    parser.add_argument("--output", default="data/aihub238/aihub_waveform_deep_benchmark.csv")
    parser.add_argument("--report-output", default="data/aihub238/aihub_waveform_deep_report.md")
    parser.add_argument("--model-dir", default="data/models/aihub_waveform_deep")
    args = parser.parse_args()

    _set_seed(args.seed)
    zip_path = Path(args.zip_path) if args.zip_path else _find_default_zip(args.signal_kind)
    records = _load_waveform_records(
        zip_path=zip_path,
        signal_kind=args.signal_kind,
        max_files=args.max_files,
        max_per_path_label=args.max_per_path_label,
        target_length=args.target_length,
        seed=args.seed,
    )
    if not records:
        raise ValueError("No waveform records loaded.")

    tasks = [task.strip() for task in args.tasks.split(",") if task.strip()]
    model_names = [model.strip() for model in args.models.split(",") if model.strip()]
    output_rows: list[dict[str, Any]] = []
    saved_models: list[dict[str, Any]] = []
    model_dir = Path(args.model_dir)
    model_dir.mkdir(parents=True, exist_ok=True)

    for task_name in tasks:
        task_records = _task_records(records, task_name)
        raw_labels = pd.Series([record.label for record in task_records])
        labels = _task_label_series(raw_labels, task_name)
        groups = pd.Series([record.group for record in task_records])
        label_values = _label_values(task_name, labels)
        label_to_index = {label: index for index, label in enumerate(label_values)}
        y = labels.map(label_to_index)
        splits = _cv_splits(y, groups, args.seed, args.cv_folds)
        for fold, train_index, test_index in splits:
            train_records = [task_records[index] for index in train_index]
            test_records = [task_records[index] for index in test_index]
            print(
                f"task={task_name} fold={fold} rows={len(task_records)} labels={label_values} "
                f"groups={groups.nunique()} train/test={len(train_records)}/{len(test_records)}"
            )

            if not args.skip_tabular_reference:
                baseline_row, baseline_model = _run_tabular_reference(
                    signal_kind=args.signal_kind,
                    task_name=task_name,
                    label_values=label_values,
                    label_to_index=label_to_index,
                    train_members={record.member for record in train_records},
                    test_members={record.member for record in test_records},
                    args=args,
                )
                if baseline_row:
                    baseline_row["fold"] = fold
                    output_rows.append(baseline_row)
                    path = model_dir / f"{args.signal_kind}_{task_name}_fold{fold}_tabular_reference.joblib"
                    joblib.dump(baseline_model, path)
                    saved_models.append({"task": task_name, "model": "tabular_reference", "path": str(path)})

            for model_name in model_names:
                row, trained_model = _train_deep_model(
                    model_name=model_name,
                    signal_kind=args.signal_kind,
                    task_name=task_name,
                    label_values=label_values,
                    train_records=train_records,
                    test_records=test_records,
                    args=args,
                )
                row["fold"] = fold
                output_rows.append(row)
                path = model_dir / f"{args.signal_kind}_{task_name}_fold{fold}_{model_name}.pt"
                torch.save(
                    {
                        "model_state_dict": trained_model.state_dict(),
                        "model_name": model_name,
                        "signal_kind": args.signal_kind,
                        "task": task_name,
                        "fold": fold,
                        "label_values": label_values,
                        "target_length": args.target_length,
                        "metrics": row,
                    },
                    path,
                )
                saved_models.append({"task": task_name, "model": model_name, "path": str(path)})

    benchmark = pd.DataFrame(output_rows).sort_values(["task", "macro_f1"], ascending=[True, False])
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    benchmark.to_csv(output_path, index=False, encoding="utf-8-sig")

    report_path = Path(args.report_output)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        _make_report(zip_path, records, benchmark, saved_models, args),
        encoding="utf-8",
    )
    print("")
    print(f"benchmark_csv={output_path}")
    print(f"report_md={report_path}")
    for item in saved_models:
        print(f"model={item['path']}")


def _find_default_zip(signal_kind: str) -> Path:
    if signal_kind == "vibration":
        return find_default_aihub_vibration_zip()
    return find_default_aihub_current_zip()


def _load_waveform_records(
    zip_path: Path,
    signal_kind: str,
    max_files: int,
    max_per_path_label: int,
    target_length: int,
    seed: int,
) -> list[WaveformRecord]:
    with zipfile.ZipFile(zip_path) as archive:
        entries = sorted(
            [info for info in archive.infolist() if info.filename.lower().endswith(".csv")],
            key=lambda info: info.filename,
        )
        selected = _select_entries(entries, max_files, max_per_path_label, seed)
        records = []
        start = time.time()
        for count, info in enumerate(selected, start=1):
            record = _read_waveform_member(archive, info, signal_kind, target_length)
            if record is not None:
                records.append(record)
            if count % 500 == 0:
                print(f"loaded={count}/{len(selected)} kept={len(records)} elapsed={time.time() - start:.1f}s", flush=True)
    return records


def _select_entries(
    entries: list[zipfile.ZipInfo],
    max_files: int,
    max_per_path_label: int,
    seed: int,
) -> list[zipfile.ZipInfo]:
    rng = random.Random(seed)
    buckets: dict[str, list[zipfile.ZipInfo]] = {}
    for info in entries:
        parts = info.filename.split("/")
        path_label = parts[3] if len(parts) >= 4 else "unknown"
        buckets.setdefault(path_label, []).append(info)
    selected: list[zipfile.ZipInfo] = []
    for path_label in sorted(buckets):
        members = buckets[path_label][:]
        rng.shuffle(members)
        selected.extend(members[:max_per_path_label])
    rng.shuffle(selected)
    return selected[:max_files]


def _read_waveform_member(
    archive: zipfile.ZipFile,
    info: zipfile.ZipInfo,
    signal_kind: str,
    target_length: int,
) -> WaveformRecord | None:
    metadata: dict[str, list[str]] = {}
    rows: list[list[float]] = []
    with archive.open(info) as raw_file:
        text_file = io.TextIOWrapper(raw_file, encoding="utf-8-sig", newline="")
        reader = csv.reader(text_file)
        for row in reader:
            if not row:
                continue
            key = row[0].strip()
            if key in {
                "Date",
                "Filename",
                "Data Label",
                "Label No",
                "Label_No",
                "Motor Spec",
                "Period",
                "Sample Rate",
                "RMS",
                "Data Length",
            }:
                metadata[key] = [value.strip() for value in row[1:] if value.strip()]
                continue
            values = []
            for value in row:
                try:
                    values.append(float(str(value).strip()))
                except ValueError:
                    pass
            if len(values) >= 2:
                rows.append(values)
    label = (_first(metadata.get("Label No")) or _first(metadata.get("Label_No"))).zfill(2)
    if label not in LABEL_ORDER or len(rows) < 16:
        return None
    signal = np.asarray(rows, dtype=np.float32)
    channels = signal[:, 1:]
    if channels.ndim != 2 or channels.shape[1] < 1:
        return None
    expected_channels = 3 if signal_kind == "current" else 1
    if channels.shape[1] < expected_channels:
        padding = np.zeros((channels.shape[0], expected_channels - channels.shape[1]), dtype=np.float32)
        channels = np.concatenate([channels, padding], axis=1)
    channels = channels[:, :expected_channels].T
    channels = _center_resample(channels, target_length)
    motor_values = metadata.get("Motor Spec", [])
    path_parts = info.filename.split("/")
    group = motor_values[0] if motor_values else (path_parts[2] if len(path_parts) >= 3 else "unknown")
    motor_kw = _to_float(motor_values[2]) if len(motor_values) >= 3 else _extract_kw(path_parts[1] if len(path_parts) >= 2 else "")
    return WaveformRecord(
        member=info.filename,
        label=label,
        group=group,
        motor_kw=motor_kw,
        sample_rate=_to_float(_first(metadata.get("Sample Rate"))),
        waveform=channels.astype(np.float32),
    )


def _center_resample(channels: np.ndarray, target_length: int) -> np.ndarray:
    length = channels.shape[1]
    if length == target_length:
        return channels
    if length > target_length:
        start = (length - target_length) // 2
        return channels[:, start : start + target_length]
    x_old = np.linspace(0.0, 1.0, length)
    x_new = np.linspace(0.0, 1.0, target_length)
    return np.vstack([np.interp(x_new, x_old, channel) for channel in channels]).astype(np.float32)


def _task_records(records: list[WaveformRecord], task_name: str) -> list[WaveformRecord]:
    if task_name == "fault_type_only":
        return [record for record in records if record.label != "00"]
    return records


def _label_values(task_name: str, labels: pd.Series) -> list[str]:
    if task_name == "binary_normal_vs_fault":
        return ["normal", "fault"]
    return [label for label in LABEL_ORDER if label in set(labels)]


def _task_label_series(labels: pd.Series, task_name: str) -> pd.Series:
    if task_name == "binary_normal_vs_fault":
        return labels.map(lambda value: "normal" if value == "00" else "fault")
    return labels


def _best_group_split(y: pd.Series, groups: pd.Series, seed: int) -> tuple[np.ndarray, np.ndarray]:
    splitter = StratifiedGroupKFold(n_splits=min(5, groups.nunique()), shuffle=True, random_state=seed)
    best_split: tuple[np.ndarray, np.ndarray] | None = None
    best_score: tuple[float, float, float] | None = None
    for train_index, test_index in splitter.split(np.zeros(len(y)), y, groups):
        test_counts = y.iloc[test_index].value_counts().reindex(sorted(y.unique()), fill_value=0)
        coverage = float((test_counts > 0).sum())
        balance = -float(test_counts.std(ddof=0))
        size_penalty = -abs(len(test_index) / len(y) - 0.2)
        score = (coverage, balance, size_penalty)
        if best_score is None or score > best_score:
            best_score = score
            best_split = (train_index, test_index)
    if best_split is None:
        raise ValueError("Could not create group split.")
    return best_split


def _cv_splits(
    y: pd.Series,
    groups: pd.Series,
    seed: int,
    cv_folds: int,
) -> list[tuple[int, np.ndarray, np.ndarray]]:
    if cv_folds <= 1:
        train_index, test_index = _best_group_split(y, groups, seed)
        return [(1, train_index, test_index)]
    n_splits = min(cv_folds, groups.nunique())
    splitter = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    return [
        (fold, train_index, test_index)
        for fold, (train_index, test_index) in enumerate(splitter.split(np.zeros(len(y)), y, groups), start=1)
    ]


def _run_tabular_reference(
    signal_kind: str,
    task_name: str,
    label_values: list[str],
    label_to_index: dict[str, int],
    train_members: set[str],
    test_members: set[str],
    args: argparse.Namespace,
) -> tuple[dict[str, Any] | None, Any | None]:
    try:
        zip_path = _find_default_zip(signal_kind)
        loader = load_aihub_vibration_zip if signal_kind == "vibration" else load_aihub_current_zip
        frame = loader(zip_path, max_files=args.max_files, max_per_path_label=args.max_per_path_label, seed=args.seed)
        features, labels, _groups = build_aihub_feature_table(frame, include_asset_baseline_features=True)
        if task_name == "binary_normal_vs_fault":
            target_labels = labels.map(lambda value: "normal" if value == "00" else "fault")
        elif task_name == "fault_type_only":
            mask = labels != "00"
            frame = frame.loc[mask].reset_index(drop=True)
            features = features.loc[mask].reset_index(drop=True)
            target_labels = labels.loc[mask].reset_index(drop=True)
        else:
            target_labels = labels
        train_mask = frame["zip_member"].isin(train_members).to_numpy()
        test_mask = frame["zip_member"].isin(test_members).to_numpy()
        if train_mask.sum() < 10 or test_mask.sum() < 10:
            return None, None
        target = target_labels.map(label_to_index)
        model = make_pipeline(
            StandardScaler(),
            RandomForestClassifier(
                n_estimators=250,
                min_samples_leaf=2,
                max_features="sqrt",
                class_weight="balanced_subsample",
                random_state=args.seed,
                n_jobs=-1,
            ),
        )
        model.fit(features.loc[train_mask], target.loc[train_mask])
        probabilities = model.predict_proba(features.loc[test_mask])
        predictions = np.argmax(probabilities, axis=1)
        truth = target.loc[test_mask].to_numpy()
        row = _metric_row(
            signal_kind=signal_kind,
            task_name=task_name,
            model_name="tabular_random_forest_reference",
            label_values=label_values,
            truth=truth,
            predictions=predictions,
            probabilities=probabilities,
            train_rows=int(train_mask.sum()),
            test_rows=int(test_mask.sum()),
            epochs=0,
        )
        print(_format_metric(row))
        return row, model
    except Exception as exc:  # pragma: no cover - benchmark convenience path
        print(f"tabular_reference_skipped={exc}")
        return None, None


def _train_deep_model(
    model_name: str,
    signal_kind: str,
    task_name: str,
    label_values: list[str],
    train_records: list[WaveformRecord],
    test_records: list[WaveformRecord],
    args: argparse.Namespace,
) -> tuple[dict[str, Any], nn.Module]:
    num_classes = len(label_values)
    input_channels = train_records[0].waveform.shape[0]
    train_dataset = WaveformDataset(train_records, label_values, task_name, args.target_length, augment=True, seed=args.seed)
    test_dataset = WaveformDataset(test_records, label_values, task_name, args.target_length, augment=False, seed=args.seed)
    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True)
    test_loader = DataLoader(test_dataset, batch_size=args.batch_size, shuffle=False)
    model = _make_model(model_name, input_channels, num_classes)
    class_counts = np.bincount([label for _, label in train_dataset], minlength=num_classes)
    class_weights = class_counts.sum() / np.maximum(class_counts, 1)
    class_weights = class_weights / class_weights.mean()
    criterion = nn.CrossEntropyLoss(weight=torch.tensor(class_weights, dtype=torch.float32))
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-3)
    best_state = None
    best_macro = -1.0
    for epoch in range(1, args.epochs + 1):
        model.train()
        losses = []
        for batch_x, batch_y in train_loader:
            optimizer.zero_grad(set_to_none=True)
            logits = model(batch_x)
            loss = criterion(logits, batch_y)
            loss.backward()
            optimizer.step()
            losses.append(float(loss.item()))
        truth, predictions, probabilities = _predict(model, test_loader)
        macro = f1_score(truth, predictions, average="macro", zero_division=0)
        if macro > best_macro:
            best_macro = float(macro)
            best_state = {key: value.detach().clone() for key, value in model.state_dict().items()}
        print(
            f"{signal_kind} {task_name} {model_name} epoch={epoch}/{args.epochs} "
            f"loss={np.mean(losses):.4f} macro_f1={macro:.3f}",
            flush=True,
        )
    if best_state is not None:
        model.load_state_dict(best_state)
    truth, predictions, probabilities = _predict(model, test_loader)
    row = _metric_row(
        signal_kind=signal_kind,
        task_name=task_name,
        model_name=model_name,
        label_values=label_values,
        truth=truth,
        predictions=predictions,
        probabilities=probabilities,
        train_rows=len(train_records),
        test_rows=len(test_records),
        epochs=args.epochs,
    )
    print(_format_metric(row))
    return row, model


class WaveformDataset(Dataset):
    def __init__(
        self,
        records: list[WaveformRecord],
        label_values: list[str],
        task_name: str,
        target_length: int,
        augment: bool,
        seed: int,
    ) -> None:
        self.records = records
        self.label_values = label_values
        self.label_to_index = {label: index for index, label in enumerate(label_values)}
        self.task_name = task_name
        self.target_length = target_length
        self.augment = augment
        self.rng = np.random.default_rng(seed)

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor]:
        record = self.records[index]
        x = record.waveform.copy()
        if self.augment:
            scale = self.rng.uniform(0.9, 1.1)
            noise = self.rng.normal(0.0, 0.015, size=x.shape).astype(np.float32)
            shift = int(self.rng.integers(-32, 33))
            x = np.roll(x * scale + noise, shift=shift, axis=1)
        x = _normalize_waveform(x)
        if self.task_name == "binary_normal_vs_fault":
            label = "normal" if record.label == "00" else "fault"
        else:
            label = record.label
        return torch.tensor(x, dtype=torch.float32), torch.tensor(self.label_to_index[label], dtype=torch.long)


def _normalize_waveform(x: np.ndarray) -> np.ndarray:
    mean = x.mean(axis=1, keepdims=True)
    std = x.std(axis=1, keepdims=True)
    return ((x - mean) / np.maximum(std, 1e-6)).astype(np.float32)


class CNN1D(nn.Module):
    def __init__(self, channels: int, classes: int) -> None:
        super().__init__()
        self.net = nn.Sequential(
            _conv_block(channels, 32, 7),
            _conv_block(32, 64, 5),
            _conv_block(64, 96, 5),
            _conv_block(96, 128, 3),
            nn.AdaptiveAvgPool1d(1),
        )
        self.head = nn.Sequential(nn.Flatten(), nn.Dropout(0.25), nn.Linear(128, classes))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.head(self.net(x))


class TCN1D(nn.Module):
    def __init__(self, channels: int, classes: int) -> None:
        super().__init__()
        self.input = nn.Conv1d(channels, 64, kernel_size=1)
        self.blocks = nn.Sequential(
            TCNBlock(64, dilation=1),
            TCNBlock(64, dilation=2),
            TCNBlock(64, dilation=4),
            TCNBlock(64, dilation=8),
            TCNBlock(64, dilation=16),
        )
        self.pool = nn.AdaptiveAvgPool1d(1)
        self.head = nn.Sequential(nn.Flatten(), nn.Dropout(0.25), nn.Linear(64, classes))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.input(x)
        x = self.blocks(x)
        return self.head(self.pool(x))


class TCNBlock(nn.Module):
    def __init__(self, channels: int, dilation: int) -> None:
        super().__init__()
        padding = dilation * 2
        self.net = nn.Sequential(
            nn.Conv1d(channels, channels, kernel_size=5, padding=padding, dilation=dilation),
            nn.BatchNorm1d(channels),
            nn.ReLU(),
            nn.Conv1d(channels, channels, kernel_size=3, padding=dilation, dilation=dilation),
            nn.BatchNorm1d(channels),
        )
        self.activation = nn.ReLU()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        y = self.net(x)
        if y.shape[-1] != x.shape[-1]:
            y = y[..., : x.shape[-1]]
        return self.activation(x + y)


def _conv_block(in_channels: int, out_channels: int, kernel_size: int) -> nn.Sequential:
    return nn.Sequential(
        nn.Conv1d(in_channels, out_channels, kernel_size=kernel_size, padding=kernel_size // 2),
        nn.BatchNorm1d(out_channels),
        nn.ReLU(),
        nn.MaxPool1d(2),
    )


def _make_model(model_name: str, channels: int, classes: int) -> nn.Module:
    if model_name == "tcn":
        return TCN1D(channels, classes)
    if model_name == "cnn":
        return CNN1D(channels, classes)
    raise ValueError(f"Unsupported model: {model_name}")


def _predict(model: nn.Module, loader: DataLoader) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    model.eval()
    truths: list[np.ndarray] = []
    probs: list[np.ndarray] = []
    with torch.no_grad():
        for batch_x, batch_y in loader:
            logits = model(batch_x)
            probabilities = torch.softmax(logits, dim=1).cpu().numpy()
            truths.append(batch_y.cpu().numpy())
            probs.append(probabilities)
    truth = np.concatenate(truths)
    probabilities = np.vstack(probs)
    predictions = np.argmax(probabilities, axis=1)
    return truth, predictions, probabilities


def _metric_row(
    signal_kind: str,
    task_name: str,
    model_name: str,
    label_values: list[str],
    truth: np.ndarray,
    predictions: np.ndarray,
    probabilities: np.ndarray,
    train_rows: int,
    test_rows: int,
    epochs: int,
) -> dict[str, Any]:
    return {
        "signal": signal_kind,
        "task": task_name,
        "model": model_name,
        "labels": ",".join(label_values),
        "train_rows": train_rows,
        "test_rows": test_rows,
        "epochs": epochs,
        "accuracy": float(accuracy_score(truth, predictions)),
        "macro_f1": float(f1_score(truth, predictions, average="macro", zero_division=0)),
        "weighted_f1": float(f1_score(truth, predictions, average="weighted", zero_division=0)),
        "top2_accuracy": _top_k_accuracy(truth, probabilities, k=2),
        "top3_accuracy": _top_k_accuracy(truth, probabilities, k=3),
    }


def _top_k_accuracy(truth: np.ndarray, probabilities: np.ndarray, k: int) -> float:
    k = min(k, probabilities.shape[1])
    ranked = np.argsort(probabilities, axis=1)[:, -k:]
    return float(np.mean([truth[index] in set(row) for index, row in enumerate(ranked)]))


def _format_metric(row: dict[str, Any]) -> str:
    return (
        f"{row['signal']} {row['task']} {row['model']} "
        f"acc={row['accuracy']:.3f} macro_f1={row['macro_f1']:.3f} "
        f"top2={row['top2_accuracy']:.3f} top3={row['top3_accuracy']:.3f}"
    )


def _make_report(
    zip_path: Path,
    records: list[WaveformRecord],
    benchmark: pd.DataFrame,
    saved_models: list[dict[str, Any]],
    args: argparse.Namespace,
) -> str:
    label_counts = pd.Series([record.label for record in records]).value_counts().sort_index().to_dict()
    group_count = len({record.group for record in records})
    lines = [
        "# AI-Hub Raw Waveform Deep Model Benchmark",
        "",
        "## Setting",
        "",
        f"- ZIP: `{zip_path}`",
        f"- Signal kind: `{args.signal_kind}`",
        f"- Loaded rows: `{len(records)}`",
        f"- Groups: `{group_count}`",
        f"- Target length: `{args.target_length}`",
        f"- Epochs: `{args.epochs}`",
        f"- CV folds: `{args.cv_folds}`",
        f"- Models: `{args.models}`",
        f"- Tasks: `{args.tasks}`",
        "",
        "## Label Distribution",
        "",
        "| Label | Name | Count |",
        "|---|---|---:|",
    ]
    for label, count in label_counts.items():
        lines.append(f"| {label} | {AIHUB_LABELS.get(label, label)} | {count} |")
    lines.extend(
        [
            "",
            "## Results",
            "",
            "| Fold | Task | Model | Accuracy | Macro F1 | Weighted F1 | Top-2 | Top-3 |",
            "|---:|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    for _, row in benchmark.iterrows():
        lines.append(
            f"| {int(row.get('fold', 1))} | {row['task']} | {row['model']} | {float(row['accuracy']):.3f} | "
            f"{float(row['macro_f1']):.3f} | {float(row['weighted_f1']):.3f} | "
            f"{float(row['top2_accuracy']):.3f} | {float(row['top3_accuracy']):.3f} |"
        )
    lines.extend(["", "## Saved Models", "", "| Task | Model | Path |", "|---|---|---|"])
    for item in saved_models:
        lines.append(f"| {item['task']} | {item['model']} | `{item['path']}` |")
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- This benchmark uses grouped holdout by asset group, not row split.",
            "- Raw waveform models use per-window z-score normalization and light augmentation: scaling, Gaussian noise, and time shift.",
            "- Compare against the tabular reference row in the same result table for this exact sample/split.",
            "",
        ]
    )
    return "\n".join(lines)


def _set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(max(1, min(8, torch.get_num_threads())))


def _first(values: list[str] | None) -> str:
    if not values:
        return ""
    return values[0]


def _to_float(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _extract_kw(value: object) -> float | None:
    import re

    match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*kW", str(value), re.IGNORECASE)
    if match:
        return float(match.group(1))
    return None


if __name__ == "__main__":
    main()
