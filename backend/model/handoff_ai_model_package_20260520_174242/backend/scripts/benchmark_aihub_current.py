from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import joblib
from sklearn.base import clone
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier, RandomForestClassifier, VotingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.model_selection import StratifiedGroupKFold, StratifiedShuffleSplit
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
    parser = argparse.ArgumentParser(description="Initial AI-Hub 238 current-signal classification benchmark.")
    parser.add_argument("--zip-path", default="", help="Path to current.zip. Auto-detected when omitted.")
    parser.add_argument("--signal-kind", choices=["current", "vibration"], default="current")
    parser.add_argument("--max-files", type=int, default=2500)
    parser.add_argument("--max-per-path-label", type=int, default=500)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", default="data/aihub238/aihub_current_initial_benchmark.csv")
    parser.add_argument("--report-output", default="data/aihub238/aihub_current_initial_report.md")
    parser.add_argument("--model-output", default="data/models/aihub_current_fault_classifier.joblib")
    parser.add_argument("--selection-task", default="multiclass_fault_type")
    parser.add_argument("--selection-split", default="row_stratified_upper_bound")
    parser.add_argument(
        "--no-asset-baseline-features",
        action="store_true",
        help="Disable per-asset normal-baseline delta features.",
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
    features, labels, groups = build_aihub_feature_table(
        frame,
        include_asset_baseline_features=not args.no_asset_baseline_features,
    )

    fault_mask = labels != "00"
    tasks = {
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
    splitters = {
        "row_stratified_upper_bound": _row_stratified_split,
        "asset_group_stratified": _asset_group_stratified_split,
    }
    models = _models(args.seed)

    rows: list[dict[str, object]] = []
    reports: dict[str, object] = {}
    for task_name, task_data in tasks.items():
        task_features = task_data["features"]
        y = task_data["labels"]
        task_groups = task_data["groups"]
        for split_name, split_fn in splitters.items():
            train_index, test_index = split_fn(task_features, y, task_groups, args.seed)
            for model_name, model in models.items():
                estimator = clone(model)
                estimator.fit(task_features.iloc[train_index], y.iloc[train_index])
                predictions = estimator.predict(task_features.iloc[test_index])
                report = classification_report(
                    y.iloc[test_index],
                    predictions,
                    zero_division=0,
                    output_dict=True,
                )
                row = {
                    "task": task_name,
                    "split": split_name,
                    "model": model_name,
                    "rows": int(len(task_features)),
                    "features": int(task_features.shape[1]),
                    "train_rows": int(len(train_index)),
                    "test_rows": int(len(test_index)),
                    "train_groups": int(task_groups.iloc[train_index].nunique()),
                    "test_groups": int(task_groups.iloc[test_index].nunique()),
                    "accuracy": float(accuracy_score(y.iloc[test_index], predictions)),
                    "macro_f1": float(f1_score(y.iloc[test_index], predictions, average="macro", zero_division=0)),
                    "weighted_f1": float(f1_score(y.iloc[test_index], predictions, average="weighted", zero_division=0)),
                }
                rows.append(row)
                reports[f"{task_name}/{split_name}/{model_name}"] = report
                print(_format_row(row))

    benchmark = pd.DataFrame(rows).sort_values(["task", "split", "macro_f1"], ascending=[True, True, False])
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    benchmark.to_csv(output, index=False, encoding="utf-8-sig")
    saved_model = _save_selected_model(
        benchmark=benchmark,
        models=models,
        tasks=tasks,
        args=args,
    )

    report_output = Path(args.report_output)
    report_output.parent.mkdir(parents=True, exist_ok=True)
    report_output.write_text(
        _make_report_v2(
            zip_path=zip_path,
            zip_info=zip_info,
            summary=summary,
            features=features,
            benchmark=benchmark,
            reports=reports,
            args=args,
            saved_model=saved_model,
        ),
        encoding="utf-8",
    )

    print("")
    print(f"benchmark_csv={output}")
    print(f"report_md={report_output}")
    if saved_model:
        print(f"model={saved_model['path']}")


def _models(seed: int) -> dict[str, object]:
    extra_trees_deep = ExtraTreesClassifier(
        n_estimators=600,
        min_samples_leaf=1,
        max_features="sqrt",
        class_weight="balanced",
        random_state=seed,
        n_jobs=-1,
    )
    random_forest_deep = RandomForestClassifier(
        n_estimators=500,
        min_samples_leaf=1,
        max_features="sqrt",
        class_weight="balanced_subsample",
        random_state=seed,
        n_jobs=-1,
    )
    hist_gradient = HistGradientBoostingClassifier(
        learning_rate=0.07,
        max_iter=250,
        max_leaf_nodes=31,
        l2_regularization=0.03,
        early_stopping=True,
        random_state=seed,
        class_weight="balanced",
    )
    return {
        "logistic_regression": make_pipeline(
            StandardScaler(),
            LogisticRegression(max_iter=2000, class_weight="balanced", random_state=seed),
        ),
        "random_forest_deep": random_forest_deep,
        "extra_trees_deep": extra_trees_deep,
        "extra_trees_smooth": ExtraTreesClassifier(
            n_estimators=700,
            min_samples_leaf=2,
            max_features=0.6,
            class_weight="balanced",
            random_state=seed,
            n_jobs=-1,
        ),
        "hist_gradient_boosting": hist_gradient,
        "soft_voting_tree": VotingClassifier(
            estimators=[
                ("extra_trees", extra_trees_deep),
                ("random_forest", random_forest_deep),
                ("hist_gradient", hist_gradient),
            ],
            voting="soft",
            weights=[2, 1, 1],
            n_jobs=-1,
        ),
        # Kept for continuity with the first baseline reports.
        "random_forest_baseline": RandomForestClassifier(
            n_estimators=200,
            min_samples_leaf=2,
            class_weight="balanced",
            random_state=seed,
            n_jobs=-1,
        ),
        "extra_trees_baseline": ExtraTreesClassifier(
            n_estimators=300,
            min_samples_leaf=2,
            class_weight="balanced",
            random_state=seed,
            n_jobs=-1,
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


def _row_stratified_split(features: pd.DataFrame, labels: pd.Series, groups: pd.Series, seed: int) -> tuple[np.ndarray, np.ndarray]:
    splitter = StratifiedShuffleSplit(n_splits=1, test_size=0.25, random_state=seed)
    return next(splitter.split(features, labels))


def _asset_group_stratified_split(
    features: pd.DataFrame,
    labels: pd.Series,
    groups: pd.Series,
    seed: int,
) -> tuple[np.ndarray, np.ndarray]:
    unique_groups = groups.nunique()
    n_splits = min(5, unique_groups)
    if n_splits < 2:
        return _row_stratified_split(features, labels, groups, seed)

    required_labels = set(labels.astype(str).unique())
    best_split: tuple[np.ndarray, np.ndarray] | None = None
    best_score: tuple[float, float, float, float] | None = None
    # Try deterministic seed variants. The score uses only label coverage and
    # split balance, not model predictions, so the test labels are not used for
    # model selection.
    for offset in range(25):
        splitter = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=seed + offset)
        for train_index, test_index in splitter.split(features, labels, groups):
            train_labels = labels.iloc[train_index].astype(str)
            test_labels = labels.iloc[test_index].astype(str)
            train_counts = train_labels.value_counts().reindex(sorted(required_labels), fill_value=0)
            test_counts = test_labels.value_counts().reindex(sorted(required_labels), fill_value=0)
            coverage = float((train_counts > 0).sum() + (test_counts > 0).sum())
            min_test_count = float(test_counts.min())
            test_ratio = len(test_index) / len(features)
            balance = -float(test_counts.std(ddof=0))
            size_penalty = -abs(test_ratio - 0.2)
            score = (coverage, min_test_count, balance, size_penalty)
            if best_score is None or score > best_score:
                best_score = score
                best_split = (train_index, test_index)
    if best_split is None:
        raise ValueError("Could not build a group-stratified split.")
    return best_split


def _format_row(row: dict[str, object]) -> str:
    return (
        f"{row['task']:>24} {row['split']:>26} {row['model']:>20} "
        f"acc={float(row['accuracy']):.3f} macro_f1={float(row['macro_f1']):.3f} "
        f"groups={int(row['train_groups'])}/{int(row['test_groups'])}"
    )


def _save_selected_model(
    benchmark: pd.DataFrame,
    models: dict[str, object],
    tasks: dict[str, dict[str, pd.DataFrame | pd.Series]],
    args: argparse.Namespace,
) -> dict[str, object] | None:
    if not args.model_output:
        return None
    candidates = benchmark[
        (benchmark["task"] == args.selection_task)
        & (benchmark["split"] == args.selection_split)
    ].copy()
    if candidates.empty:
        candidates = benchmark[benchmark["task"] == args.selection_task].copy()
    if candidates.empty:
        candidates = benchmark.copy()
    selected = candidates.sort_values("macro_f1", ascending=False).iloc[0]
    model_name = str(selected["model"])
    task_name = str(selected["task"])
    estimator = clone(models[model_name])
    task_features = tasks[task_name]["features"]
    target = tasks[task_name]["labels"]
    estimator.fit(task_features, target)
    model_output = Path(args.model_output)
    model_output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "model": estimator,
        "model_name": model_name,
        "task": task_name,
        "selection_split": str(selected["split"]),
        "feature_columns": list(task_features.columns),
        "label_names": AIHUB_LABELS,
        "metrics": {
            "accuracy": float(selected["accuracy"]),
            "macro_f1": float(selected["macro_f1"]),
            "weighted_f1": float(selected["weighted_f1"]),
            "rows": int(selected["rows"]),
            "features": int(selected["features"]),
        },
        "seed": int(args.seed),
        "source": "AI-Hub 238 Validation/current.zip enhanced current-signal benchmark",
    }
    joblib.dump(payload, model_output)
    return {
        "path": str(model_output),
        "model": model_name,
        "task": task_name,
        "split": str(selected["split"]),
        "accuracy": float(selected["accuracy"]),
        "macro_f1": float(selected["macro_f1"]),
        "weighted_f1": float(selected["weighted_f1"]),
    }


def _make_report(
    zip_path: Path,
    zip_info: dict[str, object],
    summary,
    features: pd.DataFrame,
    benchmark: pd.DataFrame,
    reports: dict[str, object],
    args: argparse.Namespace,
) -> str:
    lines = [
        "# AI-Hub 238 Current Dataset Initial Experiment Report",
        "",
        "## 실험 설정",
        "",
        f"- ZIP: `{zip_path}`",
        f"- Signal kind: `{args.signal_kind}`",
        f"- ZIP size: `{zip_info['zip_size_bytes'] / (1024 ** 3):.2f} GB`",
        f"- CSV count in ZIP: `{zip_info['csv_count']}`",
        f"- Parsed sample rows: `{summary.rows}`",
        f"- Max files: `{args.max_files}`",
        f"- Max per path label: `{args.max_per_path_label}`",
        f"- Seed: `{args.seed}`",
        f"- Feature count: `{features.shape[1]}`",
        f"- Feature columns: `{', '.join(features.columns)}`",
        f"- Asset baseline features: `{not args.no_asset_baseline_features}`",
        "",
        "## 라벨 분포",
        "",
        "| Label | Name | Count |",
        "|---|---|---:|",
    ]
    for label, count in summary.label_counts.items():
        lines.append(f"| {label} | {AIHUB_LABELS.get(label, label)} | {count} |")

    lines.extend(
        [
            "",
            "## 벤치마크 결과",
            "",
            "| Task | Split | Model | Accuracy | Macro F1 | Weighted F1 | Train/Test Rows | Train/Test Groups |",
            "|---|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    for _, row in benchmark.iterrows():
        lines.append(
            f"| {row['task']} | {row['split']} | {row['model']} | "
            f"{float(row['accuracy']):.3f} | {float(row['macro_f1']):.3f} | {float(row['weighted_f1']):.3f} | "
            f"{int(row['train_rows'])}/{int(row['test_rows'])} | {int(row['train_groups'])}/{int(row['test_groups'])} |"
        )

    best = benchmark.sort_values("macro_f1", ascending=False).iloc[0]
    lines.extend(
        [
            "",
            "## 현재 최고 후보",
            "",
            f"- Task: `{best['task']}`",
            f"- Split: `{best['split']}`",
            f"- Model: `{best['model']}`",
            f"- Accuracy: `{float(best['accuracy']):.3f}`",
            f"- Macro F1: `{float(best['macro_f1']):.3f}`",
            "",
            "## 주의",
            "",
            "- `row_stratified_upper_bound`는 같은 설비의 유사 파일이 train/test에 동시에 들어갈 수 있어 실제 일반화 성능보다 높게 나올 수 있다.",
            "- `asset_group_stratified`는 설비 그룹을 분리하므로 더 현실적인 검증이지만, sample 수가 작으면 label 분포가 불안정할 수 있다.",
            "- AI-Hub current 데이터는 RUL label이 아니라 상태 label이므로, 이 실험은 RUL 회귀가 아니라 상태/고장유형 분류 실험이다.",
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


def _make_report_v2(
    zip_path: Path,
    zip_info: dict[str, object],
    summary,
    features: pd.DataFrame,
    benchmark: pd.DataFrame,
    reports: dict[str, object],
    args: argparse.Namespace,
    saved_model: dict[str, object] | None = None,
) -> str:
    lines = [
        "# AI-Hub 238 전류 데이터 초기 실험 리포트",
        "",
        "## 실험 설정",
        "",
        f"- ZIP: `{zip_path}`",
        f"- ZIP size: `{zip_info['zip_size_bytes'] / (1024 ** 3):.2f} GB`",
        f"- CSV count in ZIP: `{zip_info['csv_count']}`",
        f"- Parsed sample rows: `{summary.rows}`",
        f"- Max files: `{args.max_files}`",
        f"- Max per path label: `{args.max_per_path_label}`",
        f"- Seed: `{args.seed}`",
        f"- Feature count: `{features.shape[1]}`",
        f"- Feature columns: `{', '.join(features.columns)}`",
        "",
        "## 초기값을 이렇게 둔 이유",
        "",
        "| 설정 | 초기값 | 이유 |",
        "|---|---:|---|",
        "| 사용 파일 | `Validation/current.zip` | 확보된 AI-Hub 묶음 중 가장 작고, 전류 기반 상태 분류 파이프라인을 먼저 검증하기 좋습니다. |",
        f"| 샘플 수 | `{args.max_files}` | 전체 `{zip_info['csv_count']}`개 CSV를 바로 처리하기 전에 feature 추출, split, 모델 학습, 리포트 생성을 빠르게 확인하기 위한 크기입니다. |",
        f"| 라벨별 최대 샘플 | `{args.max_per_path_label}` | 정상/고장 라벨 불균형을 줄여 accuracy가 한쪽 라벨에 끌려가지 않게 하고 macro F1을 안정적으로 보기 위한 균형 샘플링입니다. |",
        f"| random seed | `{args.seed}` | 같은 ZIP과 같은 옵션이면 동일한 샘플과 split을 재현하기 위한 고정값입니다. |",
        "| 입력 feature | metadata + 전류 시간/주파수/3상 불균형 통계 | 원시 파형을 직접 딥러닝에 넣기 전, 설명 가능하면서 빠른 tabular feature로 성능 상한을 먼저 끌어올리기 위한 설정입니다. RMS, crest factor, spectral ratio, phase imbalance는 작업지시서 근거로 연결하기 쉽습니다. |",
        f"| 설비별 정상 baseline feature | `{not args.no_asset_baseline_features}` | 실제 현장에서는 설비별 정상 운전 기준선을 먼저 잡을 수 있으므로, raw 전류값뿐 아니라 정상 대비 변화량을 함께 학습시켜 모터 크기와 설비별 스케일 차이를 줄입니다. |",
        "| binary task | 정상 vs 고장 | MVP 알림 흐름에서는 먼저 위험 여부를 안정적으로 구분하는 것이 가장 직접적인 가치입니다. |",
        "| multiclass task | 5개 상태 라벨 | 고장 유형별 조치 추천과 작업지시서 문구를 분기하기 위한 다음 단계입니다. |",
        "| row split | 25% test | 같은 설비/유사 파일이 train과 test에 함께 들어갈 수 있어 성능 상한선을 확인하는 용도입니다. 운영 성능으로 해석하면 안 됩니다. |",
        "| asset-group split | 5-fold group holdout | 설비 그룹을 분리해 처음 보는 설비에 대한 일반화 가능성을 확인하는 더 현실적인 검증입니다. |",
        "| baseline models | Logistic Regression, RandomForest, ExtraTrees, HistGradientBoosting, Soft Voting | 선형 기준선과 tree/boosting/앙상블을 같이 두면 feature가 단순 선형으로 충분한지, 비선형 tabular 모델이나 앙상블이 필요한지 비교할 수 있습니다. |",
        "| metrics | Accuracy, Macro F1, Weighted F1 | 전체 정답률뿐 아니라 라벨별 성능 균형과 데이터 분포 영향을 함께 보기 위한 조합입니다. |",
        "",
        "## 라벨 분포",
        "",
        "| Label | Name | Count |",
        "|---|---|---:|",
    ]
    for label, count in summary.label_counts.items():
        lines.append(f"| {label} | {AIHUB_LABELS.get(label, label)} | {count} |")

    lines.extend(
        [
            "",
            "## 벤치마크 결과",
            "",
            "| Task | Split | Model | Accuracy | Macro F1 | Weighted F1 | Train/Test Rows | Train/Test Groups |",
            "|---|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    for _, row in benchmark.iterrows():
        lines.append(
            f"| {row['task']} | {row['split']} | {row['model']} | "
            f"{float(row['accuracy']):.3f} | {float(row['macro_f1']):.3f} | {float(row['weighted_f1']):.3f} | "
            f"{int(row['train_rows'])}/{int(row['test_rows'])} | {int(row['train_groups'])}/{int(row['test_groups'])} |"
        )

    best = benchmark.sort_values("macro_f1", ascending=False).iloc[0]
    operational = benchmark[benchmark["split"] == "asset_group_stratified"].sort_values("macro_f1", ascending=False)
    operational_best = operational.iloc[0] if not operational.empty else None
    lines.extend(
        [
            "",
            "## 현재 최고 후보: 성능 상한선",
            "",
            f"- Task: `{best['task']}`",
            f"- Split: `{best['split']}`",
            f"- Model: `{best['model']}`",
            f"- Accuracy: `{float(best['accuracy']):.3f}`",
            f"- Macro F1: `{float(best['macro_f1']):.3f}`",
        ]
    )
    if operational_best is not None:
        lines.extend(
            [
                "",
                "## 현재 최고 후보: 미지 설비 일반화 기준",
                "",
                f"- Task: `{operational_best['task']}`",
                f"- Split: `{operational_best['split']}`",
                f"- Model: `{operational_best['model']}`",
                f"- Accuracy: `{float(operational_best['accuracy']):.3f}`",
                f"- Macro F1: `{float(operational_best['macro_f1']):.3f}`",
            ]
        )
    if saved_model:
        lines.extend(
            [
                "",
                "## 저장된 모델",
                "",
                f"- Path: `{saved_model['path']}`",
                f"- Task: `{saved_model['task']}`",
                f"- Split 기준: `{saved_model['split']}`",
                f"- Model: `{saved_model['model']}`",
                f"- Accuracy: `{saved_model['accuracy']:.3f}`",
                f"- Macro F1: `{saved_model['macro_f1']:.3f}`",
            ]
        )
    lines.extend(
        [
            "",
            "## 해석 주의",
            "",
            "- `row_stratified_upper_bound`는 같은 설비나 유사 파일 패턴이 train/test에 동시에 들어갈 수 있어 실제 일반화 성능보다 높게 나올 수 있습니다.",
            "- `asset_group_stratified`는 설비 그룹을 분리하므로 더 현실적입니다. 다만 초기 샘플 수가 작으면 test 라벨 분포가 흔들릴 수 있습니다.",
            "- AI-Hub current 데이터는 RUL 정답이 아니라 상태 라벨 데이터입니다. 그래서 이 실험은 RUL 회귀가 아니라 정상/고장 및 고장 유형 분류 실험입니다.",
            "",
            "## 다음 실험 명령",
            "",
            "```powershell",
            "$env:PYTHONPATH='backend'",
            "python backend\\scripts\\benchmark_aihub_current.py --max-files 10000 --max-per-path-label 2000 --seed 42 --output data\\aihub238\\aihub_current_10k_benchmark.csv --report-output data\\aihub238\\aihub_current_10k_report.md --model-output data\\models\\aihub_current_fault_classifier.joblib",
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


if __name__ == "__main__":
    main()
