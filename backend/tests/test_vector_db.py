import os
import tempfile
import unittest


_chroma_dir = tempfile.TemporaryDirectory()
os.environ["CHROMA_PERSIST_DIRECTORY"] = _chroma_dir.name

from app.services.vector_db import document_id


class DocumentIdTest(unittest.TestCase):
    def test_same_document_has_same_id(self):
        first = {"text": "등기부 청크", "metadata": {"source": "registry", "page": 1}}
        second = {"metadata": {"page": 1, "source": "registry"}, "text": "등기부 청크"}

        self.assertEqual(document_id(first), document_id(second))


if __name__ == "__main__":
    unittest.main()
