from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.aihub import (
    build_aihub_feature_table,
    load_aihub_annotations,
    make_sample_aihub_frame,
    summarize_aihub,
    train_aihub_fault_classifier,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a quick AI-Hub annotation/fault-classification smoke test.")
    parser.add_argument("--annotation-path", default="", help="Path to AI-Hub annotation CSV/XLSX. Uses sample data when omitted.")
    args = parser.parse_args()

    if args.annotation_path:
        frame = load_aihub_annotations(Path(args.annotation_path))
        source = args.annotation_path
    else:
        frame = make_sample_aihub_frame()
        source = "built-in sample"

    summary = summarize_aihub(frame)
    features, labels, groups = build_aihub_feature_table(frame)
    result = train_aihub_fault_classifier(frame)

    print("[AI-Hub smoke]")
    print(f"source={source}")
    print(f"rows={summary.rows}")
    print(f"missing_required_columns={summary.missing_required_columns}")
    print(f"label_counts={summary.label_counts}")
    print(f"motor_kw_values={summary.motor_kw_values}")
    print(f"sample_rate_values={summary.sample_rate_values}")
    print(f"feature_shape={features.shape} labels={labels.nunique()} groups={groups.nunique()}")
    print(f"classifier_split={result['split']} train_rows={result['train_rows']} test_rows={result['test_rows']}")
    print(f"classifier_accuracy={result['accuracy']:.3f}")


if __name__ == "__main__":
    main()
