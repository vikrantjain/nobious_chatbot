import json

import pytest
from pathlib import Path


def test_find_doc_files(tmp_path):
    """Test that _find_doc_files finds markdown and text files."""
    from cli.index_docs import _find_doc_files

    doc_dir = tmp_path / "docs"
    doc_dir.mkdir()
    (doc_dir / "intro.md").write_text("# Introduction\n\nThis is the Nobious IMS system.")
    (doc_dir / "guide.txt").write_text("User guide content here.")
    (doc_dir / "code.py").write_text("print('not a doc')")

    files = _find_doc_files(doc_dir)
    assert len(files) == 2
    assert all(f.suffix in (".md", ".txt") for f in files)


def test_chunk_text_splits_correctly():
    """Test that text chunking splits by paragraphs."""
    from cli.index_docs import _chunk_text

    text = "Para 1.\n\nPara 2.\n\nPara 3."
    chunks = _chunk_text(text, "test.md", max_chars=20)
    assert len(chunks) >= 2
    assert all("text" in c and "source" in c for c in chunks)


def test_chunk_text_single_chunk():
    """Test short text stays as one chunk."""
    from cli.index_docs import _chunk_text

    text = "Short paragraph."
    chunks = _chunk_text(text, "test.md", max_chars=500)
    assert len(chunks) == 1
    assert chunks[0]["text"] == "Short paragraph."
    assert chunks[0]["source"] == "test.md"


def test_search_documentation_no_index():
    """Test search returns empty list when index is not loaded."""
    import src.chat_service.doc_tools as doc_tools

    original = doc_tools._retriever
    doc_tools._retriever = None

    result = doc_tools.search_documentation.invoke({"query": "test query"})
    assert result == []

    doc_tools._retriever = original


def test_search_documentation_with_index():
    """Test search returns results when index is loaded."""
    import bm25s
    import Stemmer
    import src.chat_service.doc_tools as doc_tools

    chunks = [
        {"text": "Nobious IMS manages inventory items at multiple locations.", "source": "intro.md"},
        {"text": "Use the search function to find materials by SKU.", "source": "guide.md"},
        {"text": "Allocation history shows all item movements.", "source": "guide.md"},
    ]

    stemmer = Stemmer.Stemmer("english")
    corpus_tokens = bm25s.tokenize([c["text"] for c in chunks], stopwords="en", stemmer=stemmer)
    retriever = bm25s.BM25()
    retriever.index(corpus_tokens)

    original_retriever = doc_tools._retriever
    original_chunks = doc_tools._chunks
    original_stemmer = doc_tools._stemmer

    doc_tools._retriever = retriever
    doc_tools._chunks = chunks
    doc_tools._stemmer = stemmer

    try:
        results = doc_tools.search_documentation.invoke({"query": "inventory items", "top_k": 2})
        assert isinstance(results, list)
        assert len(results) <= 2
        if results:
            assert "rank" in results[0]
            assert "score" in results[0]
            assert "text" in results[0]
            assert "source" in results[0]
    finally:
        doc_tools._retriever = original_retriever
        doc_tools._chunks = original_chunks
        doc_tools._stemmer = original_stemmer
