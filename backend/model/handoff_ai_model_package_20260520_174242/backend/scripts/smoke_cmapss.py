from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.cmapss import (
    add_train_rul,
    build_sliding_windows,
    load_split,
    load_test_rul,
    phm_score,
    rmse,
    validate_subset_counts,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a quick C-MAPSS ingestion/RUL smoke test.")
    parser.add_argument("--data-dir", default="data/cmapss")
    parser.add_argument("--subset", default="FD001", choices=["FD001", "FD002", "FD003", "FD004"])
    parser.add_argument("--window-size", type=int, default=50)
    parser.add_argument("--max-windows", type=int, default=3000)
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    train = load_split(data_dir, subset=args.subset, split="train")
    test = load_split(data_dir, subset=args.subset, split="test")
    test_rul = load_test_rul(data_dir, subset=args.subset)
    labeled = add_train_rul(train)
    windows, labels, units = build_sliding_windows(labeled, window_size=args.window_size)

    sample_count = min(args.max_windows, len(labels))
    sampled_labels = labels[:sample_count]
    naive_predictions = np.repeat(float(np.median(sampled_labels)), sample_count)

    print("[C-MAPSS smoke]")
    print(f"subset={args.subset}")
    print(f"train_rows={len(train)} train_units={train['unit'].nunique()}")
    print(f"test_rows={len(test)} test_units={test['unit'].nunique()} test_rul_rows={len(test_rul)}")
    print(f"window_shape={windows.shape} labels_shape={labels.shape} units_shape={units.shape}")
    print(f"rul_min={int(labels.min())} rul_max={int(labels.max())} rul_mean={labels.mean():.2f}")
    print(f"naive_rmse_on_first_{sample_count}={rmse(sampled_labels, naive_predictions):.3f}")
    print(f"naive_phm_score_on_first_{sample_count}={phm_score(sampled_labels, naive_predictions):.3f}")
    for validation in validate_subset_counts(data_dir, args.subset):
        print(
            "count_check="
            f"{validation.subset}/{validation.split} expected={validation.expected_units} "
            f"actual={validation.actual_units} match={validation.matches_nasa_readme} "
            f"note={validation.note}"
        )


if __name__ == "__main__":
    main()
