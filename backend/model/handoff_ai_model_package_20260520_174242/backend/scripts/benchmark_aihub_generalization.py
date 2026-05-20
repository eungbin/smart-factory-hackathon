from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, classification_report, f1_score
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.aihub import (  # noqa: E402
    AIHUB_LABELS,
    build_aihub_feature_table,
    find_default_aihub_current_zip,
    find_default_aihub_vibration_zip,
    inspect_aihub_current_zip,
    load_aihub_current_zip,
    load_aihub_vibration_zip,
    summarize_aihub,
)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    parser = argparse.ArgumentParser(description="AI-Hub 238 unseen-asset generalization benchmark.")
    parser.add_argument("--zip-path", default="", help="Path to current.zip. Auto-detected when omitted.")
    parser.add_argument("--signal-kind", choices=["current", "vibration"], default="current")
    parser.add_argument("--max-files", type=int, default=10000)
    parser.add_argument("--max-per-path-label", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--output", default="data/aihub238/aihub_current_generalization_cv.csv")
    parser.add_argument("--report-output", default="data/aihub238/aihub_current_generalization_cv_report.md")
    parser.add_argument("--model-dir", default="data/models/aihub_generalization")
    parser.add_argument(
        "--feature-mode",
        choices=["raw", "asset_baseline", "both"],
        default="asset_baseline",
        help="raw uses only extracted signal stats; asset_baseline adds per-asset normal-baseline deltas.",
    )
    args = parser.parse_args()

    zip_path = Path(args.zip_path) if args.zip_path else _find_default_zip(args.signal_kind)
    zip_info = inspect_aihub_current_zip(zip_path)
    frame = _load_signal_zip(
        args.signal_kind,
        zip_path,
        max_files=args.max_files,
        max_per_path_label=args.max_per_path_label,
        seed=args.seed,
    )
    summary = summarize_aihub(frame)

    feature_modes = ["raw", "asset_baseline"] if args.feature_mode == "both" else [args.feature_mode]
    models = _models(args.seed)
    rows: list[dict[str, Any]] = []
    reports: dict[str, Any] = {}
    best_models: list[dict[str, Any]] = []

    for feature_mode in feature_modes:
        include_baseline = feature_mode == "asset_baseline"
        features, labels, groups = build_aihub_feature_table(
            frame,
            include_asset_baseline_features=include_baseline,
        )
        tasks = _tasks(features, labels, groups)
        for task_name, task in tasks.items():
            task_features = task["features"]
            y = task["labels"]
            task_groups = task["groups"]
            label_set = sorted(y.astype(str).unique())
            for model_name, model in models.items():
                fold_rows: list[dict[str, Any]] = []
                for fold, (train_index, test_index) in enumerate(
                    _group_cv_splits(task_features, y, task_groups, args.folds, args.seed),
                    start=1,
                ):
                    estimator = clone(model)
                    estimator.fit(task_features.iloc[train_index], y.iloc[train_index])
                    predictions = estimator.predict(task_features.iloc[test_index])
                    probabilities = (
                        estimator.predict_proba(task_features.iloc[test_index])
                        if hasattr(estimator, "predict_proba")
                        else None
                    )
                    report = classification_report(
                        y.iloc[test_index],
                        predictions,
                        labels=label_set,
                        zero_division=0,
                        output_dict=True,
                    )
                    row = {
                        "feature_mode": feature_mode,
                        "task": task_name,
                        "model": model_name,
                        "fold": fold,
                        "rows": int(len(task_features)),
                        "features": int(task_features.shape[1]),
                        "train_rows": int(len(train_index)),
                        "test_rows": int(len(test_index)),
                        "train_groups": int(task_groups.iloc[train_index].nunique()),
                        "test_groups": int(task_groups.iloc[test_index].nunique()),
                        "test_label_count": int(y.iloc[test_index].nunique()),
                        "accuracy": float(accuracy_score(y.iloc[test_index], predictions)),
                        "balanced_accuracy": float(balanced_accuracy_score(y.iloc[test_index], predictions)),
                        "macro_f1": float(
                            f1_score(y.iloc[test_index], predictions, labels=label_set, average="macro", zero_division=0)
                        ),
                        "weighted_f1": float(
                            f1_score(y.iloc[test_index], predictions, labels=label_set, average="weighted", zero_division=0)
                        ),
                        "top2_accuracy": _top_k_accuracy(y.iloc[test_index], probabilities, estimator, k=2),
                        "top3_accuracy": _top_k_accuracy(y.iloc[test_index], probabilities, estimator, k=3),
                    }
                    fold_rows.append(row)
                    reports[f"{feature_mode}/{task_name}/{model_name}/fold_{fold}"] = report
                    print(_format_row(row))
                rows.extend(fold_rows)

    results = pd.DataFrame(rows)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(output, index=False, encoding="utf-8-sig")
    summary_table = _summarize_results(results)
    best_models = _save_best_models(frame, summary_table, models, args)

    report_output = Path(args.report_output)
    report_output.parent.mkdir(parents=True, exist_ok=True)
    report_output.write_text(
        _make_report(
            zip_path=zip_path,
            zip_info=zip_info,
            data_summary=summary,
            results=results,
            summary_table=summary_table,
            reports=reports,
            best_models=best_models,
            args=args,
        ),
        encoding="utf-8",
    )

    print("")
    print(f"cv_csv={output}")
    print(f"report_md={report_output}")
    for item in best_models:
        print(f"model={item['path']}")


def _models(seed: int) -> dict[str, Any]:
    return {
        "logistic_regression": make_pipeline(
            StandardScaler(),
            LogisticRegression(max_iter=3000, class_weight="balanced", random_state=seed),
        ),
        "random_forest": RandomForestClassifier(
            n_estimators=350,
            min_samples_leaf=2,
            max_features="sqrt",
            class_weight="balanced_subsample",
            random_state=seed,
            n_jobs=-1,
        ),
        "extra_trees": ExtraTreesClassifier(
            n_estimators=500,
            min_samples_leaf=2,
            max_features=0.6,
            class_weight="balanced",
            random_state=seed,
            n_jobs=-1,
        ),
        "hist_gradient_boosting": HistGradientBoostingClassifier(
            learning_rate=0.07,
            max_iter=250,
            max_leaf_nodes=31,
            l2_regularization=0.03,
            early_stopping=True,
            random_state=seed,
            class_weight="balanced",
        ),
    }


def _find_default_zip(signal_kind: str) -> Path:
    if signal_kind == "vibration":
        return find_default_aihub_vibration_zip()
    return find_default_aihub_current_zip()


def _load_signal_zip(
    signal_kind: str,
    zip_path: Path,
    max_files: int | None,
    max_per_path_label: int | None,
    seed: int,
) -> pd.DataFrame:
    if signal_kind == "vibration":
        return load_aihub_vibration_zip(
            zip_path,
            max_files=max_files,
            max_per_path_label=max_per_path_label,
            seed=seed,
        )
    return load_aihub_current_zip(
        zip_path,
        max_files=max_files,
        max_per_path_label=max_per_path_label,
        seed=seed,
    )


def _tasks(features: pd.DataFrame, labels: pd.Series, groups: pd.Series) -> dict[str, dict[str, Any]]:
    fault_mask = labels != "00"
    return {
        "binary_normal_vs_fault": {
            "features": features,
            "labels": labels.map(lambda value: "normal" if value == "00" else "fault"),
            "groups": groups,
        },
        "multiclass_fault_type": {
            "features": features,
            "labels": labels,
            "groups": groups,
        },
        "fault_type_only": {
            "features": features.loc[fault_mask].reset_index(drop=True),
            "labels": labels.loc[fault_mask].reset_index(drop=True),
            "groups": groups.loc[fault_mask].reset_index(drop=True),
        },
    }


def _group_cv_splits(
    features: pd.DataFrame,
    labels: pd.Series,
    groups: pd.Series,
    folds: int,
    seed: int,
):
    n_splits = min(folds, groups.nunique())
    if n_splits < 2:
        raise ValueError("Need at least two asset groups for group CV.")
    splitter = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    return splitter.split(features, labels, groups)


def _top_k_accuracy(y_true: pd.Series, probabilities: np.ndarray | None, estimator: Any, k: int) -> float | None:
    if probabilities is None or not hasattr(estimator, "classes_"):
        return None
    classes = np.asarray(estimator.classes_)
    if probabilities.shape[1] <= 1:
        return None
    k = min(k, probabilities.shape[1])
    ranked_indices = np.argsort(probabilities, axis=1)[:, -k:]
    ranked_labels = classes[ranked_indices]
    truth = y_true.astype(str).to_numpy()
    return float(np.mean([truth[index] in set(row.astype(str)) for index, row in enumerate(ranked_labels)]))


def _summarize_results(results: pd.DataFrame) -> pd.DataFrame:
    numeric_columns = [
        "accuracy",
        "balanced_accuracy",
        "macro_f1",
        "weighted_f1",
        "top2_accuracy",
        "top3_accuracy",
        "test_label_count",
    ]
    grouped = (
        results.groupby(["feature_mode", "task", "model"], dropna=False)[numeric_columns]
        .agg(["mean", "std", "min", "max"])
        .reset_index()
    )
    grouped.columns = [
        "_".join([item for item in column if item]).rstrip("_")
        if isinstance(column, tuple)
        else str(column)
        for column in grouped.columns
    ]
    return grouped.sort_values(["task", "macro_f1_mean"], ascending=[True, False])


def _save_best_models(
    frame: pd.DataFrame,
    summary_table: pd.DataFrame,
    models: dict[str, Any],
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    model_dir = Path(args.model_dir)
    model_dir.mkdir(parents=True, exist_ok=True)
    saved: list[dict[str, Any]] = []
    for task_name in ["binary_normal_vs_fault", "fault_type_only", "multiclass_fault_type"]:
        candidates = summary_table[summary_table["task"] == task_name].sort_values("macro_f1_mean", ascending=False)
        if candidates.empty:
            continue
        selected = candidates.iloc[0]
        feature_mode = str(selected["feature_mode"])
        model_name = str(selected["model"])
        features, labels, groups = build_aihub_feature_table(
            frame,
            include_asset_baseline_features=feature_mode == "asset_baseline",
        )
        task = _tasks(features, labels, groups)[task_name]
        estimator = clone(models[model_name])
        estimator.fit(task["features"], task["labels"])
        path = model_dir / f"{task_name}_{feature_mode}_{model_name}.joblib"
        payload = {
            "model": estimator,
            "model_name": model_name,
            "task": task_name,
            "feature_mode": feature_mode,
            "feature_columns": list(task["features"].columns),
            "label_names": AIHUB_LABELS,
            "group_cv_metrics": selected.to_dict(),
            "seed": int(args.seed),
            "source": "AI-Hub 238 current.zip group-CV generalization benchmark",
        }
        joblib.dump(payload, path)
        saved.append(
            {
                "path": str(path),
                "task": task_name,
                "feature_mode": feature_mode,
                "model": model_name,
                "macro_f1_mean": float(selected["macro_f1_mean"]),
                "accuracy_mean": float(selected["accuracy_mean"]),
                "top2_accuracy_mean": _optional_float(selected.get("top2_accuracy_mean")),
                "top3_accuracy_mean": _optional_float(selected.get("top3_accuracy_mean")),
            }
        )
    return saved


def _optional_float(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def _format_row(row: dict[str, Any]) -> str:
    return (
        f"{row['feature_mode']:>14} {row['task']:>24} {row['model']:>22} fold={row['fold']} "
        f"acc={row['accuracy']:.3f} macro_f1={row['macro_f1']:.3f} "
        f"top2={_metric(row['top2_accuracy'])} top3={_metric(row['top3_accuracy'])}"
    )


def _make_report(
    zip_path: Path,
    zip_info: dict[str, Any],
    data_summary: Any,
    results: pd.DataFrame,
    summary_table: pd.DataFrame,
    reports: dict[str, Any],
    best_models: list[dict[str, Any]],
    args: argparse.Namespace,
) -> str:
    lines = [
        "# AI-Hub Current 미지 설비 일반화 실험",
        "",
        "## 목적",
        "",
        "row split 성능이 아니라 설비 그룹을 분리한 group-CV 기준으로 분류모델의 미지 설비 일반화 성능을 확인한다.",
        "",
        "## Row Split과 Group Split",
        "",
        "| 방식 | 의미 | 사용 목적 |",
        "|---|---|---|",
        "| row split | 개별 CSV 행을 무작위로 train/test 분리 | 같은 설비가 양쪽에 섞일 수 있어 성능 상한선 확인용 |",
        "| group split / group-CV | 설비 ID를 기준으로 train/test 분리 | 처음 보는 설비에 대한 일반화 평가용 |",
        "",
        "## 데이터 설정",
        "",
        f"- ZIP: `{zip_path}`",
        f"- Signal kind: `{args.signal_kind}`",
        f"- ZIP size: `{zip_info['zip_size_bytes'] / (1024 ** 3):.2f} GB`",
        f"- CSV count in ZIP: `{zip_info['csv_count']}`",
        f"- Parsed sample rows: `{data_summary.rows}`",
        f"- Max files: `{args.max_files}`",
        f"- Max per path label: `{args.max_per_path_label}`",
        f"- Seed: `{args.seed}`",
        f"- Folds: `{args.folds}`",
        f"- Feature mode: `{args.feature_mode}`",
        "",
        "## 라벨 분포",
        "",
        "| Label | Name | Count |",
        "|---|---|---:|",
    ]
    for label, count in data_summary.label_counts.items():
        lines.append(f"| {label} | {AIHUB_LABELS.get(label, label)} | {count} |")

    lines.extend(
        [
            "",
            "## Group-CV 평균 성능",
            "",
            "| Feature | Task | Model | Accuracy mean | Macro F1 mean | Macro F1 std | Top-2 mean | Top-3 mean |",
            "|---|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    for _, row in summary_table.iterrows():
        lines.append(
            f"| {row['feature_mode']} | {row['task']} | {row['model']} | "
            f"{float(row['accuracy_mean']):.3f} | {float(row['macro_f1_mean']):.3f} | "
            f"{float(row['macro_f1_std']):.3f} | "
            f"{_metric(row.get('top2_accuracy_mean'))} | {_metric(row.get('top3_accuracy_mean'))} |"
        )

    lines.extend(
        [
            "",
            "## 저장된 Group-CV 기준 모델",
            "",
            "| Task | Feature | Model | Macro F1 mean | Path |",
            "|---|---|---|---:|---|",
        ]
    )
    for item in best_models:
        lines.append(
            f"| {item['task']} | {item['feature_mode']} | {item['model']} | "
            f"{item['macro_f1_mean']:.3f} | `{item['path']}` |"
        )

    lines.extend(
        [
            "",
            "## 해석",
            "",
            "- 미지 설비 일반화 평가는 row split이 아니라 group-CV 결과를 기준으로 봐야 한다.",
            "- 정상/고장 이진분류는 설비가 바뀌어도 비교적 일반화 가능성이 있다.",
            "- 5-class 고장유형은 설비별 물리 특성과 고장 주입 조건에 강하게 의존하므로, 전류 데이터만으로는 미지 설비 일반화에 한계가 있다.",
            "- 실제 제품에서는 고장유형 top-1 확정보다 top-2/top-3 후보와 센서 근거를 함께 보여주는 방식이 안전하다.",
            "",
            "## 재현 명령",
            "",
            "```powershell",
            "$env:PYTHONPATH='backend'",
            (
                "python backend\\scripts\\benchmark_aihub_generalization.py "
                f"--signal-kind {args.signal_kind} "
                f"--max-files {args.max_files} --max-per-path-label {args.max_per_path_label} "
                f"--seed {args.seed} --folds {args.folds} --feature-mode {args.feature_mode} "
                f"--output {args.output} --report-output {args.report_output} --model-dir {args.model_dir}"
            ),
            "```",
            "",
            "## Classification Reports JSON",
            "",
            "```json",
            json.dumps(reports, ensure_ascii=False, indent=2),
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def _metric(value: Any) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value):.3f}"


if __name__ == "__main__":
    main()
