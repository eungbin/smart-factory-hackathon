from datetime import UTC, datetime, timedelta
import unittest

from app.db.models import EquipmentStatus, FaultTypeCode
from app.ml.contracts import SensorPoint, SensorWindow
from app.ml.handoff_runtime import infer


class HandoffRuntimeTests(unittest.TestCase):
    def test_infer_records_synthetic_adapter_metadata(self) -> None:
        start = datetime(2026, 5, 20, 8, 0, tzinfo=UTC)
        points = [
            SensorPoint(
                measured_at=start + timedelta(minutes=index),
                vibration_rms_g=1.2 + index * 0.04,
                hydraulic_temp_c=68.0 + index * 0.2,
                motor_current_a=22.0 + index * 0.15,
                hydraulic_pressure_bar=142.0 - index * 0.12,
            )
            for index in range(12)
        ]

        result = infer(SensorWindow(equipment_id=3, points=points))

        self.assertIn(result.status, {EquipmentStatus.normal, EquipmentStatus.warn, EquipmentStatus.danger})
        self.assertGreater(result.rul_hours, 0)
        self.assertGreaterEqual(len(result.fault_probabilities), 5)
        self.assertGreaterEqual(len(result.root_sensors), 3)
        self.assertEqual(result.raw_output["model"], "handoff_adapter_v1")
        self.assertEqual(result.raw_output["rul_source"], "synthetic_cmapss_adapter")
        self.assertEqual(result.raw_output["fault_source"], "aihub_feature_adapter")
        self.assertEqual(result.raw_output["visible_sensor_count"], 4)
        self.assertEqual(result.raw_output["synthetic_rul_feature_shape"], [50, 31])
        self.assertIn("model_rul_hours", result.raw_output["rul_detail"])
        self.assertIn("sensor_penalty_hours", result.raw_output["rul_detail"])
        self.assertIn("adjusted_rul_hours", result.raw_output["rul_detail"])
        self.assertIn("sensor_degradation_score", result.raw_output)
        self.assertIn("risk_detail", result.raw_output)

    def test_abnormal_sensors_reduce_rul_and_increase_risk(self) -> None:
        start = datetime(2026, 5, 20, 8, 0, tzinfo=UTC)
        healthy_points = [
            SensorPoint(
                measured_at=start + timedelta(minutes=index),
                vibration_rms_g=0.8,
                hydraulic_temp_c=62.0,
                motor_current_a=19.0,
                hydraulic_pressure_bar=145.0,
            )
            for index in range(12)
        ]
        abnormal_points = [
            SensorPoint(
                measured_at=start + timedelta(minutes=index),
                vibration_rms_g=4.8 + index * 0.02,
                hydraulic_temp_c=96.0 + index * 0.1,
                motor_current_a=35.0 + index * 0.04,
                hydraulic_pressure_bar=171.0 + index * 0.05,
            )
            for index in range(12)
        ]

        healthy = infer(SensorWindow(equipment_id=1, points=healthy_points))
        abnormal = infer(SensorWindow(equipment_id=1, points=abnormal_points))

        self.assertLess(abnormal.rul_hours, healthy.rul_hours)
        self.assertGreater(abnormal.risk_pct, healthy.risk_pct)
        self.assertGreater(
            abnormal.raw_output["sensor_degradation_score"],
            healthy.raw_output["sensor_degradation_score"],
        )
        self.assertNotEqual(FaultTypeCode.normal, abnormal.fault_type_code)
        self.assertIsNotNone(abnormal.fault_confidence_pct)


if __name__ == "__main__":
    unittest.main()
