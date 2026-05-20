import unittest

from sqlalchemy import func, select

from app.db.models import KnowledgeChunk, KnowledgeDocument
from app.db.seed import seed_demo_data
from app.db.seed_manuals import load_manual_documents, seed_manual_knowledge_with_session
from app.db.session import SessionLocal, engine
from app.services.knowledge import search_chunks


class SeedManualsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        seed_demo_data()

    @classmethod
    def tearDownClass(cls) -> None:
        engine.dispose()

    def test_load_manual_documents_reads_markdown_sources(self) -> None:
        manuals = load_manual_documents()
        ls240_manual = next(item for item in manuals if item["equipment_model_id"] == 2)

        self.assertEqual(3, len(manuals))
        self.assertEqual("LS240-B 설비 운영 매뉴얼", ls240_manual["title"])
        self.assertEqual("docs/manuals/ls240b_manual.md", ls240_manual["file_uri"])
        self.assertEqual("유압 펌프 베어링 정비 절차", ls240_manual["chunks"][0]["heading"])
        self.assertEqual("LS240-B-4.3", ls240_manual["chunks"][0]["metadata"]["section"])
        self.assertIn("베어링 이상음", ls240_manual["chunks"][0]["body"])

    def test_seed_manuals_creates_searchable_manual_for_each_equipment_model(self) -> None:
        with SessionLocal() as db:
            result = seed_manual_knowledge_with_session(db)
            db.commit()
            document_count = db.execute(select(func.count()).select_from(KnowledgeDocument)).scalar_one()
            chunk_count = db.execute(select(func.count()).select_from(KnowledgeChunk)).scalar_one()
            ls240_document = db.execute(
                select(KnowledgeDocument).where(KnowledgeDocument.equipment_model_id == 2)
            ).scalar_one()
            ls240_results = search_chunks(db, "LS240-B 베어링 유압 정비", equipment_model_id=2, limit=1)

        self.assertEqual(3, result["documents"])
        self.assertGreaterEqual(result["chunks"], 9)
        self.assertEqual(3, document_count)
        self.assertGreaterEqual(chunk_count, 9)
        self.assertEqual("docs/manuals/ls240b_manual.md", ls240_document.file_uri)
        self.assertEqual("LS240-B 설비 운영 매뉴얼", ls240_results[0].title)
        self.assertIn("베어링", ls240_results[0].heading or "")

    def test_seed_manuals_is_idempotent(self) -> None:
        with SessionLocal() as db:
            seed_manual_knowledge_with_session(db)
            seed_manual_knowledge_with_session(db)
            db.commit()
            document_count = db.execute(select(func.count()).select_from(KnowledgeDocument)).scalar_one()
            chunk_count = db.execute(select(func.count()).select_from(KnowledgeChunk)).scalar_one()

        self.assertEqual(3, document_count)
        self.assertEqual(9, chunk_count)


if __name__ == "__main__":
    unittest.main()
