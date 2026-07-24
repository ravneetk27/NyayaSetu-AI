# Draft Agent — Setup Guide

A step-by-step guide to get the Draft Agent running on your local machine.

---

## Prerequisites

Before you begin, ensure you have the following installed:

| Requirement | Version | Purpose |
|---|---|---|
| **Python** | 3.11 or higher | Backend runtime |
| **Ollama** | Latest | Local LLM inference engine |
| **Git** | Any | Version control (optional) |
| **Web Browser** | Chrome / Edge / Firefox | Frontend UI |

---

## Step 1: Install Ollama & Pull the Model

### 1.1 Install Ollama

Download and install Ollama from [https://ollama.ai](https://ollama.ai).

### 1.2 Pull the LLM Model

Open a terminal and run:

```bash
ollama pull llama3.2:1b
```

> **Note:** The default model is `llama3.2:1b` (lightweight, runs on CPU). You can use a larger model like `llama3.2:3b` or `qwen3:4b` for better quality — just update the `LLM_MODEL` environment variable (see [Configuration](#configuration) below).

### 1.3 Verify Ollama is Running

```bash
ollama list
```

You should see `llama3.2:1b` in the list. Ollama serves on `http://localhost:11434` by default.

---

## Step 2: Set Up the Python Environment

### 2.1 Create a Virtual Environment

```bash
cd F:\draft_agent
python -m venv venv
```

### 2.2 Activate the Virtual Environment

**Windows (PowerShell):**
```powershell
.\venv\Scripts\Activate.ps1
```

**Windows (Command Prompt):**
```cmd
.\venv\Scripts\activate.bat
```

**Linux / macOS:**
```bash
source venv/bin/activate
```

### 2.3 Install Dependencies

```bash
pip install -r backend/requirements.txt
```

This installs:
- `fastapi` + `uvicorn` — Web server
- `pydantic` — Data validation
- `requests` — HTTP client for Ollama
- `sentence-transformers` — Local embedding model for RAG
- `numpy` — Vector similarity search
- `pypdf` — PDF text extraction
- `python-docx` — DOCX export

> **First Run Note:** The embedding model (`all-MiniLM-L6-v2`, ~80MB) is downloaded automatically on first startup. This is a one-time download.

---

## Step 3: Place Your Legal Documents

The system uses two types of reference documents:

### 3.1 Legal Act Documents (Guidelines)

Place your act PDFs in:
```
F:\draft_agent\data\legal_docs\
```

These are the reference legal texts the system uses for RAG retrieval. Example files:
- `posh_act.pdf` — The POSH Act, 2013
- `pocso_act.pdf` — The POCSO Act, 2012

### 3.2 Complaint Templates (Reference Format)

Place your template PDFs in:
```
F:\draft_agent\data\templates\
```

These are the approved complaint formats. Example files:
- `posh_complaint_template.pdf`
- `pocso_complaint_template.pdf`

> **Note:** The templates are already hardcoded into the system's drafting engine. The template PDFs serve as reference copies for your team.

---

## Step 4: Start the Backend Server

```bash
cd F:\draft_agent\backend
python run.py
```

You should see:
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Application startup complete.
```

---

## Step 5: Ingest Legal Documents

Before the system can reference legal acts during drafting, you need to ingest them into the vector store. 

**Option A — Via API (recommended):**
```bash
curl -X POST http://127.0.0.1:8000/api/ingest
```

**Option B — Via the Frontend UI:**
Click the **"Ingest Documents"** button in the web interface.

You should see a response like:
```json
{
  "status": "success",
  "processed_files": ["pocso_act.pdf", "posh_act.pdf"],
  "total_chunks": 5
}
```

> **Note:** Ingestion only needs to be done once, or whenever you add new legal documents. The vector store is held in memory and resets on server restart.

---

## Step 6: Open the Frontend

Open the following file in your web browser:

```
F:\draft_agent\frontend\index.html
```

The UI will connect to the backend at `http://127.0.0.1:8000`.

---

## Step 7: Verify Everything Works

Run the automated test suite:

```bash
cd F:\draft_agent
.\venv\Scripts\python.exe test_pipeline.py
```

A successful run ends with:
```
=== ALL PIPELINE TESTS PASSED ===
```

---

## Configuration

All configuration is in `backend/app/config.py` and can be overridden via environment variables:

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_URL` | `http://localhost:11434` | Ollama server URL |
| `LLM_MODEL` | `llama3.2:1b` | Ollama model name |
| `EMBEDDING_MODEL_NAME` | `sentence-transformers/all-MiniLM-L6-v2` | HuggingFace embedding model |

**Example — using a different model:**

```powershell
$env:LLM_MODEL = "qwen3:4b"
python run.py
```

---

## Troubleshooting

### "Could not connect to Ollama"
- Ensure Ollama is running: `ollama serve`
- Check the URL: default is `http://localhost:11434`
- Verify the model is pulled: `ollama list`

### "No module named pip" in venv
```bash
python -m ensurepip --upgrade
python -m pip install --upgrade pip
```

### Slow first startup
The embedding model (~80MB) downloads on first run. Subsequent startups are fast.

### Unicode errors on Windows console
The test script handles this automatically. If you see encoding errors in your own scripts, add this at the top:
```python
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
```

### Port 8000 already in use
```powershell
# Find and kill the process
Get-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess | Stop-Process -Force
```
