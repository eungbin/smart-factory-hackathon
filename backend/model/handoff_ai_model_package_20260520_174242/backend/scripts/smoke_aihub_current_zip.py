from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.aihub import (  # noqa: E402
    build_aihub_feature_table,
    find_default_aihub_current_zip,
    inspect_aihub_current_zip,
    load_aihub_current_zip,
    summarize_aihub,
    train_aihub_fault_classifier,
)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    parser = argparse.ArgumentParser(description="Smoke-test the downloaded AI-Hub 238 current.zip bundle.")
    parser.add_argument("--zip-path", default="", help="Path to current.zip. Auto-detects under data/aihub238/downloads when omitted.")
    parser.add_argument("--max-files", type=int, default=250, help="Maximum CSV files to parse for this smoke test.")
    parser.add_argument("--max-per-path-label", type=int, default=50, help="Balanced sample size per ZIP path label folder.")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    zip_path = Path(args.zip_path) if args.zip_path else find_default_aihub_current_zip()
    zip_info = inspect_aihub_current_zip(zip_path)
    frame = load_aihub_current_zip(
        zip_path,
        max_files=args.max_files,
        max_per_path_label=args.max_per_path_label,
        seed=args.seed,
    )
    summary = summarize_aihub(frame)
    features, labels, groups = build_aihub_feature_table(frame)
    result = train_aihub_fault_classifier(frame)

    print("[AI-Hub current ZIP smoke]")
    print(f"zip_path={zip_path}")
    print(f"zip_size_gb={zip_info['zip_size_bytes'] / (1024 ** 3):.2f}")
    print(f"csv_count={zip_info['csv_count']}")
    print(f"parsed_rows={summary.rows}")
    print(f"missing_required_columns={summary.missing_required_columns}")
    print(f"label_counts={summary.label_counts}")
    print(f"motor_kw_values={summary.motor_kw_values}")
    print(f"sample_rate_values={summary.sample_rate_values}")
    print(f"feature_shape={features.shape} labels={labels.nunique()} groups={groups.nunique()}")
    print(f"feature_columns={list(features.columns)}")
    print(f"classifier_split={result['split']} train_rows={result['train_rows']} test_rows={result['test_rows']}")
    print(f"classifier_accuracy={result['accuracy']:.3f}")


if __name__ == "__main__":
    main()
