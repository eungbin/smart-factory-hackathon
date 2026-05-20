from __future__ import annotations

import argparse
import json
import sys
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.cmapss import (  # noqa: E402
    BASE_COLUMNS,
    NASA_EXPECTED_COUNTS,
    SENSOR_COLUMNS,
    SETTING_COLUMNS,
    SUBSETS,
    add_train_rul,
    build_sliding_windows,
    download_cmapss,
    load_split,
    load_test_rul,
    validate_subset_counts,
)


@dataclass(frozen=True)
class ValidationIssue:
    level: str
    subset: str
    check: str
    message: str


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    parser = argparse.ArgumentParser(description="Validate NASA C-MAPSS data integrity and current RUL benchmark outputs.")
    parser.add_argument("--data-dir", default="data/cmapss")
    parser.add_argument("--window-size", type=int, default=50)
    parser.add_argument("--benchmark-path", default="data/cmapss/cmapss_rul_gru_benchmark.csv")
    parser.add_argument("--report-json", default="data/cmapss/cmapss_validation_report.json")
    parser.add_argument("--report-md", default="data/cmapss/cmapss_validation_report.md")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    zip_path = download_cmapss(data_dir)
    issues: list[ValidationIssue] = []
    report: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_dir": str(data_dir),
        "zip_path": str(zip_path),
        "zip_size_bytes": zip_path.stat().st_size,
        "window_size": args.window_size,
        "schema_columns": BASE_COLUMNS,
        "subsets": {},
    }

    report["zip"] = _validate_zip(zip_path, issues)

    for subset in SUBSETS:
        report["subsets"][subset] = _validate_subset(data_dir, subset, args.window_size, issues)

    benchmark_path = Path(args.benchmark_path)
    report["benchmark"] = _validate_benchmark(benchmark_path, issues)
    report["summary"] = _summary(issues)

    json_path = Path(args.report_json)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    md_path = Path(args.report_md)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(_markdown_report(report, issues), encoding="utf-8")

    print("[C-MAPSS validation]")
    print(f"zip={zip_path} size_mb={zip_path.stat().st_size / (1024 * 1024):.2f}")
    for subset, subset_report in report["subsets"].items():
        print(
            f"{subset}: train_rows={subset_report['train']['rows']} "
            f"test_rows={subset_report['test']['rows']} "
            f"rul_rows={subset_report['rul']['rows']} "
            f"windows={subset_report['train']['sliding_windows']['actual_windows']} "
            f"status={subset_report['status']}"
        )
    print(
        "issues="
        f"error:{report['summary']['errors']} "
        f"warn:{report['summary']['warnings']} "
        f"info:{report['summary']['infos']}"
    )
    print(f"benchmark_status={report['benchmark']['status']}")
    print(f"report_json={json_path}")
    print(f"report_md={md_path}")


def _validate_zip(zip_path: Path, issues: list[ValidationIssue]) -> dict[str, Any]:
    required_members = {
        f"{split}_{subset}.txt"
        for subset in SUBSETS
        for split in ("train", "test")
    } | {f"RUL_{subset}.txt" for subset in SUBSETS}
    with zipfile.ZipFile(zip_path) as archive:
        members = set(archive.namelist())
        missing = sorted(required_members - members)
        bad_member = archive.testzip()
    if missing:
        issues.append(ValidationIssue("ERROR", "ALL", "zip_members", f"Missing ZIP members: {missing}"))
    if bad_member is not None:
        issues.append(ValidationIssue("ERROR", "ALL", "zip_crc", f"CRC check failed for {bad_member}"))
    return {
        "status": "PASS" if not missing and bad_member is None else "FAIL",
        "required_members_present": not missing,
        "missing_members": missing,
        "crc_check": "PASS" if bad_member is None else f"FAIL:{bad_member}",
    }


