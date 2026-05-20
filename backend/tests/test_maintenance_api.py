import unittest

from app.api.equipment_detail import read_maintenance_history
from app.api.maintenance import create_maintenance_record
from app.db.seed import seed_demo_data
from app.db.session import SessionLocal, engine
from app.schemas.maintenance import MaintenanceRecordIn


class MaintenanceApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        seed_demo_data()

    @classmethod
    def tearDownClass(cls) -> None:
        engine.dispose()

    def test_create_maintenance_record_saves_history_and_learning_queue(self) -> None:
        payload = MaintenanceRecordIn(
            equipmentId=3,
            date="2026-05-19",
            technicianName="이민준",
            type="preventive",
            result="restored",
            duration=65,
            actions={"grease": True, "bearing": False, "seal": False},
            partsReplaced="Mobilux EP 2",
            actualFaultTypeCode="bearing_fault",
            note="진동 감소 확인",
            nextPlan="2026-06-19 재점검",
        )

        with SessionLocal() as db:
            created = create_maintenance_record(payload, db=db)
            history = read_maintenance_history(3, db=db)

        self.assertTrue(created["data"]["saved"])
        self.assertTrue(created["data"]["learningQueueId"].startswith("LQ-"))
        self.assertGreaterEqual(created["data"]["maintenanceRecordId"], 1)
        self.assertEqual(3, len(history["data"]))
        self.assertEqual("2026-05-19", history["data"][0]["date"])


if __name__ == "__main__":
    unittest.main()
