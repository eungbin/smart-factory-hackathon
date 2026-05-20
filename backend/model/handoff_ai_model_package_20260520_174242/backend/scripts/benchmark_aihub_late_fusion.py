from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

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


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    parser = argparse.ArgumentParser(description="AI-Hub current+vibration decision-level late fusion benchmark.")
    parser.add_argument("--max-files", type=int, default=10000)
    parser.add_argument("--max-per-path-label", type=int, default=2000)
    parser.add_argument("--max-pairs", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", default="data/aihub238/aihub_current_vibration_late_fusion_benchmark.csv")
    parser.add_argument("--report-output", default="data/aihub238/aihub_current_vibration_late_fusion_report.md")
    parser.add_argument("--model-dir", default="data/models/aihub_late_fusion")
    args = parser.parse_args()

    rng = random.Random(args.seed)
    print("Loading current features...")
    current_frame = load_aihub_current_zip(
        find_default_aihub_current_zip(),
        max_files=args.max_files,
        max_per_path_label=args.max_per_path_label,
        seed=args.seed,
    )
    current_features, current_labels, current_groups = build_aihub_feature_table(
        current_frame,
        include_asset_baseline_features=True,
    )
    print("Loading vibration features...")
    vibration_frame = load_aihub_vibration_zip(
        find_default_aihub_vibration_zip(),
        max_files=args.max_files,
        max_per_path_label=args.max_per_path_label,
        seed=args.seed,
    )
    vibration_features, vibration_labels, vibration_groups = build_aihub_feature_table(
        vibration_frame,
        include_asset_baseline_features=True,
    )

    pairs = _make_pairs(
        current_labels=current_labels,
        current_groups=current_groups,
        vibration_labels=vibration_labels,
        vibration_groups=vibration_groups,
        max_pairs=args.max_pairs,
        rng=rng,
    )
    if pairs.empty:
        raise ValueError("No current/vibration pairs were created.")
    labels = pairs["label"].astype(str)
    groups = pairs["asset_group"].astype(str)
    y_multiclass = labels.map({label: index for index, label in enumerate(LABEL_ORDER)})
    y_binary = labels.map(lambda label: "normal" if label == "00" else "fault")
    train_index, test_index = _best_group_split(y_multiclass, groups, args.seed)
    print(
        f"paired_rows={len(pairs)} groups={groups.nunique()} "
        f"train/test={len(train_index)}/{len(test_index)}"
    )

    c_train = current_features.iloc[pairs.iloc[train_index]["current_index"].to_numpy()]
    c_test = current_features.iloc[pairs.iloc[test_index]["current_index"].to_numpy()]
    v_train = vibration_features.iloc[pairs.iloc[train_index]["vibration_index"].to_numpy()]
    v_test = vibration_features.iloc[pairs.iloc[test_index]["vibration_index"].to_numpy()]
    y_train_multi = y_multiclass.iloc[train_index].to_numpy()
    y_test_multi = y_multiclass.iloc[test_index].to_numpy()
    y_train_binary = y_binary.iloc[train_index]
    y_test_binary = y_binary.iloc[test_index]

    current_binary = RandomForestClassifier(
        n_estimators=400,
        min_samples_leaf=2,
        max_features="sqrt",
        class_weight="balanced_subsample",
        random_state=args.seed,
        n_jobs=-1,
    )
    vibration_multiclass = make_pipeline(
        StandardScaler(),
        LogisticRegression(max_iter=3000, class_weight="balanced", random_state=args.seed),
    )
    current_multiclass = RandomForestClassifier(
        n_estimators=400,
        min_samples_leaf=2,
        max_features="sqrt",
        class_weight="balanced_subsample",
        random_state=args.seed,
        n_jobs=-1,
    )
    vibration_rf_multiclass = RandomForestClassifier(
        n_estimators=400,
        min_samples_leaf=2,
        max_features="sqrt",
        class_weight="balanced_subsample",
        random_state=args.seed,
        n_jobs=-1,
    )

    current_binary.fit(c_train, y_train_binary)
    vibration_multiclass.fit(v_train, y_train_multi)
    current_multiclass.fit(c_train, y_train_multi)
    vibration_rf_multiclass.fit(v_train, y_train_multi)

    rows: list[dict[str, Any]] = []
    rows.append(_evaluate_multiclass("current_multiclass_rf", y_test_multi, _aligned_index_proba(current_multiclass, c_test, len(LABEL_ORDER))))
    rows.append(_evaluate_multiclass("vibration_multiclass_logreg", y_test_multi, _aligned_index_proba(vibration_multiclass, v_test, len(LABEL_ORDER))))
    rows.append(_evaluate_multiclass("vibration_multiclass_rf", y_test_multi, _aligned_index_proba(vibration_rf_multiclass, v_test, len(LABEL_ORDER))))

    binary_probs = _binary_prob_matrix(current_binary, c_test)
    vibration_probs = _aligned_index_proba(vibration_multiclass, v_test, len(LABEL_ORDER))
    hard_probs = _hard_gate_fusion(binary_probs, vibration_probs)
    soft_probs = _soft_fusion(binary_probs, vibration_probs, fault_weight=0.65)
    rows.append(_evaluate_multiclass("late_fusion_hard_gate", y_test_multi, hard_probs))
    rows.append(_evaluate_multiclass("late_fusion_soft_gate", y_test_multi, soft_probs))

    binary_pred = current_binary.predict(c_test)
    rows.append(
        {
            "model": "current_binary_rf",
            "task": "binary_normal_vs_fault",
            "accuracy": float(accuracy_score(y_test_binary, binary_pred)),
            "macro_f1": float(f1_score(y_test_binary, binary_pred, average="macro", zero_division=0)),
            "weighted_f1": float(f1_score(y_test_binary, binary_pred, average="weighted", zero_division=0)),
            "top2_accuracy": 1.0,
            "top3_accuracy": 1.0,
            "train_rows": int(len(train_index)),
            "test_rows": int(len(test_index)),
            "groups": int(groups.nunique()),
            "test_groups": int(groups.iloc[test_index].nunique()),
        }
    )

    for row in rows:
        row.setdefault("task", "multiclass_fault_type")
        row.setdefault("train_rows", int(len(train_index)))
        row.setdefault("test_rows", int(len(test_index)))
        row.setdefault("groups", int(groups.nunique()))
        row.setdefault("test_groups", int(groups.iloc[test_index].nunique()))
        print(_format_row(row))

    benchmark = pd.DataFrame(rows).sort_values(["task", "macro_f1"], ascending=[True, False])
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    benchmark.to_csv(output, index=False, encoding="utf-8-sig")

    model_dir = Path(args.model_dir)
    model_dir.mkdir(parents=True, exist_ok=True)
    model_paths = {
        "current_binary": str(model_dir / "current_binary_random_forest.joblib"),
        "vibration_multiclass": str(model_dir / "vibration_multiclass_logistic_regression.joblib"),
        "current_multiclass": str(model_dir / "current_multiclass_random_forest.joblib"),
        "vibration_rf_multiclass": str(model_dir / "vibration_multiclass_random_forest.joblib"),
    }
    joblib.dump(current_binary, model_paths["current_binary"])
    joblib.dump(vibration_multiclass, model_paths["vibration_multiclass"])
    joblib.dump(current_multiclass, model_paths["current_multiclass"])
    joblib.dump(vibration_rf_multiclass, model_paths["vibration_rf_multiclass"])

    report_output = Path(args.report_output)
    report_output.parent.mkdir(parents=True, exist_ok=True)
    report_output.write_text(
        _make_report(
            benchmark=benchmark,
            pairs=pairs,
            current_frame=current_frame,
            vibration_frame=vibration_frame,
            model_paths=model_paths,
            args=args,
        ),
        encoding="utf-8",
    )
    print("")
    print(f"benchmark_csv={output}")
    print(f"report_md={report_output}")
    for path in model_paths.values():
        print(f"model={path}")


def _make_pairs(
    current_labels: pd.Series,
    current_groups: pd.Series,
    vibration_labels: pd.Series,
    vibration_groups: pd.Series,
    max_pairs: int,
    rng: random.Random,
) -> pd.DataFrame:
    current_buckets: dict[tuple[str, str], list[int]] = {}
    vibration_buckets: dict[tuple[str, str], list[int]] = {}
    for index, (label, group) in enumerate(zip(current_labels.astype(str), current_groups.astype(str))):
        current_buckets.setdefault((group, label), []).append(index)
    for index, (label, group) in enumerate(zip(vibration_labels.astype(str), vibration_groups.astype(str))):
        vibration_buckets.setdefault((group, label), []).append(index)

    rows: list[dict[str, Any]] = []
    for key in sorted(set(current_buckets) & set(vibration_buckets)):
        c_indices = current_buckets[key][:]
        v_indices = vibration_buckets[key][:]
        rng.shuffle(c_indices)
        rng.shuffle(v_indices)
        count = min(len(c_indices), len(v_indices))
        group, label = key
        for c_index, v_index in zip(c_indices[:count], v_indices[:count]):
            rows.append(
                {
                    "asset_group": group,
                    "label": label,
                    "current_index": c_index,
                    "vibration_index": v_index,
                }
            )
    rng.shuffle(rows)
    if len(rows) > max_pairs:
        rows = rows[:max_pairs]
    return pd.DataFrame(rows)


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


def _aligned_proba(model: Any, features: pd.DataFrame, class_order: list[str]) -> np.ndarray:
    proba = model.predict_proba(features)
    classes = [str(item) for item in model.classes_] if hasattr(model, "classes_") else [str(item) for item in model[-1].classes_]
    out = np.zeros((len(features), len(class_order)), dtype=float)
    for source_index, class_name in enumerate(classes):
        out[:, class_order.index(class_name)] = proba[:, source_index]
    row_sum = out.sum(axis=1, keepdims=True)
    return out / np.maximum(row_sum, 1e-12)


def _aligned_index_proba(model: Any, features: pd.DataFrame, class_count: int) -> np.ndarray:
    proba = model.predict_proba(features)
    classes = model.classes_ if hasattr(model, "classes_") else model[-1].classes_
    out = np.zeros((len(features), class_count), dtype=float)
    for source_index, class_value in enumerate(classes):
        class_index = int(class_value)
        if 0 <= class_index < class_count:
            out[:, class_index] = proba[:, source_index]
    row_sum = out.sum(axis=1, keepdims=True)
    return out / np.maximum(row_sum, 1e-12)


def _binary_prob_matrix(model: Any, features: pd.DataFrame) -> np.ndarray:
    proba = model.predict_proba(features)
    classes = [str(item) for item in model.classes_]
    out = np.zeros((len(features), 2), dtype=float)
    for source_index, class_name in enumerate(classes):
        if class_name == "normal":
            out[:, 0] = proba[:, source_index]
        elif class_name == "fault":
            out[:, 1] = proba[:, source_index]
    row_sum = out.sum(axis=1, keepdims=True)
    return out / np.maximum(row_sum, 1e-12)


def _hard_gate_fusion(binary_probs: np.ndarray, vibration_probs: np.ndarray) -> np.ndarray:
    out = np.zeros_like(vibration_probs)
    normal_mask = binary_probs[:, 0] >= binary_probs[:, 1]
    out[normal_mask, 0] = 1.0
    fault_mask = ~normal_mask
    fault_probs = vibration_probs[fault_mask, 1:]
    fault_probs = fault_probs / np.maximum(fault_probs.sum(axis=1, keepdims=True), 1e-12)
    out[fault_mask, 1:] = fault_probs
    return out


def _soft_fusion(binary_probs: np.ndarray, vibration_probs: np.ndarray, fault_weight: float) -> np.ndarray:
    out = np.zeros_like(vibration_probs)
    fault_probs = vibration_probs[:, 1:]
    fault_probs = fault_probs / np.maximum(fault_probs.sum(axis=1, keepdims=True), 1e-12)
    out[:, 0] = (1.0 - fault_weight) * vibration_probs[:, 0] + fault_weight * binary_probs[:, 0]
    out[:, 1:] = (1.0 - fault_weight) * vibration_probs[:, 1:] + fault_weight * binary_probs[:, [1]] * fault_probs
    return out / np.maximum(out.sum(axis=1, keepdims=True), 1e-12)


def _evaluate_multiclass(model_name: str, truth: np.ndarray, probabilities: np.ndarray) -> dict[str, Any]:
    predictions = np.argmax(probabilities, axis=1)
    return {
        "model": model_name,
        "task": "multiclass_fault_type",
        "accuracy": float(accuracy_score(truth, predictions)),
        "macro_f1": float(f1_score(truth, predictions, average="macro", zero_division=0)),
        "weighted_f1": float(f1_score(truth, predictions, average="weighted", zero_division=0)),
        "top2_accuracy": _top_k_accuracy(truth, probabilities, 2),
        "top3_accuracy": _top_k_accuracy(truth, probabilities, 3),
    }


def _top_k_accuracy(truth: np.ndarray, probabilities: np.ndarray, k: int) -> float:
    k = min(k, probabilities.shape[1])
    ranked = np.argsort(probabilities, axis=1)[:, -k:]
    return float(np.mean([truth[index] in set(row) for index, row in enumerate(ranked)]))


def _format_row(row: dict[str, Any]) -> str:
    return (
        f"{row['task']} {row['model']} acc={row['accuracy']:.3f} "
        f"macro_f1={row['macro_f1']:.3f} top2={row['top2_accuracy']:.3f} top3={row['top3_accuracy']:.3f}"
    )


def _make_report(
    benchmark: pd.DataFrame,
    pairs: pd.DataFrame,
    current_frame: pd.DataFrame,
    vibration_frame: pd.DataFrame,
    model_paths: dict[str, str],
    args: argparse.Namespace,
) -> str:
    lines = [
        "# AI-Hub Current + Vibration Late Fusion Benchmark",
        "",
        "## Purpose",
        "",
        "Evaluate an MVP decision-level fusion strategy: current detects normal/fault, vibration ranks fault-type candidates.",
        "",
        "## Important Pairing Note",
        "",
        "AI-Hub current.zip and vibration.zip are separate bundles and are not guaranteed to be simultaneous sensor captures.",
        "For this benchmark, samples are paired by same asset_group and same label. This tests the decision strategy, not exact synchronized multimodal sensing.",
        "",
        "## Setting",
        "",
        f"- Current rows loaded: `{len(current_frame)}`",
        f"- Vibration rows loaded: `{len(vibration_frame)}`",
        f"- Paired rows: `{len(pairs)}`",
        f"- Groups: `{pairs['asset_group'].nunique()}`",
        f"- Max files per modality: `{args.max_files}`",
        f"- Max per label path: `{args.max_per_path_label}`",
        "",
        "## Results",
        "",
        "| Task | Model | Accuracy | Macro F1 | Weighted F1 | Top-2 | Top-3 |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for _, row in benchmark.iterrows():
        lines.append(
            f"| {row['task']} | {row['model']} | {float(row['accuracy']):.3f} | "
            f"{float(row['macro_f1']):.3f} | {float(row['weighted_f1']):.3f} | "
            f"{float(row['top2_accuracy']):.3f} | {float(row['top3_accuracy']):.3f} |"
        )
    lines.extend(["", "## Saved Models", "", "| Role | Path |", "|---|---|"])
    for role, path in model_paths.items():
        lines.append(f"| {role} | `{path}` |")
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- Hard gate is conservative: if current predicts normal, final class is normal.",
            "- Soft gate blends current normal/fault probability with vibration fault-type probabilities.",
            "- For MVP, use this as a product decision policy, while still labeling fault type as ranked candidates.",
            "",
        ]
    )
    return "\n".join(lines)


if __name__ == "__main__":
    main()
