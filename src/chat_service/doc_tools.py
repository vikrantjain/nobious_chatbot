import json
import logging
from pathlib import Path
from typing import Any

from langchain_core.tools import tool

from src.chat_service.config import config

logger = logging.getLogger(__name__)

_retriever = None
_chunks: list[dict] = []
_stemmer = None


def _load_index():
    global _retriever, _chunks, _stemmer
    import bm25s
    import Stemmer

    doc_index_path = config.doc_index_path
    index_dir = Path(doc_index_path)
    chunks_path = index_dir / "chunks.json"
    index_path = index_dir / "bm25s_index"

    if not chunks_path.exists() or not index_path.exists():
        logger.warning(f"BM25S index not found at {doc_index_path}. Run cli/index_docs.py first.")
        return

    try:
        _stemmer = Stemmer.Stemmer("english")
        _retriever = bm25s.BM25.load(str(index_path), load_corpus=True)
        with open(chunks_path) as f:
            _chunks = json.load(f)
        logger.info(f"Loaded BM25S index with {len(_chunks)} chunks from {doc_index_path}")
    except Exception as e:
        logger.error(f"Failed to load BM25S index: {e}")


_load_index()


@tool
def search_documentation(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    """Search Nobious IMS documentation using full-text BM25S search.
    Returns ranked documentation chunks relevant to the query.

    Args:
        query: The search query string
        top_k: Number of top results to return (default 5)

    Returns:
        List of dicts with keys: rank, score, text, source
    """
    if _retriever is None or not _chunks:
        logger.warning("Documentation index not loaded, returning empty results")
        return []

    try:
        import bm25s

        query_tokens = bm25s.tokenize(query, stopwords="en", stemmer=_stemmer)
        results, scores = _retriever.retrieve(query_tokens, k=min(top_k, len(_chunks)))

        output = []
        for rank, (doc_idx, score) in enumerate(zip(results[0], scores[0])):
            chunk = _chunks[int(doc_idx)]
            output.append({
                "rank": rank + 1,
                "score": float(score),
                "text": chunk["text"],
                "source": chunk["source"],
            })
        return output
    except Exception as e:
        logger.error(f"Search error: {e}")
        return []


DOC_TOOLS = [search_documentation]
