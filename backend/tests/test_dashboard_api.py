import unittest

from app.api.dashboard import read_dashboard
from app.db.seed import seed_demo_data
from app.db.session import SessionLocal, engine


class DashboardApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        seed_demo_data()

    @classmethod
    def tearDownClass(cls) -> None:
        engine.dispose()

    def test_read_dashboard_returns_summary_alerts_and_equipment(self) -> None:
        with SessionLocal() as db:
            response = read_dashboard(db=db)

        data = response["data"]

        self.assertEqual(
            {
                "totalEquipment": 8,
                "dangerCount": 1,
                "warnCount": 2,
                "normalCount": 5,
                "monthlyUptimePct": 96.2,
            },
            data["summary"],
        )
        self.assertEqual(8, len(data["equipment"]))
        self.assertEqual(3, len(data["alerts"]))
        self.assertEqual(
            {
                "id": 101,
                "equipmentId": 3,
                "equipmentName": "3호 사출기",
                "level": "danger",
                "title": "즉시 점검 필요",
                "rulHours": 72,
                "rulRangeText": "72h (±24h)",
                "riskPct": 78,
                "faultType": "베어링 불량",
            },
            data["alerts"][0],
        )

    def test_read_dashboard_respects_factory_id(self) -> None:
        with SessionLocal() as db:
            response = read_dashboard(factory_id=999, db=db)

        self.assertEqual(
            {
                "totalEquipment": 0,
                "dangerCount": 0,
                "warnCount": 0,
                "normalCount": 0,
                "monthlyUptimePct": 96.2,
            },
            response["data"]["summary"],
        )
        self.assertEqual([], response["data"]["alerts"])
        self.assertEqual([], response["data"]["equipment"])


if __name__ == "__main__":
    unittest.main()
