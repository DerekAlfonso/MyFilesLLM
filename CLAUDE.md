# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

**FileIndexer** — a local file semantic-search system. It crawls directories, embeds file content with `sentence-transformers`, stores vectors in a remote Qdrant instance, and answers natural-language questions about the files via Ollama.

## Setup & common commands

```bash
# First-time setup (creates .venv, installs deps)
setup.bat

# Activate venv (PowerShell)
.venv\Scripts\Activate.ps1

# Install / update dependencies
pip install -r requirements.txt

# Index all configured paths
python indexer.py

# Index with useful flags
python indexer.py --force      # re-index everything regardless of mtime
python indexer.py --cleanup    # remove records for deleted files
python indexer.py --stats      # show collection record counts
python indexer.py --file PATH  # index a single file

# Search / Q&A
python search.py               # interactive REPL
python search.py "question"    # single-shot
python search.py "question" --no-llm  # search only, no Ollama

# Real-time watcher
python watcher.py              # continuous watch (Ctrl-C to stop)
python watcher.py --once       # one-shot scan then exit (Task Scheduler)
```

There are no automated tests or a linter configured in this project.

## Configuration

**`config.py` is the only file users should need to edit.** Key settings:

| Setting | Purpose |
|---|---|
| `WATCH_PATHS` | Directories to index |
| `SKIP_DIRS` / `SKIP_FILES` | Exclusion lists |
| `CONTENT_EXTENSIONS` | Extensions that get full text extraction — documents (`.docx`, `.xlsx`, `.xls`, `.pdf`) and plain text/code (`.txt`, `.md`, `.py`, `.cs`, `.js`, `.json`, `.yml`, `.yaml`, `.php`) — all others get metadata-only records |
| `HF_TOKEN` | HuggingFace API token — set when using gated models; populates `HF_TOKEN` env var at startup |
| `EMBED_MODEL` | sentence-transformers model name |
| `QDRANT_URL` | Qdrant REST endpoint (`https://dxp4800.local:6333`) |
| `QDRANT_API_KEY` | Leave empty when Qdrant auth is disabled |
| `QDRANT_VERIFY_SSL` | `False` for self-signed TLS certs |
| `COLLECTION_NAME` | Qdrant collection (auto-created on first run) |
| `OLLAMA_HOST` / `OLLAMA_MODEL` | LLM used for Q&A answers |

## Architecture

### Data flow

```
File on disk
  └─► indexer.py: _file_stat() → change detection via mtime_ns
        ├─ meta-only record   (all file types)
        └─ content chunks     (CONTENT_EXTENSIONS only, via _PARSERS)
              └─► sentence-transformers: _embed() / _embed_batch()
                    └─► Qdrant upsert (REST via qdrant-client)
```

### Qdrant record structure

Every point's payload carries all metadata fields plus a `"document"` key holding the embedded text. Two `record_type` values exist:

- `"meta"` — one per file; payload includes `mtime_ns` (change detection), `total_chunks` (needed to reconstruct chunk IDs for deletion), `content_indexed` flag.
- `"chunk"` — one per text chunk; payload includes `chunk_index`.

Point IDs are **UUID5s** derived deterministically from string keys of the form `{md5(normalised_path)}_meta` and `{md5(normalised_path)}_chunk_{n}`. This means IDs are stable across runs and can be reconstructed without querying Qdrant first (critical for efficient deletion).

### Change detection

`_needs_reindex(path)` retrieves the `mtime_ns` field from the meta point and compares it with `os.stat().st_mtime_ns`. No file content is read. A missing point or any exception → treat as needing re-index.

### Watcher threading model

`watcher.py` uses `watchdog.observers.Observer` (background thread) + a `threading.Lock`-guarded dict of `threading.Timer`s for per-file debouncing. Timers fire `index_file` or `remove_file` from `indexer.py`. The file `watchdog.py` at the repo root is a **deprecated stub** — `watcher.py` works around it by temporarily removing the project directory from `sys.path` before importing the installed `watchdog` package.

### Search result format

`semantic_search()` in `search.py` returns a dict `{"documents": [[...]], "metadatas": [[...]], "distances": [[...]]}` — intentionally shaped like ChromaDB's response so `_render_sources()` and `_ask_llm()` remain unchanged. Qdrant returns cosine *similarity* scores; these are converted to *distances* as `distance = 1 - score`.