def _validate_subset(
    data_dir: Path,
    subset: str,
    window_size: int,
    issues: list[ValidationIssue],
) -> dict[str, Any]:
    train = load_split(data_dir, subset=subset, split="train")  # type: ignore[arg-type]
    test = load_split(data_dir, subset=subset, split="test")  # type: ignore[arg-type]
    rul = load_test_rul(data_dir, subset=subset)  # type: ignore[arg-type]
    subset_issues_before = len(issues)

    train_report = _validate_split_frame(train, subset, "train", issues)
    test_report = _validate_split_frame(test, subset, "test", issues)
    rul_report = _validate_rul(rul, test, subset, issues)
    count_report = [asdict(item) for item in validate_subset_counts(data_dir, subset)]
    for item in count_report:
        if not item["matches_nasa_readme"]:
            level = "WARN" if subset == "FD004" else "ERROR"
            issues.append(
                ValidationIssue(
                    level,
                    subset,
                    f"{item['split']}_unit_count",
                    (
                        f"NASA expected {item['expected_units']} units, "
                        f"downloaded ZIP has {item['actual_units']}. {item['note']}"
                    ),
                )
            )

    labeled_uncapped = add_train_rul(train, cap=None)
    final_ruls = labeled_uncapped.loc[
        labeled_uncapped["cycle"] == labeled_uncapped.groupby("unit")["cycle"].transform("max"),
        "rul",
    ]
    if not (final_ruls == 0).all():
        issues.append(ValidationIssue("ERROR", subset, "train_rul_label", "Some final train cycles do not have RUL=0."))

    labeled_capped = add_train_rul(train, cap=125)
    windows, labels, units = build_sliding_windows(labeled_capped, window_size=window_size)
    expected_windows = int(
        train.groupby("unit")["cycle"].max().map(lambda cycles: max(0, int(cycles) - window_size + 1)).sum()
    )
    if windows.shape[0] != expected_windows:
        issues.append(
            ValidationIssue(
                "ERROR",
                subset,
                "sliding_windows",
                f"Expected {expected_windows} windows, got {windows.shape[0]}.",
            )
        )
    if windows.shape[1:] != (window_size, len(SETTING_COLUMNS) + len(SENSOR_COLUMNS)):
        issues.append(
            ValidationIssue(
                "ERROR",
                subset,
                "window_shape",
                f"Unexpected window shape {windows.shape}.",
            )
        )

    train_report["sliding_windows"] = {
        "expected_windows": expected_windows,
        "actual_windows": int(windows.shape[0]),
        "window_shape": list(windows.shape),
        "label_min": float(labels.min()),
        "label_max": float(labels.max()),
        "unit_count_in_windows": int(np.unique(units).size),
    }
    train_report["rul_label"] = {
        "uncapped_final_rul_zero": bool((final_ruls == 0).all()),
        "capped_min": float(labeled_capped["rul"].min()),
        "capped_max": float(labeled_capped["rul"].max()),
        "capped_mean": float(labeled_capped["rul"].mean()),
    }

    subset_issue_levels = {issue.level for issue in issues[subset_issues_before:] if issue.subset in {subset, "ALL"}}
    status = "FAIL" if "ERROR" in subset_issue_levels else ("WARN" if "WARN" in subset_issue_levels else "PASS")
    return {
        "status": status,
        "scenario": _scenario_description(subset),
        "count_validation": count_report,
        "operating_setting_ranges": _ranges(train, SETTING_COLUMNS),
        "sensor_low_variance_columns": _low_variance_columns(train, SENSOR_COLUMNS),
        "train": train_report,
        "test": test_report,
        "rul": rul_report,
    }


def _validate_split_frame(
    frame: pd.DataFrame,
    subset: str,
    split: str,
    issues: list[ValidationIssue],
) -> dict[str, Any]:
    missing_columns = [column for column in BASE_COLUMNS if column not in frame.columns]
    if missing_columns:
        issues.append(ValidationIssue("ERROR", subset, f"{split}_schema", f"Missing columns: {missing_columns}"))
    null_count = int(frame.isna().sum().sum())
    if null_count:
        issues.append(ValidationIssue("ERROR", subset, f"{split}_nulls", f"{null_count} null values found."))
    numeric_finite = bool(np.isfinite(frame[BASE_COLUMNS].to_numpy(dtype=float)).all())
    if not numeric_finite:
        issues.append(ValidationIssue("ERROR", subset, f"{split}_finite", "Non-finite numeric values found."))
    units = sorted(int(unit) for unit in frame["unit"].unique())
    contiguous_units = units == list(range(1, len(units) + 1))
    if not contiguous_units:
        issues.append(ValidationIssue("ERROR", subset, f"{split}_unit_sequence", "Unit ids are not contiguous from 1."))
    cycle_continuity = _cycle_continuity(frame)
    if not cycle_continuity:
        issues.append(ValidationIssue("ERROR", subset, f"{split}_cycle_sequence", "Cycles are not continuous from 1 per unit."))
    return {
        "rows": int(len(frame)),
        "columns": int(frame.shape[1]),
        "unit_count": int(len(units)),
        "unit_min": int(min(units)),
        "unit_max": int(max(units)),
        "cycle_min": int(frame["cycle"].min()),
        "cycle_max": int(frame["cycle"].max()),
        "schema_ok": not missing_columns and frame.shape[1] == len(BASE_COLUMNS),
        "null_count": null_count,
        "numeric_finite": numeric_finite,
        "contiguous_units": contiguous_units,
        "cycle_continuity": cycle_continuity,
        "sample_rows": frame.head(3).to_dict(orient="records"),
    }


def _validate_rul(
    rul: pd.Series,
    test: pd.DataFrame,
    subset: str,
    issues: list[ValidationIssue],
) -> dict[str, Any]:
    rows = int(len(rul))
    test_units = int(test["unit"].nunique())
    if rows != test_units:
        issues.append(
            ValidationIssue(
                "ERROR",
                subset,
                "rul_alignment",
                f"RUL rows {rows} != test unit count {test_units}.",
            )
        )
    null_count = int(rul.isna().sum())
    if null_count:
        issues.append(ValidationIssue("ERROR", subset, "rul_nulls", f"{null_count} null RUL values found."))
    if (rul < 0).any():
        issues.append(ValidationIssue("ERROR", subset, "rul_negative", "Negative test RUL values found."))
    return {
        "rows": rows,
        "matches_test_unit_count": rows == test_units,
        "null_count": null_count,
        "min": int(rul.min()),
        "max": int(rul.max()),
        "mean": float(rul.mean()),
        "head": [int(value) for value in rul.head(10).tolist()],
    }


