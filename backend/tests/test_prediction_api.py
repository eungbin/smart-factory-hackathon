import unittest

from app.api.predictions import read_latest_prediction, run_prediction
from app.db.models import EquipmentStateLatest, PredictionFaultProbability, PredictionRootCause, PredictionRun
from app.db.seed import seed_demo_data
from app.db.session import SessionLocal, engine
from app.schemas.predictions import PredictionRunIn


class PredictionApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        seed_demo_data()

    @classmethod
    def tearDownClass(cls) -> None:
        engine.dispose()

    def test_run_prediction_persists_outputs_and_updates_latest_state(self) -> None:
        with SessionLocal() as db:
            response = run_prediction(PredictionRunIn(equipmentId=3), db=db)

            data = response["data"]
            run_id = data["predictionRunId"]

            self.assertIsInstance(data["rul"], int)
            self.assertIsInstance(data["risk"], int)
            self.assertIn(data["status"], {"normal", "warn", "danger"})
            self.assertGreaterEqual(len(data["faultProbabilities"]), 5)
            self.assertGreaterEqual(len(data["rootSensors"]), 3)
            self.assertIsNotNone(db.get(PredictionRun, run_id))
            prediction_run = db.get(PredictionRun, run_id)
            self.assertEqual("handoff_adapter_v1", prediction_run.raw_output["model"])
            self.assertEqual("synthetic_cmapss_adapter", prediction_run.raw_output["rul_source"])
            self.assertEqual("aihub_feature_adapter", prediction_run.raw_output["fault_source"])
            self.assertGreater(
                db.query(PredictionFaultProbability)
                .filter(PredictionFaultProbability.prediction_run_id == run_id)
                .count(),
                0,
            )
            self.assertGreater(
                db.query(PredictionRootCause).filter(PredictionRootCause.prediction_run_id == run_id).count(),
                0,
            )

            state = db.get(EquipmentStateLatest, 3)
            self.assertEqual(run_id, state.latest_prediction_run_id)
            self.assertEqual(data["rul"], state.rul_hours)
            self.assertEqual(data["risk"], int(state.risk_pct))

    def test_read_latest_prediction_returns_persisted_run(self) -> None:
        with SessionLocal() as db:
            created = run_prediction(PredictionRunIn(equipmentId=3), db=db)["data"]
            response = read_latest_prediction(3, db=db)

        self.assertEqual(created["predictionRunId"], response["data"]["predictionRunId"])
        self.assertGreaterEqual(len(response["data"]["faultProbabilities"]), 5)
        self.assertGreaterEqual(len(response["data"]["rootSensors"]), 3)


if __name__ == "__main__":
    unittest.main()
