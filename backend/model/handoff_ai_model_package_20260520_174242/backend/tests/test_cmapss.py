from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.cmapss import SENSOR_COLUMNS, SETTING_COLUMNS, add_train_rul, build_sliding_windows, validate_unit_leakage
from app.cmapss_conditioning import (
    condition_feature_columns,
    fit_condition_normalizer,
    transform_with_condition_normalization,
)
from app.cmapss_runtime import cmapss_risk_percent


class CMapssPipelineTests(unittest.TestCase):
    def test_rul_labeler_and_windows(self) -> None:
        rows = []
        for unit in [1, 2]:
            for cycle in range(1, 7):
                rows.append(
                    {
                        "unit": unit,
                        "cycle": cycle,
                        "operational_setting_1": 0.0,
                        "operational_setting_2": 0.0,
                        "operational_setting_3": 100.0,
                        "T2": 1.0 + cycle,
                        "T24": 2.0 + cycle,
                    }
                )
        frame = pd.DataFrame(rows)
        labeled = add_train_rul(frame, cap=None)
        self.assertEqual(labeled[labeled["unit"] == 1]["rul"].tolist(), [5, 4, 3, 2, 1, 0])

        windows, labels, units = build_sliding_windows(
            labeled,
            window_size=3,
            feature_columns=["operational_setting_1", "T2", "T24"],
        )
        self.assertEqual(windows.shape, (8, 3, 3))
        self.assertEqual(labels[0], 3)
        self.assertEqual(units.tolist().count(1), 4)

    def test_unit_leakage_detection(self) -> None:
        train = pd.DataFrame({"unit": [1, 1, 2], "cycle": [1, 2, 1]})
        test = pd.DataFrame({"unit": [3, 3], "cycle": [1, 2]})
        leaked = pd.DataFrame({"unit": [2, 4], "cycle": [1, 1]})
        self.assertTrue(validate_unit_leakage(train, test))
        self.assertFalse(validate_unit_leakage(train, leaked))

    def test_cmapss_risk_percent_increases_as_rul_drops(self) -> None:
        self.assertGreater(cmapss_risk_percent(30), cmapss_risk_percent(72))
        self.assertGreater(cmapss_risk_percent(72), cmapss_risk_percent(125))

    def test_condition_normalizer_adds_condition_features(self) -> None:
        rows = []
        settings = [
            (0.0, 0.0, 60.0),
            (10.0, 0.25, 100.0),
            (20.0, 0.7, 100.0),
            (25.0, 0.62, 60.0),
            (35.0, 0.84, 100.0),
            (42.0, 0.84, 100.0),
        ]
        for unit in range(1, 4):
            for cycle, setting in enumerate(settings * 2, start=1):
                row = {
                    "unit": unit,
                    "cycle": cycle,
                    **{column: value for column, value in zip(SETTING_COLUMNS, setting)},
                }
                for index, sensor in enumerate(SENSOR_COLUMNS, start=1):
                    row[sensor] = float(index + cycle + unit)
                rows.append(row)
        frame = pd.DataFrame(rows)
        normalizer = fit_condition_normalizer(frame, "FD002")
        transformed = transform_with_condition_normalization(frame, normalizer)
        self.assertEqual(normalizer.condition_count, 6)
        self.assertIn("condition_id", transformed.columns)
        self.assertIn("norm_T2", transformed.columns)
        self.assertEqual(len(condition_feature_columns()), 30)
        self.assertGreaterEqual(transformed["condition_id"].nunique(), 5)


if __name__ == "__main__":
    unittest.main()