def _validate_benchmark(path: Path, issues: list[ValidationIssue]) -> dict[str, Any]:
    if not path.exists():
        issues.append(ValidationIssue("WARN", "ALL", "benchmark", f"Benchmark CSV not found: {path}"))
        return {"status": "MISSING", "path": str(path), "rows": []}
    frame = pd.read_csv(path)
    required = {
        "subset",
        "test_rmse_capped",
        "test_phm_score_capped",
        "high_risk_count",
    }
    missing = sorted(required - set(frame.columns))
    model_column = "model_type" if "model_type" in frame.columns else "name" if "name" in frame.columns else ""
    if not model_column:
        missing.append("model_type_or_name")
    if missing:
        issues.append(ValidationIssue("ERROR", "ALL", "benchmark_schema", f"Missing benchmark columns: {missing}"))
    if model_column:
        combined_all = frame[
            frame[model_column].isin(
                [
                    "combined",
                    "condition_combined",
                    "gru_sequence",
                    "single_gru",
                    "ensemble_grid_gru_tcn_patchtst_val",
                    "ensemble_equal_gru_tcn_patchtst",
                ]
            )
            & (frame["subset"] == "ALL")
        ]
    else:
        combined_all = pd.DataFrame()
    if combined_all.empty:
        issues.append(ValidationIssue("WARN", "ALL", "benchmark_combined", "Combined ALL benchmark row is missing."))
    return {
        "status": "PASS" if not missing and not combined_all.empty else "WARN",
        "path": str(path),
        "row_count": int(len(frame)),
        "combined_all": combined_all.to_dict(orient="records"),
        "rows": frame.to_dict(orient="records"),
    }


def _cycle_continuity(frame: pd.DataFrame) -> bool:
    for _, unit_frame in frame.groupby("unit"):
        cycles = unit_frame["cycle"].astype(int).to_numpy()
        expected = np.arange(1, len(cycles) + 1)
        if not np.array_equal(cycles, expected):
            return False
    return True


def _ranges(frame: pd.DataFrame, columns: list[str]) -> dict[str, dict[str, float]]:
    return {
        column: {
            "min": float(frame[column].min()),
            "max": float(frame[column].max()),
            "std": float(frame[column].std()),
        }
        for column in columns
    }


def _low_variance_columns(frame: pd.DataFrame, columns: list[str], threshold: float = 1e-8) -> list[str]:
    return [
        column
        for column in columns
        if float(frame[column].std()) <= threshold or int(frame[column].nunique()) <= 1
    ]


def _scenario_description(subset: str) -> dict[str, object]:
    return {
        "FD001": {"operating_conditions": 1, "fault_modes": 1},
        "FD002": {"operating_conditions": 6, "fault_modes": 1},
        "FD003": {"operating_conditions": 1, "fault_modes": 2},
        "FD004": {"operating_conditions": 6, "fault_modes": 2},
    }[subset]


def _summary(issues: list[ValidationIssue]) -> dict[str, int]:
    return {
        "errors": sum(issue.level == "ERROR" for issue in issues),
        "warnings": sum(issue.level == "WARN" for issue in issues),
        "infos": sum(issue.level == "INFO" for issue in issues),
    }


def _markdown_report(report: dict[str, Any], issues: list[ValidationIssue]) -> str:
    lines = [
        "# C-MAPSS Validation Report",
        "",
        f"- Generated: `{report['generated_at']}`",
        f"- ZIP: `{report['zip_path']}`",
        f"- ZIP size: `{report['zip_size_bytes']}` bytes",
        f"- Window size: `{report['window_size']}` cycle",
        f"- ZIP status: `{report['zip']['status']}`",
        "",
        "## Subset Summary",
        "",
        "| subset | status | train rows | train units | test rows | test units | RUL rows | windows |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for subset, item in report["subsets"].items():
        lines.append(
            f"| {subset} | {item['status']} | {item['train']['rows']} | {item['train']['unit_count']} | "
            f"{item['test']['rows']} | {item['test']['unit_count']} | {item['rul']['rows']} | "
            f"{item['train']['sliding_windows']['actual_windows']} |"
        )
    lines.extend(["", "## Benchmark", ""])
    combined = report["benchmark"].get("combined_all", [])
    if combined:
        row = combined[0]
        lines.append(
            f"- Combined ALL capped RMSE: `{float(row['test_rmse_capped']):.3f}`"
        )
        lines.append(
            f"- Combined ALL PHM score: `{float(row['test_phm_score_capped']):.3f}`"
        )
        lines.append(f"- Combined high-risk count: `{int(row['high_risk_count'])}`")
    else:
        lines.append("- Combined benchmark row missing.")
    lines.extend(["", "## Issues", ""])
    if not issues:
        lines.append("- No issues.")
    else:
        for issue in issues:
            lines.append(f"- `{issue.level}` `{issue.subset}` `{issue.check}`: {issue.message}")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
