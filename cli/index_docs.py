#!/usr/bin/env python3
"""CLI tool to clone a GitHub repo and build a BM25S search index from its documentation."""
import json
import sys
from pathlib import Path

import bm25s
import click
import Stemmer
from git import Repo


def _clone_or_pull(repo_url: str, local_path: Path, token: str | None = None) -> Repo:
    """Clone repo if not exists, otherwise pull latest."""
    if token and repo_url.startswith("https://"):
        repo_url = repo_url.replace("https://", f"https://{token}@", 1)

    if local_path.exists() and (local_path / ".git").exists():
        click.echo(f"Pulling latest from {local_path}...")
        repo = Repo(local_path)
        repo.remotes.origin.pull()
    else:
        click.echo(f"Cloning {repo_url} to {local_path}...")
        repo = Repo.clone_from(repo_url, local_path)
    return repo


def _find_doc_files(repo_path: Path) -> list[Path]:
    """Recursively find all markdown and text files."""
    files = []
    for ext in ("*.md", "*.txt", "*.rst"):
        files.extend(repo_path.rglob(ext))
    files = [f for f in files if ".git" not in f.parts]
    return sorted(files)


def _chunk_text(text: str, source: str, max_chars: int = 500) -> list[dict]:
    """Split text into chunks by paragraph, max max_chars each."""
    chunks = []
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    current = []
    current_len = 0

    for para in paragraphs:
        if current_len + len(para) > max_chars and current:
            chunks.append({"text": "\n\n".join(current), "source": source})
            current = [para]
            current_len = len(para)
        else:
            current.append(para)
            current_len += len(para)

    if current:
        chunks.append({"text": "\n\n".join(current), "source": source})

    return chunks


@click.command()
@click.option("--repo-url", required=True, help="GitHub repo URL to clone/pull")
@click.option("--index-path", default="./doc_index", show_default=True, help="Path to save the BM25S index")
@click.option("--token", default=None, envvar="GITHUB_TOKEN", help="GitHub personal access token for private repos")
@click.option("--repo-dir", default=None, help="Local directory to clone into (default: <index-path>/repo)")
def main(repo_url: str, index_path: str, token: str | None, repo_dir: str | None):
    """Clone a GitHub repo and build a BM25S search index from its documentation files."""
    index_path = Path(index_path)
    index_path.mkdir(parents=True, exist_ok=True)

    if repo_dir is None:
        repo_dir = index_path / "repo"
    else:
        repo_dir = Path(repo_dir)

    _clone_or_pull(repo_url, repo_dir, token)

    doc_files = _find_doc_files(repo_dir)
    click.echo(f"Found {len(doc_files)} documentation files")

    all_chunks = []
    for f in doc_files:
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
            rel_path = str(f.relative_to(repo_dir))
            chunks = _chunk_text(text, source=rel_path)
            all_chunks.extend(chunks)
        except Exception as e:
            click.echo(f"Warning: could not read {f}: {e}", err=True)

    if not all_chunks:
        click.echo("No content found to index.", err=True)
        sys.exit(1)

    click.echo(f"Building BM25S index from {len(all_chunks)} chunks...")

    stemmer = Stemmer.Stemmer("english")
    corpus_tokens = bm25s.tokenize(
        [c["text"] for c in all_chunks],
        stopwords="en",
        stemmer=stemmer,
    )
    retriever = bm25s.BM25()
    retriever.index(corpus_tokens)

    retriever.save(str(index_path / "bm25s_index"), corpus=corpus_tokens)

    chunks_path = index_path / "chunks.json"
    with open(chunks_path, "w") as f:
        json.dump(all_chunks, f)

    click.echo(f"Index saved to {index_path}/bm25s_index")
    click.echo(f"Chunks metadata saved to {chunks_path}")
    click.echo(f"Total chunks indexed: {len(all_chunks)}")


if __name__ == "__main__":
    main()
