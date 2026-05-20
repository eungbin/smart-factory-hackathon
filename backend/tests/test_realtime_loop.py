import unittest

from app.db.models import EquipmentStateLatest, PredictionRun, SensorReading
from app.db.seed import seed_demo_data
from app.db.session import SessionLocal, engine
from app.services.realtime_loop import PREDICTION_INTERVAL_SECONDS, SENSOR_INTERVAL_SECONDS
from app.services.simulation import create_sensor_tick


class RealtimeLoopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        seed_demo_data()

    @classmethod
    def tearDownClass(cls) -> None:
        engine.dispose()

    def test_realtime_intervals_match_requested_cadence(self) -> None:
        self.assertEqual(2.0, SENSOR_INTERVAL_SECONDS)
        self.assertEqual(10.0, PREDICTION_INTERVAL_SECONDS)

    def test_sensor_only_tick_inserts_reading_without_prediction(self) -> None:
        with SessionLocal() as db:
            state = db.get(EquipmentStateLatest, 3)
            previous_prediction_id = state.latest_prediction_run_id
            previous_readings = db.query(SensorReading).filter(SensorReading.equipment_id == 3).count()
            previous_predictions = db.query(PredictionRun).filter(PredictionRun.equipment_id == 3).count()

            result = create_sensor_tick(db, equipment_id=3, include_predictions=False)

            self.assertEqual(1, result.insertedReadings)
            self.assertEqual([], result.predictions)
            self.assertGreaterEqual(
                db.query(SensorReading).filter(SensorReading.equipment_id == 3).count(),
                previous_readings + 1,
            )
            self.assertEqual(
                previous_predictions,
                db.query(PredictionRun).filter(PredictionRun.equipment_id == 3).count(),
            )
            self.assertEqual(previous_prediction_id, state.latest_prediction_run_id)


if __name__ == "__main__":
    unittest.main()
