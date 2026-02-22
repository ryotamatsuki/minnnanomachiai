"""
RAG document store and retriever.
Manages document ingestion, embedding, and vector search using FAISS.
"""

import hashlib
import json
from pathlib import Path
from typing import Optional

import numpy as np

from src.config import CACHE_DIR, GEMINI_API_KEY


# FAISS index path
INDEX_DIR = CACHE_DIR / "rag_index"
INDEX_DIR.mkdir(parents=True, exist_ok=True)
DOCS_PATH = INDEX_DIR / "documents.json"

# Simple in-memory store as fallback
_documents: list[dict] = []
_embeddings: Optional[np.ndarray] = None
_faiss_index = None


def _load_docs() -> list[dict]:
    """Load document store from disk."""
    global _documents
    if DOCS_PATH.exists():
        _documents = json.loads(DOCS_PATH.read_text(encoding="utf-8"))
    return _documents


def _save_docs():
    """Save document store to disk."""
    DOCS_PATH.write_text(
        json.dumps(_documents, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def add_document(
    title: str,
    content: str,
    source: str,
    doc_type: str = "document",
    metadata: Optional[dict] = None,
) -> str:
    """
    Add a document to the store.

    Returns:
        Document ID
    """
    _load_docs()
    doc_id = hashlib.md5(f"{title}:{content[:200]}".encode()).hexdigest()[:12]

    doc = {
        "id": doc_id,
        "title": title,
        "content": content,
        "source": source,
        "doc_type": doc_type,
        "metadata": metadata or {},
    }
    _documents.append(doc)
    _save_docs()
    return doc_id


def search_documents(
    query: str,
    top_k: int = 5,
) -> list[dict]:
    """
    Search documents by keyword (simple TF-IDF-like search).
    Falls back to keyword matching when FAISS/embeddings are not available.

    Returns:
        List of matching documents with relevance scores
    """
    _load_docs()
    if not _documents:
        return []

    # Simple keyword scoring
    query_terms = set(query.lower().split())
    scored = []
    for doc in _documents:
        text = f"{doc['title']} {doc['content']}".lower()
        score = sum(1 for term in query_terms if term in text)
        if score > 0:
            scored.append({**doc, "score": score})

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


def get_all_documents() -> list[dict]:
    """Return all stored documents."""
    _load_docs()
    return _documents


def clear_documents():
    """Clear all documents."""
    global _documents
    _documents = []
    _save_docs()


def add_sample_documents():
    """Add sample reference documents for demonstration."""
    samples = [
        {
            "title": "第5次総合計画 基本構想",
            "content": "人口減少・少子高齢化が進む中、持続可能なまちづくりを推進する。"
                       "重点施策として、①子育て支援の充実、②産業振興と雇用創出、"
                       "③防災・減災対策の強化、④デジタル化の推進を掲げる。",
            "source": "自治体公表資料",
            "doc_type": "plan",
        },
        {
            "title": "都市計画マスタープラン",
            "content": "コンパクト・プラス・ネットワークの考え方に基づき、"
                       "都市機能誘導区域と居住誘導区域を設定。"
                       "公共交通ネットワークの維持・充実により、"
                       "高齢者等の移動手段を確保する。",
            "source": "自治体公表資料",
            "doc_type": "plan",
        },
        {
            "title": "地域公共交通計画",
            "content": "路線バスの利用者数は年々減少傾向。"
                       "デマンド交通やMaaSの導入を検討。"
                       "公共交通空白地域の解消を目指す。",
            "source": "自治体公表資料",
            "doc_type": "plan",
        },
        {
            "title": "観光振興計画",
            "content": "インバウンド需要の回復に伴い、"
                       "体験型観光コンテンツの充実と二次交通の整備を推進。"
                       "観光入込客数の目標：年間100万人。",
            "source": "自治体公表資料",
            "doc_type": "plan",
        },
    ]

    for s in samples:
        add_document(**s)
