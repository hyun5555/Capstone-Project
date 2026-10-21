import os
import unittest
from pathlib import Path
from unittest.mock import patch

import pymupdf
from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
os.environ.setdefault("SECRET_KEY", "test-secret")

from app.api.endpoints import analyze as analyze_endpoint
from app.services.chunk_store import ChunkStore
from app.services.chunker import chunk_document
from app.services.document_source import load_pdf_documents
from app.services.evidence import collect_evidence
from app.services.pdf_extractor import ExtractedPage, ExtractedPdf, PdfContentError, extract_pdf
from app.services.pdf_normalizer import normalize_registry_pdf

FIXTURES = Path(__file__).resolve().parent / "fixtures"
ADDRESS = "서울특별시 강남구 테스트로 100"


def fixture(name):
    return (FIXTURES / name).read_bytes()


def simple_pdf(text="plain text " * 20):
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


class FakeCollection:
    def __init__(self):
        self.rows = {}

    def upsert(self, ids, documents, metadatas):
        for item_id, text, metadata in zip(ids, documents, metadatas):
            self.rows[item_id] = (text, metadata)

    def get(self, where=None, include=None):
        return {"ids": [item_id for item_id, (_, meta) in self.rows.items() if self._match(meta, where or {})]}

    def query(self, query_texts, n_results, where=None):
        rows = [(item_id, text, meta) for item_id, (text, meta) in self.rows.items() if self._match(meta, where or {})]
        rows = rows[:n_results]
        return {
            "ids": [[row[0] for row in rows] for _ in query_texts],
            "documents": [[row[1] for row in rows] for _ in query_texts],
            "metadatas": [[row[2] for row in rows] for _ in query_texts],
            "distances": [[0.1 + i / 100 for i in range(len(rows))] for _ in query_texts],
        }

    @staticmethod
    def _match(meta, where):
        if "$and" in where:
            return all(FakeCollection._match(meta, item) for item in where["$and"])
        return all(meta.get(key) == value for key, value in where.items())


class PdfPipelineTest(unittest.TestCase):
    def test_text_pdfs_are_normalized_without_ocr(self):
        docs = load_pdf_documents(fixture("registry_safe.pdf"), fixture("building_safe.pdf"), ADDRESS)

        self.assertEqual(docs.source, "pdf")
        self.assertEqual(docs.processing["registry"]["ocr_pages"], [])
        self.assertEqual(docs.registry.owner_names, ["이임대"])
        self.assertEqual(docs.registry.max_claim_amount, 80_000_000)
        self.assertEqual(docs.building.owner_names, ["이임대"])
        self.assertEqual(docs.building.usage, "공동주택(아파트)")
        self.assertTrue(all(section.page_no == 1 for section in docs.registry.sections))

    def test_image_only_page_uses_ocr_fallback(self):
        image_only = simple_pdf("")
        with patch("app.services.pdf_extractor._ocr_page", return_value="등기사항전부증명서 " * 5):
            result = extract_pdf(image_only)
        self.assertEqual(result.processing()["ocr_pages"], [1])

    def test_arbitrary_pdf_is_rejected_as_wrong_document(self):
        pdf = extract_pdf(simple_pdf())
        with self.assertRaises(PdfContentError):
            normalize_registry_pdf(pdf, ADDRESS)

    def test_ocr_spacing_and_number_noise_are_normalized(self):
        text = """등기사항전부증명서
서울특별시강남구테스트로100
표제부
철근콘크리트구조 공동주택(아파트)
갑구
1 소유권이전2019년3월2일원인매매소유자이임대800101-*******
을구
1 근저당권설정 채권최고액 금80,/000,000원"""
        doc = normalize_registry_pdf(ExtractedPdf([ExtractedPage(1, text, "ocr")]), ADDRESS)

        self.assertEqual(doc.owner_names, ["이임대"])
        self.assertEqual(doc.max_claim_amount, 80_000_000)

    def test_address_mismatch_is_rejected(self):
        with self.assertRaises(PdfContentError):
            load_pdf_documents(
                fixture("registry_safe.pdf"), fixture("building_safe.pdf"), "부산광역시 남구 다른로 1"
            )

    def test_pdf_chunks_are_masked_and_keep_page_numbers(self):
        docs = load_pdf_documents(fixture("registry_safe.pdf"), fixture("building_safe.pdf"), ADDRESS)
        chunks = chunk_document(docs.registry, "case-pdf", 600, 100) + chunk_document(
            docs.building, "case-pdf", 600, 100
        )
        text = "\n".join(chunk.text for chunk in chunks)
        self.assertNotIn("이임대", text)
        self.assertNotIn("800101", text)
        self.assertTrue(all(chunk.metadata["page_no"] == 1 for chunk in chunks))

        _, evidence = collect_evidence(ChunkStore(FakeCollection()), docs.registry, docs.building, 600, 100, 3)
        self.assertTrue(any(item.get("page_no") == 1 for items in evidence.values() for item in items))

    def test_upload_endpoint_runs_end_to_end(self):
        app = FastAPI()
        app.include_router(analyze_endpoint.router, prefix="/analyze")
        client = TestClient(app)
        with patch("app.api.endpoints.analyze.OPENAI_API_KEY", ""), patch(
            "app.services.risk_score.check_defaulter", return_value=False
        ):
            response = client.post(
                "/analyze/pdf",
                files={
                    "registry_pdf": ("registry.pdf", fixture("registry_safe.pdf"), "application/pdf"),
                    "building_pdf": ("building.pdf", fixture("building_safe.pdf"), "application/pdf"),
                },
                data={"address": ADDRESS, "deposit": "300000000", "marketPrice": "500000000"},
            )

        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        data = result["data"]
        self.assertTrue(result["success"])
        self.assertEqual(data["data_source"], "pdf")
        self.assertEqual(data["risk_grade"], "안전")
        self.assertEqual(data["document_processing"]["registry"]["pages"], 1)
        self.assertEqual(len(data["risk_items"]), 6)

        wrong = client.post(
            "/analyze/pdf",
            files={
                "registry_pdf": ("wrong.pdf", simple_pdf(), "application/pdf"),
                "building_pdf": ("building.pdf", fixture("building_safe.pdf"), "application/pdf"),
            },
            data={"address": ADDRESS, "deposit": "300000000"},
        )
        self.assertEqual(wrong.status_code, 422)


if __name__ == "__main__":
    unittest.main()
