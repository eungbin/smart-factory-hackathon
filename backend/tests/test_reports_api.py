import unittest
from datetime import date

from app.api.maintenance import create_maintenance_record
from app.api.reports import read_monthly_report
from app.db.seed import seed_demo_data
from app.db.session import SessionLocal, engine
from app.schemas.maintenance import MaintenanceRecordIn


class ReportsApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        seed_demo_data()

    @classmethod
    def tearDownClass(cls) -> None:
        engine.dispose()

    def test_read_monthly_report_returns_frontend_report_shape(self) -> None:
        with SessionLocal() as db:
            response = read_monthly_report(db=db)

        data = response["data"]
        current_month = date.today().strftime("%Y-%m")

        self.assertEqual(current_month, data["month"])
        self.assertEqual(6, len(data["availableMonths"]))
        self.assertEqual(current_month, data["availableMonths"][-1]["month"])
        self.assertEqual(
            {
                "unplannedDowntimeHours",
                "preventedCount",
                "mttrMinutes",
                "learningDataCount",
            },
            set(data["kpis"].keys()),
        )
        self.assertEqual(6, len(data["monthlyStats"]))
        self.assertEqual({"month", "downtime", "prevented", "mttr"}, set(data["monthlyStats"][0].keys()))

    def test_read_seed_month_uses_seed_report_data(self) -> None:
        with SessionLocal() as db:
            response = read_monthly_report(month="2026-04", db=db)

        data = response["data"]

        self.assertEqual("2026-04", data["month"])
        self.assertEqual(
            {
                "unplannedDowntimeHours",
                "preventedCount",
                "mttrMinutes",
                "learningDataCount",
            },
            set(data["kpis"].keys()),
        )
        self.assertEqual(6, len(data["monthlyStats"]))
        self.assertEqual({"month", "downtime", "prevented", "mttr"}, set(data["monthlyStats"][0].keys()))
        self.assertEqual(5, len(data["faultDistribution"]))
        self.assertEqual({"name", "value", "color"}, set(data["faultDistribution"][0].keys()))
        self.assertEqual(4, len(data["insights"]))
        self.assertEqual({"icon", "title", "body", "priority"}, set(data["insights"][0].keys()))
        self.assertEqual(3, len(data["learnedKnowledge"]))
        self.assertEqual({"id", "equip", "content", "confidence", "date"}, set(data["learnedKnowledge"][0].keys()))

    def test_current_month_report_reflects_maintenance_and_learning_queue(self) -> None:
        seed_demo_data()
        payload = MaintenanceRecordIn(
            equipmentId=3,
            date="2026-05-19",
            technicianName="이민준",
            type="예방 정비",
            result="정상 복구",
            duration=65,
            actions={"grease": True, "bearing": True, "seal": False},
            partsReplaced="베어링 #6205-2RS",
            actualFaultTypeCode="bearing_fault",
            aiAccuracyNote="베어링 불량 - AI 진단과 일치",
            note="베어링 교체 후 진동 감소 확인",
            nextPlan="2026-06-19 재점검",
        )

        with SessionLocal() as db:
            create_maintenance_record(payload, db=db)
            response = read_monthly_report(month="2026-05", db=db)

        data = response["data"]
        last_stat = data["monthlyStats"][-1]

        self.assertEqual("2026-05", data["month"])
        self.assertEqual(0, data["kpis"]["unplannedDowntimeHours"])
        self.assertEqual(1, data["kpis"]["preventedCount"])
        self.assertEqual(65, data["kpis"]["mttrMinutes"])
        self.assertEqual(1, data["kpis"]["learningDataCount"])
        self.assertEqual({"month": "5월", "downtime": 0, "prevented": 1, "mttr": 65}, last_stat)
        self.assertEqual({"name": "베어링 불량", "value": 100, "color": "#f87171"}, data["faultDistribution"][0])
        self.assertEqual("LQ-000005", data["learnedKnowledge"][0]["id"])
        self.assertIn("베어링 교체", data["learnedKnowledge"][0]["content"])


if __name__ == "__main__":
    unittest.main()
