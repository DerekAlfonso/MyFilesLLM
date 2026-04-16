# search.py — Interactive Q&A over indexed files.
"""
Retrieves semantically relevant file chunks from Qdrant, then optionally
passes them as context to a local LLM via Ollama to generate an answer.

Works without Ollama — if Ollama is not running, the relevant files and
excerpts are displayed without an AI-generated answer.

Usage
-----
  python search.py                      # interactive REPL
  python search.py "your question"      # single-shot query
  python search.py "question" --no-llm  # search only, skip LLM
  python search.py --no-llm             # REPL without LLM
"""

from __future__ import annotations

import argparse
import concurrent.futures
import sys
import logging
import warnings

from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from config import (
    EMBED_MODEL,
    QDRANT_URL,
    QDRANT_API_KEY,
    QDRANT_VERIFY_SSL,
    COLLECTION_NAME,
    OLLAMA_HOST,
    OLLAMA_MODEL,
    TOP_K_RESULTS,
    SEARCH_TIMEOUT_SECONDS,
)

warnings.filterwarnings("ignore", message="The following layers were not sharded")
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
# or suppress the transformers loader specifically:
logging.getLogger("transformers.modeling_utils").setLevel(logging.ERROR)

console = Console()

# ── Embedding model & Qdrant ──────────────────────────────────────────────────
import torch
_device = "cuda" if torch.cuda.is_available() else "cpu"
_model = SentenceTransformer(EMBED_MODEL, device=_device)
_client = QdrantClient(
    url=QDRANT_URL,
    api_key=QDRANT_API_KEY or None,
    verify=QDRANT_VERIFY_SSL,
)


def _embed(text: str) -> list[float]:
    return _model.encode(text, normalize_embeddings=True).tolist()


# ── Ollama availability ───────────────────────────────────────────────────────

def _ollama_available() -> bool:
    """Probe Ollama with a short timeout. Returns False on any failure."""
    try:
        import httpx
        r = httpx.get(f"{OLLAMA_HOST}/api/tags", timeout=2.0)
        return r.status_code == 200
    except Exception:
        return False


# ── Vector search ─────────────────────────────────────────────────────────────

def semantic_search(question: str, k: int = TOP_K_RESULTS) -> dict:
    """Return top-k records sorted by cosine similarity to the question."""
    total = _client.count(collection_name=COLLECTION_NAME, exact=True).count
    if total == 0:
        return {"documents": [[]], "metadatas": [[]], "distances": [[]]}

    response = _client.query_points(
        collection_name=COLLECTION_NAME,
        query=_embed(question),
        limit=min(k, total),
        with_payload=True,
    )
    results = response.points

    docs      = [r.payload.get("document", "") for r in results]
    metas     = [{key: val for key, val in r.payload.items() if key != "document"} for r in results]
    distances = [1.0 - r.score for r in results]  # cosine similarity → distance

    return {"documents": [docs], "metadatas": [metas], "distances": [distances]}


# ── Result display ────────────────────────────────────────────────────────────

def _render_sources(metas: list[dict], distances: list[float]) -> None:
    """Print a Rich table of unique source files ordered by relevance."""
    # Deduplicate by file_path, keeping the best (lowest distance) match per file
    best: dict[str, tuple[dict, float]] = {}
    for meta, dist in zip(metas, distances):
        fp = meta.get("file_path", "")
        if fp not in best or dist < best[fp][1]:
            best[fp] = (meta, dist)

    table = Table(
        title="Relevant Files",
        box=box.ROUNDED,
        show_lines=True,
        highlight=True,
        expand=False,
    )
    table.add_column("#",        style="dim",         width=3,  justify="right")
    table.add_column("File",     style="bold cyan",   no_wrap=True)
    table.add_column("Score",    style="bold green",  width=7,  justify="right")
    table.add_column("Modified", style="yellow",      width=20)
    table.add_column("Indexed",  style="dim",         width=8,  justify="center")
    table.add_column("Path",     style="dim",         overflow="fold")

    for rank, (fp, (meta, dist)) in enumerate(
        sorted(best.items(), key=lambda x: x[1][1]), start=1
    ):
        similarity = f"{(1.0 - dist) * 100:.1f}%"
        indexed = "yes" if meta.get("content_indexed") else "meta"
        table.add_row(
            str(rank),
            meta.get("file_name", "?"),
            similarity,
            meta.get("date_modified", "?"),
            indexed,
            fp,
        )

    console.print(table)


# ── LLM answer ────────────────────────────────────────────────────────────────

