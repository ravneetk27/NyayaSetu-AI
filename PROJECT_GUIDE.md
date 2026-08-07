# Draft Agent — Project Guide

An AI-powered legal complaint drafting system for POSH (Prevention of Sexual Harassment at Workplace) and POCSO (Protection of Children from Sexual Offences) cases. The system classifies incidents, extracts structured facts, retrieves relevant legal context, and generates formal complaint documents.

---

## Table of Contents

- [How It Works](#how-it-works)
- [Project Structure](#project-structure)
- [System Architecture](#system-architecture)
- [API Reference](#api-reference)
- [Core Components](#core-components)
- [Design Decisions](#design-decisions)
- [Supported Categories](#supported-categories)
- [Extending the System](#extending-the-system)

---

## How It Works

The user enters a free-text incident narrative. The system processes it through a 6-step pipeline:

```
User Narrative
    │
    ▼
┌─────────────────┐
│  1. Anonymize    │  ← Redact PII (emails, phones, Aadhaar)
│     PII          │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  2. Classify     │  ← POSH / POCSO / OTHER (via LLM)
│     Incident     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  3. Extract      │  ← Names, dates, locations, witnesses (via LLM)
│     Facts        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  4. RAG          │  ← Retrieve relevant legal sections
│     Retrieval    │     from ingested act documents
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  5. Generate     │  ← Build formal complaint using
│     Draft        │     deterministic templates + LLM narrative
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  6. De-anonymize │  ← Restore real PII in final output
│     & Respond    │
└─────────────────┘
```

---

## Project Structure

```
draft_agent/
│
├── backend/                          # FastAPI backend
│   ├── app/
│   │   ├── api/
│   │   │   └── endpoints.py          # API route handlers
│   │   ├── core/
│   │   │   ├── anonymizer.py         # PII redaction/restoration
│   │   │   ├── llm.py                # Ollama LLM client (classify, extract, draft)
│   │   │   ├── rag.py                # Embedding model + vector store
│   │   │   └── exporter.py           # DOCX export utility
│   │   ├── schemas/
│   │   │   └── case.py               # Pydantic data models
│   │   ├── config.py                 # Configuration (URLs, model names, paths)
│   │   └── main.py                   # FastAPI app factory with CORS
│   ├── requirements.txt              # Python dependencies
│   └── run.py                        # Server entry point
│
├── frontend/                         # Vanilla HTML/CSS/JS UI
│   ├── index.html                    # Single-page application
│   ├── css/
│   │   └── styles.css                # Dark theme styling
│   └── js/
│       └── app.js                    # API client and DOM logic
│
├── data/
│   ├── legal_docs/                   # Place act PDFs here (auto-created)
│   │   ├── posh_act.pdf
│   │   └── pocso_act.pdf
│   └── templates/                    # Complaint template PDFs (reference)
│       ├── posh_complaint_template.pdf
│       └── pocso_complaint_template.pdf
│
├── test_pipeline.py                  # End-to-end integration tests
├── verify_setup.py                   # Quick setup verification script
├── SETUP_GUIDE.md                    # Installation instructions
└── PROJECT_GUIDE.md                  # This file
```

---

## System Architecture

### Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Frontend** | Vanilla HTML/CSS/JS | Single-page UI with dark theme |
| **Backend** | FastAPI + Uvicorn | REST API server |
| **LLM** | Ollama (`llama3.1:8b`) | Classification, fact extraction, narrative polishing |
| **Embeddings** | `sentence-transformers/all-MiniLM-L6-v2` | Local embedding model for RAG |
| **Vector Store** | In-memory NumPy | Cosine similarity search over document chunks |
| **PDF Parsing** | PyPDF | Extract text from legal act PDFs |
| **Export** | python-docx | Generate downloadable DOCX complaint files |

### Data Flow

```
Frontend (HTML/JS)
    │
    │  POST /api/analyze  { raw_text: "..." }
    ▼
FastAPI Backend
    │
    ├── Anonymizer ──── regex-based PII detection
    ├── OllamaClient ── HTTP calls to localhost:11434
    ├── LegalRAG ────── sentence-transformers embeddings
    │                    + NumPy cosine similarity
    └── Exporter ────── python-docx DOCX generation
```

---

## API Reference

### `POST /api/ingest`

Scans the `data/legal_docs/` directory and ingests all PDF and TXT files into the in-memory vector store for RAG retrieval.

**Request:** No body required.

**Response:**
```json
{
  "status": "success",
  "processed_files": ["posh_act.pdf", "pocso_act.pdf"],
  "total_chunks": 5
}
```

---

### `POST /api/analyze`

The core pipeline endpoint. Takes a free-text incident narrative and returns classification, extracted facts, a generated complaint draft, and a mandatory reporting alert.

**Request:**
```json
{
  "raw_text": "My supervisor Raj Malhotra has been sending me inappropriate personal messages and making uncomfortable remarks during meetings at our Noida office..."
}
```

**Response:**
```json
{
  "classification": {
    "category": "POSH",
    "confidence": 0.8,
    "minor_involved": false,
    "rationale": "Workplace harassment by a supervisor..."
  },
  "extracted_facts": {
    "complainant_name": "Priya Sharma",
    "respondent_name": "Raj Malhotra",
    "incident_date": "Last month",
    "incident_location": "Noida office",
    "nature_of_incident": "Inappropriate personal messages...",
    "witnesses": ["Amit Sen"],
    "evidence_description": ["Emails"]
  },
  "draft": {
    "category": "POSH",
    "addressed_to": "The Presiding Officer, Internal Committee (IC), [Organization Name]",
    "draft_text": "FORMAL COMPLAINT UNDER THE POSH ACT, 2013\n...",
    "disclaimer": "DISCLAIMER: This complaint draft was generated using AI...",
    "citations": [...]
  },
  "mandatory_report_alert": false
}
```

---

### `POST /api/export`

Generates a downloadable DOCX file from a complaint draft object.

**Request:** A `ComplaintDraft` JSON object (same structure as `draft` in the analyze response).

**Response:** Binary DOCX file download.

---

## Core Components

### 1. Anonymizer (`backend/app/core/anonymizer.py`)

Detects and replaces PII using regex patterns before sending text to the LLM:

| PII Type | Pattern | Replacement |
|---|---|---|
| Email addresses | `\b[\w.-]+@[\w.-]+\.\w+\b` | `[EMAIL_1]`, `[EMAIL_2]`, ... |
| Phone numbers | `\b\d{10}\b` | `[PHONE_1]`, `[PHONE_2]`, ... |
| Aadhaar numbers | `\b\d{4}\s?\d{4}\s?\d{4}\b` | `[AADHAAR_1]`, ... |

The anonymizer returns a mapping dictionary that is used to restore PII in the final output.

---

### 2. LLM Client (`backend/app/core/llm.py`)

Communicates with the local Ollama server via HTTP. Three main functions:

#### `classify_narrative(narrative) → ClassificationResult`
- Classifies input as **POSH**, **POCSO**, or **OTHER**
- Returns confidence score and whether a minor is involved
- Uses JSON mode for structured output

#### `extract_facts(narrative) → ExtractedFacts`
- Extracts: complainant name, respondent name, date, location, nature of incident, witnesses, evidence
- Uses JSON mode for structured output

#### `generate_draft(category, facts, contexts) → ComplaintDraft`
- Builds the complaint document using **deterministic Python templates**
- Uses the LLM only for polishing the incident narrative paragraph
- Validates LLM output to prevent hallucination (falls back to deterministic narrative if needed)

---

### 3. RAG Engine (`backend/app/core/rag.py`)

Provides retrieval-augmented generation using local embeddings:

1. **Ingestion**: Reads PDFs/TXTs from `data/legal_docs/`, chunks them, and computes embeddings using `all-MiniLM-L6-v2`
2. **Search**: Given a query, computes its embedding and finds the top-K most similar document chunks via cosine similarity
3. **Storage**: In-memory NumPy arrays (no external database needed)

---

### 4. Exporter (`backend/app/core/exporter.py`)

Generates a formatted DOCX file from the complaint draft, suitable for printing or submission.

---

### 5. Frontend (`frontend/`)

A single-page application with:
- Text input area for incident narratives
- "Ingest Documents" button for loading legal references
- "Analyze" button to run the pipeline
- Results panel showing classification, facts, and the generated draft
- "Download DOCX" button for export

---

## Design Decisions

### Why Deterministic Templates Instead of LLM-Generated Complaints?

The `llama3.1:8b` model is highly capable, but has two critical limitations:

1. **Safety filter refusals** — The model refuses to draft complaints about harassment or child abuse, responding with *"I cannot create a formal complaint that includes details about sexual harassment."*

2. **Hallucination** — When it does generate content, it often invents completely unrelated facts (wrong names, dates, locations).

**Solution:** The complaint document structure (headers, sections, legal declarations) is built entirely in Python. The LLM's role is limited to:
- Classification and fact extraction (structured JSON — works reliably)
- Polishing a pre-built incident narrative paragraph (with validation to catch hallucinations)

This ensures the output is **always correctly structured**, **always references the right facts**, and **never triggers safety refusals**.

### Why In-Memory Vector Store?

For an MVP running locally with a small number of legal documents (2-4 PDFs), a full vector database (ChromaDB, FAISS, etc.) adds unnecessary complexity. NumPy cosine similarity over a few hundred chunks is fast enough (<10ms) and requires zero infrastructure.

### Why PII Anonymization?

Even though the LLM runs locally, anonymization is a best practice for legal applications. It also prepares the system for future deployment where the LLM might be cloud-hosted.

---

## Supported Categories

### POSH (Prevention of Sexual Harassment at Workplace Act, 2013)

- **Addressed To:** Internal Committee (IC) Presiding Officer
- **Template:** Formal complaint with 7 sections (complainant, respondent, incident, witnesses, evidence, relief, declaration)
- **Legal References:** Section 9, Section 16 (confidentiality), Section 13 (action)
- **Mandatory Report:** No (handled internally by IC)

### POCSO (Protection of Children from Sexual Offences Act, 2012)

- **Addressed To:** Officer-in-Charge, SJPU / Local Police Station
- **Template:** Formal report with 8 sections (reporting person, child victim, accused, incident, witnesses, evidence, safety needs, declaration)
- **Legal References:** Section 19 (mandatory reporting), Section 21 (failure to report penalty), Section 23 (identity protection)
- **Mandatory Report:** **Yes** — system displays a mandatory reporting alert

### OTHER

- **Addressed To:** The Appropriate Authority
- **Template:** General complaint format
- **Mandatory Report:** No

---

## Extending the System

### Adding a New Legal Category

1. **Update classification prompt** in `llm.py` → `classify_narrative()` to include the new category
2. **Add a new template block** in `llm.py` → `generate_draft()` under the `if/elif/else` chain
3. **Add legal documents** to `data/legal_docs/` and re-run ingestion
4. **Update the frontend** to handle the new category's display

### Using a Larger LLM

Update the model in `config.py` or via environment variable:
```python
LLM_MODEL = "qwen3:4b"  # or "llama3.2:3b", "mistral:7b", etc.
```

Larger models will produce better incident narratives and more accurate fact extraction.

### Adding a Database

Replace the in-memory vector store in `rag.py` with ChromaDB or FAISS for persistent storage:
```bash
pip install chromadb
```

### Adding Authentication

Add FastAPI security dependencies for production use:
```python
from fastapi.security import HTTPBearer
```

---

## License

Internal use only. The legal act documents (POSH Act, POCSO Act) are public Indian legislation.
