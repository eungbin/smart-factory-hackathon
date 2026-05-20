from datetime import UTC, datetime
from decimal import Decimal
import unittest

from fastapi import HTTPException

from app.api.equipment_detail import read_maintenance_history, read_rul_history, read_sensor_history
from app.db.models import EquipmentStatus, FaultTypeCode, PredictionRun, SensorReading
from app.db.seed import seed_demo_data
from app.db.session import SessionLocal, engine


class EquipmentDetailApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        seed_demo_data()

    @classmethod
    def tearDownClass(cls) -> None:
        engine.dispose()

    def test_read_sensor_history_returns_frontend_chart_shape(self) -> None:
        with SessionLocal() as db:
            response = read_sensor_history(3, db=db)

        points = response["data"]

        self.assertGreaterEqual(len(points), 1)
        self.assertEqual(
            {"time", "measuredAt", "vibration", "temperature", "current", "pressure"},
            set(points[0].keys()),
        )

    def test_read_sensor_history_formats_chart_time_as_kst(self) -> None:
        with SessionLocal() as db:
            db.add(
                SensorReading(
                    equipment_id=3,
                    measured_at=datetime(2026, 5, 20, 17, 30, tzinfo=UTC),
                    vibration_rms_g=Decimal("1.234"),
                    hydraulic_temp_c=Decimal("67.8"),
                    motor_current_a=Decimal("21.2"),
                    hydraulic_pressure_bar=Decimal("145.6"),
                    features={"test": "kst"},
                    source="test",
                )
            )
            db.flush()

            response = read_sensor_history(3, db=db)
            point = response["data"][-1]

            self.assertEqual("02:30", point["time"])
            self.assertTrue(point["measuredAt"].startswith("2026-05-21T02:30:00"))
            self.assertTrue(point["measuredAt"].endswith("+09:00"))
            db.rollback()

    def test_read_rul_history_returns_frontend_chart_shape(self) -> None:
        with SessionLocal() as db:
            response = read_rul_history(3, db=db)

        points = response["data"]

        self.assertEqual(31, len(points))
        self.assertEqual({"date", "measuredAt", "rul", "upper", "lower"}, set(points[0].keys()))

    def test_read_rul_history_formats_chart_date_as_kst(self) -> None:
        with SessionLocal() as db:
            db.add(
                PredictionRun(
                    equipment_id=3,
                    input_window_start=datetime(2026, 5, 20, 17, 0, tzinfo=UTC),
                    input_window_end=datetime(2026, 5, 20, 17, 30, tzinfo=UTC),
                    input_readings_count=1,
                    status=EquipmentStatus.warn,
                    rul_hours=88,
                    rul_lower_hours=70,
                    rul_upper_hours=106,
                    risk_pct=Decimal("44.0"),
                    fault_type_code=FaultTypeCode.bearing_fault,
                    fault_confidence_pct=Decimal("55.0"),
                    summary="test",
                    raw_output={"test": "kst"},
                    created_at=datetime(2026, 5, 20, 17, 30, tzinfo=UTC),
                )
            )
            db.flush()

            response = read_rul_history(3, db=db)
            point = response["data"][-1]

            self.assertEqual("5/21", point["date"])
            self.assertTrue(point["measuredAt"].startswith("2026-05-21T02:30:00"))
            self.assertTrue(point["measuredAt"].endswith("+09:00"))
            db.rollback()

    def test_read_maintenance_history_returns_seeded_records(self) -> None:
        with SessionLocal() as db:
            response = read_maintenance_history(3, db=db)

        records = response["data"]

        self.assertEqual(2, len(records))
        self.assertEqual(
            {"id", "equipId", "date", "type", "tech", "parts", "result", "duration", "note"},
            set(records[0].keys()),
        )

    def test_read_detail_history_returns_404_for_missing_equipment(self) -> None:
        with SessionLocal() as db:
            with self.assertRaises(HTTPException) as raised:
                read_sensor_history(9999, db=db)

        self.assertEqual(404, raised.exception.status_code)


if __name__ == "__main__":
    unittest.main()
