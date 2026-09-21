# backend/app/services/chunk_store.py
"""
청크를 ChromaDB 컬렉션에 저장하고 "분석 한 건(case_id)의 청크만" 검색한다.

컬렉션 객체를 밖에서 받아서 쓰므로 chromadb / OpenAI 없이도 테스트할 수 있다.
실제 컬렉션(OpenAI 임베딩 연결)은 vector_db.get_chunk_store() 가 만들어 준다.
"""
from __future__ import annotations

import threading
from typing import Optional


def case_filter(case_id: str, doc_type: Optional[str] = None) -> dict:
    if doc_type:
        return {"$and": [{"case_id": case_id}, {"doc_type": doc_type}]}
    return {"case_id": case_id}


def select_balanced(hits: list, k: int) -> list:
    """
    가까운 순으로 정렬된 검색 결과에서 k 개를 고르되, 문서 종류(등기부/건축물대장)가 다르면 각 종류의 가장 가까운 청크를
    먼저 하나씩 넣는다. 두 문서를 비교하는 항목은 양쪽 근거가 다 있어야 설명할 수 있기 때문이다.
    남는 자리는 가까운 순으로 채우고, 결과는 다시 가까운 순으로 정렬한다.
    """
    if k <= 0 or not hits:
        return []
    if k == 1:
        return hits[:1]
    chosen, seen_types = [], set()
    for h in hits:
        doc_type = h["metadata"].get("doc_type")
        if doc_type not in seen_types:
            seen_types.add(doc_type)
            chosen.append(h)
            if len(chosen) == k:
                break
    ids = {h["id"] for h in chosen}
    for h in hits:
        if len(chosen) >= k:
            break
        if h["id"] not in ids:
            chosen.append(h)
            ids.add(h["id"])
    return sorted(chosen, key=lambda h: h["distance"])


class ChunkStore:
    """ChromaDB 컬렉션 호출은 한 번에 하나씩 실행한다. (chromadb 의 텔레메트리 집계가 스레드 안전하지 않아 동시에 부르면
    KeyError 가 난다. FastAPI 는 동기 엔드포인트를 스레드풀에서 돌리므로 요청이 겹치면 실제로 일어날 수 있다.)"""

    def __init__(self, collection):
        self._c = collection
        self._lock = threading.RLock()

    def upsert(self, chunks) -> int:
        chunks = list({c.id: c for c in chunks}.values())          # 같은 ID 는 하나로
        if not chunks:
            return 0
        with self._lock:
            self._c.upsert(
                ids=[c.id for c in chunks],
                documents=[c.text for c in chunks],
                metadatas=[c.metadata for c in chunks],
            )
        return len(chunks)

    def count(self, case_id: str) -> int:
        with self._lock:
            return len(self._c.get(where=case_filter(case_id), include=[])["ids"])

    def search(self, case_id: str, queries: list, n_results: int = 3, doc_type: Optional[str] = None) -> list:
        """질의마다 [{id, text, metadata, distance}, ...] 를 가까운 순으로 돌려준다. 다른 case 의 청크는 나오지 않는다."""
        if not queries:
            return []
        where = case_filter(case_id, doc_type)
        with self._lock:
            available = len(self._c.get(where=where, include=[])["ids"])
            if available == 0:
                return [[] for _ in queries]
            res = self._c.query(query_texts=list(queries), n_results=min(n_results, available), where=where)
        out = []
        for i in range(len(queries)):
            out.append([
                {"id": cid, "text": text, "metadata": meta, "distance": dist}
                for cid, text, meta, dist in zip(res["ids"][i], res["documents"][i], res["metadatas"][i], res["distances"][i])
            ])
        return out

    def delete_case(self, case_id: str) -> None:
        with self._lock:
            self._c.delete(where=case_filter(case_id))
