import os
import unittest

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
os.environ.setdefault("SECRET_KEY", "test-secret-key-at-least-32-bytes-long")

from evaluation.pdf_golden import run_pdf_golden


class PdfGoldenTest(unittest.TestCase):
    def test_deidentified_document_pipeline_matches_gold(self):
        results = run_pdf_golden()
        self.assertTrue(results)
        self.assertTrue(all(item["ok"] for item in results), results)


if __name__ == "__main__":
    unittest.main()
