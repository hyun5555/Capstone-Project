# backend/app/services/lc_retriever.py
"""
ChunkStore(ChromaDB)를 LangChain 리트리버 인터페이스로 감싼다.

- 검색 결과를 langchain_core.documents.Document (page_content + metadata) 로 돌려준다.
- 항상 분석 한 건(case_id)의 청크만 검색한다. 다른 사용자의 문서가 섞여 나오지 않는다.
- balanced=True 이면 등기부/건축물대장 청크를 각각 하나 이상 포함한다 (chunk_store.select_balanced).
- LangChain 표준 인터페이스라서 retriever.invoke(질의) 로 호출하고, 콜백/트레이싱(LangSmith 등)에 잡힌다.
"""
from typing import Any, List, Optional

from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

from app.services.chunk_store import select_balanced

# balanced 로 고를 때 먼저 가져올 후보 수 (Top-K 의 몇 배). 한 분석 건의 청크는 보통 수십 개 이하다.
BALANCED_POOL_FACTOR = 4
BALANCED_POOL_MIN = 12


class CaseChunkRetriever(BaseRetriever):
    store: Any                      # ChunkStore
    case_id: str
    top_k: int = 3
    doc_type: Optional[str] = None  # "registry" | "building" 로 한정 (없으면 둘 다)
    balanced: bool = False

    def _get_relevant_documents(self, query: str, *, run_manager: CallbackManagerForRetrieverRun) -> List[Document]:
        use_balance = self.balanced and not self.doc_type
        pool = max(self.top_k * BALANCED_POOL_FACTOR, BALANCED_POOL_MIN) if use_balance else self.top_k
        hits = self.store.search(self.case_id, [query], n_results=pool, doc_type=self.doc_type)[0]
        hits = select_balanced(hits, self.top_k) if use_balance else hits[: self.top_k]
        return [
            Document(
                page_content=h["text"],
                metadata={**h["metadata"], "chunk_id": h["id"], "distance": h["distance"]},
            )
            for h in hits
        ]
