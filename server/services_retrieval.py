from collections import Counter
from models import SourceDocument


def split_chunks(text: str, chunk_size: int = 900, overlap: int = 120) -> list[str]:
    if not text:
        return []
    chunks: list[str] = []
    i = 0
    while i < len(text):
        chunks.append(text[i : i + chunk_size])
        i += max(1, chunk_size - overlap)
    return chunks


def keyword_score(query: str, body: str) -> float:
    q_tokens = [t for t in query.lower().split() if t]
    b_tokens = body.lower().split()
    if not q_tokens or not b_tokens:
        return 0.0
    q = Counter(q_tokens)
    b = Counter(b_tokens)
    return float(sum(min(q[token], b.get(token, 0)) for token in q))


def retrieve_top_sources(query: str, docs: list[SourceDocument], limit: int = 5) -> list[dict]:
    scored = []
    for doc in docs:
        score = keyword_score(query, doc.body or "")
        scored.append(
            {
                "source_id": doc.id,
                "title": doc.title,
                "score": score,
                "excerpt": (doc.body or "")[:320],
            }
        )
    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:limit]
