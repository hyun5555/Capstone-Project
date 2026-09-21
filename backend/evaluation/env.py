# backend/evaluation/env.py
"""평가에 쓰는 외부 부품을 만든다. 실제(ChromaDB + OpenAI)와 dry-run(가짜)."""
import shutil
import tempfile
import uuid
from typing import List

from app.services.chunk_store import ChunkStore
from evaluation.runner import Config, Environment, TrackingStore


def build_dry_env() -> Environment:
    from app.services.explain_chain import make_llm_call
    from evaluation.fake_store import FakeCollection
    from evaluation.fakes import FakeChatModel

    def make_store(size: int, overlap: int) -> TrackingStore:
        return TrackingStore(ChunkStore(FakeCollection()))

    def make_llm(config: Config, callbacks: list):
        return make_llm_call(config.prompt_version, llm=FakeChatModel(), callbacks=callbacks)

    return Environment(make_store, make_llm, dry_run=True)


class RealEnvironment:
    """임시 폴더에 ChromaDB 를 만들고 끝나면 지운다. 운영 데이터(chroma_data)는 건드리지 않는다."""

    def __init__(self):
        from app.config import EMBEDDING_MODEL, OPENAI_API_KEY
        if not OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY 가 설정되지 않았습니다. backend/.env 를 확인하거나 --dry-run 으로 실행하세요.")
        import chromadb
        from chromadb.config import Settings

        self._key, self._model = OPENAI_API_KEY, EMBEDDING_MODEL
        self._dir = tempfile.mkdtemp(prefix="eval_chroma_")
        self._client = chromadb.PersistentClient(path=self._dir, settings=Settings(anonymized_telemetry=False))
        self._run = uuid.uuid4().hex[:8]
        self._llms = {}

    def make_store(self, size: int, overlap: int) -> TrackingStore:
        from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
        collection = self._client.create_collection(
            name=f"eval{self._run}s{size}o{overlap}",
            embedding_function=OpenAIEmbeddingFunction(api_key=self._key, model_name=self._model),
            metadata={"hnsw:space": "cosine"},
        )
        return TrackingStore(ChunkStore(collection))

    def make_llm_call(self, config: Config, callbacks: List):
        from app.services.explain_chain import get_llm, make_llm_call
        if config.json_mode not in self._llms:
            self._llms[config.json_mode] = get_llm(config.json_mode)
        return make_llm_call(config.prompt_version, llm=self._llms[config.json_mode], callbacks=callbacks)

    def environment(self) -> Environment:
        return Environment(self.make_store, self.make_llm_call, dry_run=False)

    def close(self):
        shutil.rmtree(self._dir, ignore_errors=True)
