from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.aihub import (
    build_aihub_feature_table,
    make_sample_aihub_frame,
    summarize_aihub,
    train_aihub_fault_classifier,
)


class AIHubPipelineTests(unittest.TestCase):
    def test_sample_summary_and_classifier(self) -> None:
        frame = make_sample_aihub_frame()
        summary = summarize_aihub(frame)
        self.assertEqual(summary.rows, 60)
        self.assertEqual(summary.missing_required_columns, [])
        self.assertIn("00", summary.label_counts)

        features, labels, groups = build_aihub_feature_table(frame)
        self.assertEqual(features.shape[1], 4)
        self.assertEqual(labels.nunique(), 5)
        self.assertGreaterEqual(groups.nunique(), 3)

        result = train_aihub_fault_classifier(frame)
        self.assertIn("accuracy", result)
        self.assertGreaterEqual(result["train_rows"], 1)
        self.assertGreaterEqual(result["test_rows"], 1)


if __name__ == "__main__":
    unittest.main()
