import hashlib
import json

import chromadb
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
from app.config import (
    CHROMA_CHUNK_COLLECTION,
    CHROMA_LEGAL_COLLECTION,
    CHROMA_PERSIST_DIRECTORY,
    EMBEDDING_MODEL,
    OPENAI_API_KEY,
)

# ── 1) OpenAI API 키 로딩 및 임베딩 함수 설정
api_key = OPENAI_API_KEY
if not api_key:
    raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다")

embedding_function = OpenAIEmbeddingFunction(api_key=api_key)

# ── 2) Chroma Client 초기화 및 컬렉션 준비
client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIRECTORY)
collection = client.get_or_create_collection(
    name="property_docs",
    embedding_function=embedding_function
)


def document_id(doc: dict) -> str:
    if doc.get("id"):
        return str(doc["id"])

    payload = json.dumps(
        {"text": doc["text"], "metadata": doc.get("metadata", {})},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return f"doc-{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"


# ── 3) Upsert 함수
def upsert_property_docs(docs: list[dict]):
    unique_docs = {document_id(doc): doc for doc in docs}
    ids = list(unique_docs)
    texts = [doc["text"] for doc in unique_docs.values()]
    metadatas = [doc.get("metadata", {}) for doc in unique_docs.values()]
    collection.upsert(
        documents=texts,
        metadatas=metadatas,
        ids=ids
    )

# ── 4) Query 함수
def query_similar_documents(query: str, n_results: int = 5) -> list[dict]:
    results = collection.query(
        query_texts=[query],
        n_results=n_results
    )
    ids = results["ids"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]
    return [
        {"id": iid, "metadata": meta, "distance": dist}
        for iid, meta, dist in zip(ids, metadatas, distances)
    ]

# ── 5) 분석 결과 저장 함수
def store_full_analysis(case_id: str, summary: str, score: dict, address: str):
    collection.upsert(
        documents=[summary],
        metadatas=[{
            "score": score["score"],
            "grade": score["grade"],
            "reasons": ", ".join(score.get("reasons", [])) if isinstance(score.get("reasons"), list) else "",
            "address": address
        }],
        ids=[f"analyzed-{case_id}"]
    )

# ── 6) 등기부 + 건축물대장 메타데이터 정리
def build_vector_docs(registry_list, building_list):
    docs = []
    for reg, bld in zip(registry_list, building_list):
        case_id = reg["case_id"]
        text = (
            f"[등기부등본] 소유자: {reg['owner_name']}, 용도: {reg['building_purpose']}, 구조: {reg['building_structure']}, "
            f"전용면적: {reg['area_exclusive']}, 공유면적: {reg['area_shared']}, 연면적: {reg['area_total']}, "
            f"준공년도: {reg['construction_year']}, 권리사항: {reg.get('rights', [])}. "
            f"[건축물대장] 소유자: {bld['owner_name']}, 용도: {bld['building_purpose']}, 구조: {bld['building_structure']}, "
            f"전용면적: {bld['area_exclusive']}, 공유면적: {bld['area_shared']}, 연면적: {bld['area_total']}, "
            f"준공년도: {bld['construction_year']}, 승인일: {bld['approval_date']}."
        )
        docs.append({
            "id": case_id,
            "text": text,
            "metadata": {"address": reg["address"]}
        })
    upsert_property_docs(docs)


# ── 7) 청크 단위 저장소 (분석 건별 case_id 로 검색 범위를 제한한다)
_chunk_store = None
_legal_store = None


def get_chunk_store():
    """청크 컬렉션은 기존 property_docs 와 분리한다 (임베딩 모델과 거리 함수가 다르다)."""
    global _chunk_store
    if _chunk_store is None:
        from app.services.chunk_store import ChunkStore
        chunk_collection = client.get_or_create_collection(
            name=CHROMA_CHUNK_COLLECTION,
            embedding_function=OpenAIEmbeddingFunction(api_key=api_key, model_name=EMBEDDING_MODEL),
            metadata={"hnsw:space": "cosine"},
        )
        _chunk_store = ChunkStore(chunk_collection)
    return _chunk_store


def get_legal_store():
    """법률·전세계약 자료는 개별 매물 문서와 섞이지 않게 별도 컬렉션에 저장한다."""
    global _legal_store
    if _legal_store is None:
        from app.services.chunk_store import ChunkStore
        legal_collection = client.get_or_create_collection(
            name=CHROMA_LEGAL_COLLECTION,
            embedding_function=OpenAIEmbeddingFunction(api_key=api_key, model_name=EMBEDDING_MODEL),
            metadata={"hnsw:space": "cosine"},
        )
        _legal_store = ChunkStore(legal_collection)
    return _legal_store
