# config.py — Central configuration for FileIndexer.
# This is the only file you need to edit.

import os

# ── 1. Directories to index ────────────────────────────────────────────────────
# All subdirectories are included automatically.
WATCH_PATHS: list[str] = [
    r"H:\Nextcloud\Work",
    # r"C:\Users\Derek\Documents",
    # r"D:\Projects",
]

# ── 2. Directory names that are always skipped during scanning ─────────────────
SKIP_DIRS: set[str] = {
    ".git",
    "__pycache__",
    ".venv", "venv", ".env",
    "node_modules",
    ".idea", ".vscode",
    "$RECYCLE.BIN",
    "System Volume Information",
}

# ── 3. File names silently skipped at the file level ──────────────────────────
SKIP_FILES: set[str] = {
    "desktop.ini",
    "Thumbs.db",
    ".DS_Store",
}

# ── 4. Extensions whose *content* is extracted and embedded ───────────────────
# Every other file type still gets a searchable metadata record.
# Add or remove extensions here to control which file types are fully indexed.
CONTENT_EXTENSIONS: set[str] = {
    # Documents
    ".docx", ".xlsx", ".xls", ".pdf",
    # Plain text / code
    ".txt", ".md", ".py", ".cs", ".js", ".json", ".yml", ".yaml", ".php",
}

# ── 5. Text chunking ──────────────────────────────────────────────────────────
CHUNK_SIZE: int = 800     # target characters per chunk
CHUNK_OVERLAP: int = 100  # character overlap between adjacent chunks

# ── 6. HuggingFace API token (optional) ──────────────────────────────────────
# Required for gated models (e.g. nomic-embed-text-v1).
# Generate a token at: https://huggingface.co/settings/tokens
# Leave empty if you are only using public models like all-MiniLM-L6-v2.
HF_TOKEN: str = ""

# ── 7. Embedding model (sentence-transformers, no Ollama needed) ───────────────
# Downloaded once to the sentence-transformers cache (~90 MB for the default).
# Alternatives:
#   "all-mpnet-base-v2"             ~420 MB, higher accuracy
#   "nomic-ai/nomic-embed-text-v1"  ~270 MB, strong retrieval quality
EMBED_MODEL: str = "all-MiniLM-L6-v2"
#   "all-MiniLM-L6-v2"              ~90 MB, default

# ── 8. Vector database (Qdrant) ───────────────────────────────────────────────
# REST API endpoint of your Qdrant instance.
QDRANT_URL: str = "http://dxp4800.local:6333"

# API key for Qdrant authentication.  Leave empty if authentication is disabled.
QDRANT_API_KEY: str = ""

# Set to False when your Qdrant server uses a self-signed TLS certificate.
QDRANT_VERIFY_SSL: bool = False

COLLECTION_NAME: str = "documents"

# ── 9. LLM via Ollama (only needed for Q&A, not for indexing) ─────────────────
# Install Ollama: https://ollama.com
# Then pull a model: ollama pull llama3.2
#
# Recommended models by VRAM / RAM:
#   llama3.2        ~2 GB RAM   fast, good quality   (default)
#   mistral         ~4 GB RAM   very good quality
#   llama3.1:8b     ~5 GB RAM   strong reasoning
#   phi3:medium     ~8 GB RAM   excellent, slower
OLLAMA_HOST:  str = "http://localhost:11434"
OLLAMA_MODEL: str = "llama3.2"

# ── 10. Watcher ───────────────────────────────────────────────────────────────
# Seconds to wait after the last filesystem event before re-indexing a file.
# Prevents re-indexing mid-save when applications write files in multiple bursts.
DEBOUNCE_SECONDS: float = 3.0

# ── 11. Search limits ─────────────────────────────────────────────────────────
MAX_FILE_SIZE_MB: float = 50.0  # files larger than this skip content extraction
TOP_K_RESULTS:    int = 10      # number of chunks retrieved per search query
SEARCH_TIMEOUT_SECONDS: float = 15.0  # max seconds to wait for a search query before giving up
INDEX_RETRY_LIMIT: int = 3      # max attempts when a timeout occurs while indexing a file
