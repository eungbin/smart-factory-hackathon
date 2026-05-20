from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.fault_classifier import predict_fault_class
from app.predictor import predict_health, predict_rul
from app.simulator import get_asset


class FaultClassifierTests(unittest.TestCase):
    def test_fault_classifier_returns_ranked_classes(self) -> None:
        asset = get_asset("INJ-03")
        rul = predict_rul(asset.asset_id, asset.sensor_window)
        fault = predict_fault_class(asset.asset_id, asset.sensor_window, rul)

        self.assertEqual(fault.asset_id, "INJ-03")
        self.assertGreaterEqual(len(fault.top_classes), 3)
        self.assertGreaterEqual(fault.fault_probability, fault.top_classes[-1].probability)
        self.assertTrue(fault.evidence)

    def test_health_prediction_combines_rul_and_fault(self) -> None:
        asset = get_asset("INJ-03")
        health = predict_health(asset.asset_id, asset.sensor_window)

        self.assertEqual(health.asset_id, "INJ-03")
        self.assertEqual(health.rul.asset_id, "INJ-03")
        self.assertEqual(health.fault.asset_id, "INJ-03")
        self.assertGreater(health.rul.rul_hours, 0)


if __name__ == "__main__":
    unittest.main()
