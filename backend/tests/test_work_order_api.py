import os
import unittest

from fastapi import HTTPException
from sqlalchemy import text

from app.api.predictions import run_prediction
from app.api.work_orders import create_work_order
from app.api.knowledge import create_knowledge_chunks, create_knowledge_document
from app.core.config import get_settings
from app.db.seed import seed_demo_data
from app.db.session import SessionLocal, engine
from app.schemas.knowledge import KnowledgeChunkIn, KnowledgeChunksIn, KnowledgeDocumentIn
from app.schemas.predictions import PredictionRunIn
from app.schemas.work_orders import WorkOrderGenerateIn


class WorkOrderApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        seed_demo_data()

    @classmethod
    def tearDownClass(cls) -> None:
        engine.dispose()

    def test_create_work_order_returns_frontend_work_order_shape(self) -> None:
        with SessionLocal() as db:
            response = create_work_order(WorkOrderGenerateIn(equipmentId=3), db=db)

        data = response["data"]

        self.assertEqual(3, data["equipId"])
        self.assertIn("3", data["equipName"])
        self.assertEqual(
            {
                "id",
                "equipId",
                "equipName",
                "generatedAt",
                "rul",
                "risk",
                "faultType",
                "rootSensors",
                "source",
                "status",
                "steps",
                "parts",
                "totalTime",
                "techLevel",
                "caution",
            },
            set(data.keys()),
        )
        self.assertGreaterEqual(len(data["steps"]), 1)
        self.assertGreaterEqual(len(data["parts"]), 1)

    def test_create_work_order_uses_latest_root_sensors_after_multiple_predictions(self) -> None:
        seed_demo_data()

        with SessionLocal() as db:
            first = run_prediction(PredictionRunIn(equipmentId=3), db=db)["data"]
            second = run_prediction(PredictionRunIn(equipmentId=3), db=db)["data"]
            response = create_work_order(WorkOrderGenerateIn(equipmentId=3), db=db)

        self.assertGreater(second["predictionRunId"], first["predictionRunId"])
        self.assertEqual(second["rootSensors"][0]["displayText"], response["data"]["rootSensors"][0])

    def test_create_work_order_persists_header_steps_and_parts(self) -> None:
        seed_demo_data()

        with SessionLocal() as db:
            response = create_work_order(WorkOrderGenerateIn(equipmentId=3), db=db)
            order = response["data"]

            saved_order = db.execute(
                text(
                    """
                    select equipment_id, status, generator_provider, source_summary
                    from work_orders
                    where id = :id
                    """
                ),
                {"id": order["id"]},
            ).mappings().one()
            saved_step_count = db.execute(
                text("select count(*) from work_order_steps where work_order_id = :id"),
                {"id": order["id"]},
            ).scalar_one()
            saved_part_count = db.execute(
                text("select count(*) from work_order_parts where work_order_id = :id"),
                {"id": order["id"]},
            ).scalar_one()

        self.assertEqual(3, saved_order["equipment_id"])
        self.assertEqual("generated", saved_order["status"])
        self.assertEqual("template", saved_order["generator_provider"])
        self.assertEqual(order["source"], saved_order["source_summary"])
        self.assertEqual(len(order["steps"]), saved_step_count)
        self.assertEqual(len(order["parts"]), saved_part_count)

    def test_create_work_order_persists_generator_result_metadata(self) -> None:
        seed_demo_data()

        with SessionLocal() as db:
            response = create_work_order(WorkOrderGenerateIn(equipmentId=3), db=db)
            order = response["data"]
            saved_order = db.execute(
                text(
                    """
                    select generator_provider, generator_model, raw_response
                    from work_orders
                    where id = :id
                    """
                ),
                {"id": order["id"]},
            ).mappings().one()

        self.assertEqual("template", saved_order["generator_provider"])
        self.assertEqual("template-v1", saved_order["generator_model"])
        self.assertEqual("template", saved_order["raw_response"]["provider"])
        self.assertEqual("template-v1", saved_order["raw_response"]["model"])

    def test_create_work_order_falls_back_when_selected_llm_provider_is_not_ready(self) -> None:
        seed_demo_data()
        old_provider = os.environ.get("WORK_ORDER_GENERATOR_PROVIDER")
        os.environ["WORK_ORDER_GENERATOR_PROVIDER"] = "gemini"
        get_settings.cache_clear()

        try:
            with SessionLocal() as db:
                response = create_work_order(WorkOrderGenerateIn(equipmentId=3), db=db)
                order = response["data"]
                saved_order = db.execute(
                    text(
                        """
                        select generator_provider, generator_model, raw_response
                        from work_orders
                        where id = :id
                        """
                    ),
                    {"id": order["id"]},
                ).mappings().one()
        finally:
            if old_provider is None:
                os.environ.pop("WORK_ORDER_GENERATOR_PROVIDER", None)
            else:
                os.environ["WORK_ORDER_GENERATOR_PROVIDER"] = old_provider
            get_settings.cache_clear()

        self.assertEqual("template", saved_order["generator_provider"])
        self.assertEqual("template-v1", saved_order["generator_model"])
        self.assertEqual("gemini", saved_order["raw_response"]["fallbackFrom"])
        self.assertEqual("provider_not_configured", saved_order["raw_response"]["fallbackReasonCode"])

    def test_create_work_order_uses_rag_source_when_knowledge_exists(self) -> None:
        seed_demo_data()

        with SessionLocal() as db:
            document = create_knowledge_document(
                KnowledgeDocumentIn(
                    factoryId=1,
                    title="LS240-B 유압 펌프 정비 매뉴얼",
                    documentType="manual",
                    equipmentModelId=2,
                    fileName="ls240b_manual.pdf",
                    fileUri="file://manuals/ls240b_manual.pdf",
                    sourceLabel="설비 운영 매뉴얼 §4.3",
                ),
                db=db,
            )["data"]
            create_knowledge_chunks(
                document["documentId"],
                KnowledgeChunksIn(
                    chunks=[
                        KnowledgeChunkIn(
                            chunkNo=1,
                            heading="유압 펌프 베어링 정비 절차",
                            body="베어링 이상음이 발생하면 전원 차단 후 유압 잔압을 해제하고 그리스 상태를 확인한다.",
                            metadata={"section": "4.3"},
                        )
                    ]
                ),
                db=db,
            )
            response = create_work_order(WorkOrderGenerateIn(equipmentId=3), db=db)
            order = response["data"]
            saved_source = db.execute(
                text(
                    """
                    select source_label, knowledge_chunk_id, relevance_score
                    from work_order_sources
                    where work_order_id = :id
                    """
                ),
                {"id": order["id"]},
            ).mappings().one()

        self.assertEqual("설비 운영 매뉴얼 §4.3 - 유압 펌프 베어링 정비 절차", order["source"])
        self.assertEqual("설비 운영 매뉴얼 §4.3", saved_source["source_label"])
        self.assertGreater(saved_source["knowledge_chunk_id"], 0)
        self.assertGreater(saved_source["relevance_score"], 0)

    def test_create_work_order_returns_404_for_missing_equipment(self) -> None:
        with SessionLocal() as db:
            with self.assertRaises(HTTPException) as raised:
                create_work_order(WorkOrderGenerateIn(equipmentId=9999), db=db)

        self.assertEqual(404, raised.exception.status_code)


if __name__ == "__main__":
    unittest.main()
