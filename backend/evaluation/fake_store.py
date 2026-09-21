# backend/evaluation/fake_store.py
"""Chroma 컬렉션 흉내 (단어 겹침 기반 거리). dry-run 과 테스트에서 쓴다. langchain 에 의존하지 않는다."""


class FakeCollection:
    """Chroma 컬렉션 흉내: upsert/get/query/delete, where($and 포함), 단어 겹침 기반 거리."""

    def __init__(self):
        self.rows = {}

    def upsert(self, ids, documents, metadatas):
        for i, d, m in zip(ids, documents, metadatas):
            self.rows[i] = (d, m)

    @staticmethod
    def _match(meta, where):
        if "$and" in where:
            return all(FakeCollection._match(meta, w) for w in where["$and"])
        return all(meta.get(k) == v for k, v in where.items())

    def get(self, where=None, include=None):
        return {"ids": [i for i, (_, m) in self.rows.items() if self._match(m, where or {})]}

    def query(self, query_texts, n_results, where=None):
        out = {"ids": [], "documents": [], "metadatas": [], "distances": []}
        for q in query_texts:
            qt = set(q.split())
            scored = []
            for i, (d, m) in self.rows.items():
                if self._match(m, where or {}):
                    scored.append((1 - len(qt & set(d.split())) / max(len(qt), 1), i, d, m))
            scored.sort(key=lambda x: x[0])
            top = scored[:n_results]
            out["ids"].append([t[1] for t in top])
            out["documents"].append([t[2] for t in top])
            out["metadatas"].append([t[3] for t in top])
            out["distances"].append([t[0] for t in top])
        return out

    def delete(self, where):
        for i in self.get(where)["ids"]:
            del self.rows[i]