def _ask_llm(question: str, docs: list[str], metas: list[dict]) -> None:
    """Stream an LLM answer.  Gracefully handles import errors and connection failures."""
    try:
        import ollama as _ollama
    except ImportError:
        console.print(
            "[yellow]The 'ollama' Python package is not installed.[/yellow]\n"
            "  Run: [bold]pip install ollama[/bold]"
        )
        return

    # Build context block — include file attribution before each chunk
    context_parts: list[str] = []
    for doc, meta in zip(docs, metas):
        header = (
            f"[File: {meta.get('file_name', '?')} | "
            f"Path: {meta.get('file_path', '?')} | "
            f"Modified: {meta.get('date_modified', '?')}]"
        )
        context_parts.append(f"{header}\n{doc}")
    context = "\n\n---\n\n".join(context_parts)

    prompt = (
        "You are a helpful assistant that answers questions based on the user's local files.\n\n"
        "CONTEXT FROM FILES:\n"
        f"{context}\n\n"
        f"USER QUESTION: {question}\n\n"
        "Instructions:\n"
        "- Answer the question using only the context above.\n"
        "- If the answer is directly present, provide it clearly and concisely.\n"
        "- Always cite the specific file name(s) where you found the relevant information.\n"
        "- If the content only partially answers the question, say so and note where to look.\n"
        "- If no relevant content was found, say so honestly.\n"
    )

    console.print()
    console.rule("[bold green]AI Answer[/bold green]")

    try:
        client = _ollama.Client(host=OLLAMA_HOST, timeout=SEARCH_TIMEOUT_SECONDS)
        stream = client.chat(
            model=OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}],
            stream=True,
        )
        for chunk in stream:
            delta = chunk.get("message", {}).get("content", "")
            if delta:
                console.print(delta, end="", markup=False)
        console.print()  # final newline
    except Exception as exc:
        console.print(
            f"\n[red]Ollama error:[/red] {exc}\n"
            "[dim]Make sure Ollama is running: [bold]ollama serve[/bold][/dim]\n"
            f"[dim]And that the model is pulled: [bold]ollama pull {OLLAMA_MODEL}[/bold][/dim]"
        )


# ── Main ask function ─────────────────────────────────────────────────────────

def ask(question: str, use_llm: bool = True) -> None:
    """Run a full search + optional LLM answer for a question."""
    if _client.count(collection_name=COLLECTION_NAME, exact=True).count == 0:
        console.print(
            "[red]The index is empty.[/red] Run [bold]python indexer.py[/bold] first."
        )
        return

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(semantic_search, question)
            results = future.result(timeout=SEARCH_TIMEOUT_SECONDS)
    except concurrent.futures.TimeoutError:
        console.print(
            f"\n[yellow]Search timed out after {SEARCH_TIMEOUT_SECONDS:.0f} s.[/yellow] "
            "The index or network may be slow — please try again."
        )
        return
    except Exception as exc:
        console.print(f"\n[red]Search error:[/red] {exc}")
        return

    if not results or not results["documents"][0]:
        console.print("[yellow]No results found for that query.[/yellow]")
        return

    docs      = results["documents"][0]
    metas     = results["metadatas"][0]
    distances = results["distances"][0]

    console.rule(f"[bold]Query:[/bold] {question}")
    _render_sources(metas, distances)

    if not use_llm:
        return

    if not _ollama_available():
        console.print(
            "\n[yellow]Ollama is not running — showing search results only.[/yellow]\n"
            "[dim]To enable AI answers, start Ollama: [bold]ollama serve[/bold]\n"
            f"And pull a model: [bold]ollama pull {OLLAMA_MODEL}[/bold][/dim]"
        )
        return

    _ask_llm(question, docs, metas)


# ── CLI entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="FileIndexer search — ask questions about your indexed files"
    )
    parser.add_argument(
        "query", nargs="?", default=None,
        help="Question to ask (omit for interactive REPL)"
    )
    parser.add_argument(
        "--no-llm", action="store_true",
        help="Show search results only, skip the LLM answer"
    )
    args = parser.parse_args()

    use_llm = not args.no_llm

    if args.query:
        ask(args.query, use_llm=use_llm)
    else:
        llm_label = "OFF (use --no-llm to always disable)" if use_llm else "OFF"
        console.print(Panel(
            f"[bold]FileIndexer Search[/bold]\n"
            f"LLM answers: {'[green]ON[/green]' if use_llm else '[yellow]OFF[/yellow]'}\n\n"
            "Type a question and press Enter.  Type [bold]quit[/bold] or press Ctrl-C to exit.",
            title="[bold cyan]FileIndexer[/bold cyan]",
            expand=False,
        ))
        while True:
            try:
                question = console.input("\n[bold cyan]> [/bold cyan]").strip()
            except (KeyboardInterrupt, EOFError):
                console.print("\n[dim]Bye.[/dim]")
                break
            if question.lower() in {"quit", "exit", "q", ""}:
                if question.lower() in {"quit", "exit", "q"}:
                    console.print("[dim]Bye.[/dim]")
                    break
                continue
            ask(question, use_llm=use_llm)
