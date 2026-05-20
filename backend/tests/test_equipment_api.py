import unittest

from fastapi import HTTPException

from app.api.equipment import read_equipment, read_equipment_list
from app.db.seed import seed_demo_data
from app.db.session import SessionLocal, engine


class EquipmentApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        seed_demo_data()

    @classmethod
    def tearDownClass(cls) -> None:
        engine.dispose()

    def test_read_equipment_list_returns_frontend_equipment_shape(self) -> None:
        with SessionLocal() as db:
            response = read_equipment_list(db=db)

        items = response["data"]

        self.assertEqual(8, len(items))
        self.assertEqual(
            {
                "id",
                "name",
                "model",
                "year",
                "status",
                "rul",
                "rulMin",
                "rulMax",
                "risk",
                "lastMaint",
                "nextPlan",
                "sensors",
                "faultType",
                "faultConf",
                "faultTop3",
            },
            set(items[0].keys()),
        )
        self.assertEqual(
            {"vibration", "temp", "current", "pressure"},
            set(items[0]["sensors"].keys()),
        )

    def test_read_equipment_includes_structural_fault_top3(self) -> None:
        with SessionLocal() as db:
            response = read_equipment(3, db=db)

        item = response["data"]

        self.assertGreaterEqual(len(item["faultTop3"]), 1)
        self.assertLessEqual(len(item["faultTop3"]), 3)
        self.assertEqual(
            {"faultTypeCode", "faultType", "probability"},
            set(item["faultTop3"][0].keys()),
        )
        self.assertEqual(item["faultType"], item["faultTop3"][0]["faultType"])

    def test_read_equipment_list_can_filter_by_status(self) -> None:
        with SessionLocal() as db:
            response = read_equipment_list(status="danger", db=db)

        self.assertEqual(1, len(response["data"]))
        self.assertEqual("danger", response["data"][0]["status"])
        self.assertEqual("3호 사출기", response["data"][0]["name"])

    def test_read_equipment_returns_404_for_missing_equipment(self) -> None:
        with SessionLocal() as db:
            with self.assertRaises(HTTPException) as raised:
                read_equipment(9999, db=db)

        self.assertEqual(404, raised.exception.status_code)
        self.assertEqual(
            {"error": {"code": "equipment_not_found", "message": "설비를 찾을 수 없습니다.", "details": {}}},
            raised.exception.detail,
        )


if __name__ == "__main__":
    unittest.main()
