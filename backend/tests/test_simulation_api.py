import unittest

from app.api.simulation import run_simulation_tick
from app.db.models import EquipmentStateLatest, PredictionRun, SensorReading
from app.db.seed import seed_demo_data
from app.db.session import SessionLocal, engine
from app.schemas.simulation import SimulationTickIn


class SimulationApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        seed_demo_data()

    @classmethod
    def tearDownClass(cls) -> None:
        engine.dispose()

    def test_simulation_tick_creates_sensor_reading_and_prediction(self) -> None:
        with SessionLocal() as db:
            response = run_simulation_tick(SimulationTickIn(equipmentId=3), db=db)

            data = response["data"]

            self.assertEqual(1, data["insertedReadings"])
            self.assertEqual(1, len(data["predictions"]))
            self.assertIsInstance(data["predictions"][0]["rul"], int)
            self.assertIsInstance(data["predictions"][0]["risk"], int)
            self.assertGreater(
                db.query(SensorReading).filter(SensorReading.equipment_id == 3).count(),
                0,
            )
            self.assertGreater(
                db.query(PredictionRun).filter(PredictionRun.equipment_id == 3).count(),
                0,
            )

            state = db.get(EquipmentStateLatest, 3)
            self.assertIsNotNone(state.latest_sensor_reading_at)
            self.assertIsNotNone(state.latest_prediction_run_id)


if __name__ == "__main__":
    unittest.main()
