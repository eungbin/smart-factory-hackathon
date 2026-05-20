import unittest

from app.api.knowledge import create_knowledge_chunks, create_knowledge_document, search_knowledge
from app.db.seed import seed_demo_data
from app.db.session import SessionLocal, engine
from app.schemas.knowledge import KnowledgeChunkIn, KnowledgeChunksIn, KnowledgeDocumentIn


class KnowledgeApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        seed_demo_data()

    @classmethod
    def tearDownClass(cls) -> None:
        engine.dispose()

    def test_can_store_chunks_and_search_by_query(self) -> None:
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
            chunks = create_knowledge_chunks(
                document["documentId"],
                KnowledgeChunksIn(
                    chunks=[
                        KnowledgeChunkIn(
                            chunkNo=1,
                            heading="유압 펌프 베어링 정비 절차",
                            body="베어링 이상음이 발생하면 전원 차단 후 유압 잔압을 해제하고 그리스 보충 상태를 확인한다.",
                            metadata={"section": "4.3"},
                        ),
                        KnowledgeChunkIn(
                            chunkNo=2,
                            heading="냉각수 배관 점검",
                            body="냉각수 누수 여부와 배관 체결 상태를 확인한다.",
                            metadata={"section": "5.1"},
                        ),
                    ]
                ),
                db=db,
            )["data"]
            results = search_knowledge(q="베어링 정비", equipmentModelId=2, limit=1, db=db)["data"]

        self.assertEqual(2, chunks["inserted"])
        self.assertEqual(1, len(results))
        self.assertEqual("유압 펌프 베어링 정비 절차", results[0]["heading"])
        self.assertEqual("설비 운영 매뉴얼 §4.3", results[0]["sourceLabel"])
        self.assertGreater(results[0]["score"], 0)


if __name__ == "__main__":
    unittest.main()
