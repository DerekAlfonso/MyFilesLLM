@echo off
REM setup.bat — First-time setup for FileIndexer on Windows.
REM Run from the FileIndexer directory.

setlocal enabledelayedexpansion
cd /d "%~dp0"

echo.
echo ============================================================
echo  FileIndexer Setup
echo ============================================================
echo.

REM ── Check Python ──────────────────────────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found on PATH.
    echo         Install Python 3.10+ from https://python.org
    echo         Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)
for /f "tokens=2 delims= " %%V in ('python --version 2^>^&1') do set PYVER=%%V
echo [OK] Python %PYVER% found.

REM ── Create virtual environment ────────────────────────────────────────────────
if not exist ".venv\Scripts\activate.bat" (
    echo.
    echo Creating virtual environment in .venv...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created.
) else (
    echo [OK] Virtual environment already exists.
)

REM ── Activate and upgrade pip ──────────────────────────────────────────────────
echo.
echo Activating virtual environment...
call .venv\Scripts\activate.bat

echo Upgrading pip...
python -m pip install --upgrade pip --quiet
if errorlevel 1 (
    echo [WARN] pip upgrade failed — continuing anyway.
)

REM ── Detect NVIDIA GPU and install matching PyTorch ───────────────────────────
echo.
echo Detecting GPU for PyTorch variant selection...

set TORCH_INDEX=https://download.pytorch.org/whl/cpu
set TORCH_VARIANT=CPU-only

for /f "tokens=1,2 delims=|" %%A in ('python detect_cuda.py') do (
    set TORCH_INDEX=%%A
    set TORCH_VARIANT=%%B
)

echo [OK] PyTorch variant: %TORCH_VARIANT%
echo Installing PyTorch... (this will take a few minutes)
pip install torch --index-url %TORCH_INDEX%
if errorlevel 1 (
    echo [WARN] PyTorch install failed — continuing; sentence-transformers will pull a default build.
)

REM ── Install dependencies ──────────────────────────────────────────────────────
echo.
echo Installing dependencies (this may take a few minutes)...
pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [ERROR] pip install failed.
    echo         Check your internet connection and review the error above.
    pause
    exit /b 1
)
echo [OK] Dependencies installed.

REM ── Verify imports ────────────────────────────────────────────────────────────
echo.
echo Verifying key imports...
python -c "import torch, sentence_transformers, watchdog, fitz, docx, openpyxl, xlrd, rich, httpx; cuda=torch.cuda.is_available(); print('[OK] All imports successful. torch.cuda.is_available() =', cuda)"
if errorlevel 1 (
    echo [WARN] One or more imports failed — check the output above.
)

REM ── Ollama reminder ───────────────────────────────────────────────────────────
echo.
echo ============================================================
echo  Ollama setup (for AI-generated answers)
echo ============================================================
echo.
echo  FileIndexer works WITHOUT Ollama — it will still find and
echo  display relevant files.  Ollama enables natural-language
echo  answers generated from your file contents.
echo.
echo  1. Download and install Ollama: https://ollama.com
echo  2. Open a new terminal and run:  ollama pull llama3.2
echo     (or choose a different model in config.py)
echo.

REM ── Edit config.py ────────────────────────────────────────────────────────────
echo ============================================================
echo  Configuration
echo ============================================================
echo.
echo  Edit config.py to set WATCH_PATHS to your directories.
echo  Default is:  H:\Nextcloud\Work
echo.

REM ── Optional initial index ────────────────────────────────────────────────────
echo ============================================================
echo  Run initial index?
echo ============================================================
echo.
echo  This will scan your WATCH_PATHS and build the vector database.
echo  It downloads the embedding model (~90 MB) on first run and
echo  may take several minutes depending on how many files you have.
echo.
set /p RUN_INDEX="Start indexing now? (y/N): "
if /i "%RUN_INDEX%"=="y" (
    echo.
    echo Running indexer...
    python indexer.py
    if errorlevel 1 (
        echo [ERROR] Indexer failed — see output above.
        pause
        exit /b 1
    )
)

REM ── Done ──────────────────────────────────────────────────────────────────────
echo.
echo ============================================================
echo  Setup complete!
echo.
echo  Quick reference (run from this directory):
echo.
echo    Index your files:
echo      .venv\Scripts\python.exe indexer.py
echo.
echo    Re-index everything (force):
echo      .venv\Scripts\python.exe indexer.py --force
echo.
echo    Remove records for deleted files:
echo      .venv\Scripts\python.exe indexer.py --cleanup
echo.
echo    Show index statistics:
echo      .venv\Scripts\python.exe indexer.py --stats
echo.
echo    Search (interactive):
echo      .venv\Scripts\python.exe search.py
echo.
echo    Search (single question):
echo      .venv\Scripts\python.exe search.py "your question here"
echo.
echo    Watch for file changes (real-time updates):
echo      .venv\Scripts\python.exe watcher.py
echo.
echo    Schedule automatic updates with Windows Task Scheduler:
echo      Program:   .venv\Scripts\python.exe
echo      Arguments: watcher.py --once
echo      Start in:  %CD%
echo ============================================================
echo.
pause
