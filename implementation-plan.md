# Implementation Plan: PoSH/POCSO Legal Advisory AI Agent

## 0. Project Summary

Build a web application that lets a user describe a workplace harassment or child-safety incident in plain language, then:
1. Classifies it as PoSH (adult workplace harassment), POCSO (minor involved), or Other.
2. Extracts structured facts (dates, parties, incident details, witnesses, evidence).
3. Retrieves relevant statutory sections via RAG.
4. Generates a formal complaint draft addressed to the correct authority (Internal Committee for PoSH, Police/SJPU for POCSO).
5. Enforces mandatory-reporting logic and PII protection throughout.

This is a sensitive-data application (legal + personal safety information). Security, privacy, and correct routing (especially the POCSO mandatory-reporting path) are first-class requirements, not afterthoughts.

---

## 1. Documents & Resources YOU Need to Gather Before/During Build

A coding agent cannot legally source or verify these — provide them as files/text in the repo before RAG ingestion begins.

| # | Document | Purpose | Notes |
|---|---|---|---|
| 1 | Official text of the **Sexual Harassment of Women at Workplace (Prevention, Prohibition and Redressal) Act, 2013 (PoSH Act)** | RAG source for PoSH provisions | Get from India Code (indiacode.nic.in) or Ministry of Women & Child Development site — use the authoritative gazette PDF, not a summary blog |
| 2 | Official text of the **Protection of Children from Sexual Offences Act, 2012 (POCSO Act)**, including 2019 amendments | RAG source for POCSO provisions | Same source — India Code |
| 3 | PoSH Act **Rules, 2013** and any state-specific rules | Procedural detail (timelines, IC composition) | |
| 4 | Your organization's internal **HR policy / SOP for harassment complaints** | RAG source, used to tailor draft to internal process | Confirm you have rights to digitize/store it |
| 5 | Standard **complaint format templates** (IC complaint format, police FIR format if applicable) | Drafting templates | Often available from your legal/HR team or IC |
| 6 | **Legal review sign-off** — a licensed lawyer or your legal/compliance team must review all system prompts, generated draft templates, and the guardrail rules before this goes live | Not optional — see §9 | This is the single most important non-technical requirement |
| 7 | **Data Protection / Privacy Officer sign-off** on the data handling design (§8) | Required if this processes real employee/user data | Especially relevant under India's DPDP Act, 2023 |
| 8 | List of **mandatory reporting authorities** with correct contact/routing info for your jurisdiction (local police, SJPU contacts) | Needed to populate the POCSO alert flow | Do not hardcode a single generic number — verify per deployment region |
| 9 | LLM provider **API key(s)** (OpenAI, Anthropic, or self-hosted model access) | Runtime dependency | See §4 for self-hosting option if data cannot leave premises |
|10 | Company branding/letterhead assets (optional) | For exported PDF/Word drafts | |

**Do not let the coding agent proceed to Phase 3 (RAG ingestion) until items 1–5 are actually in the repo as files.** Everything else in this plan can be built and tested with dummy/synthetic data in the meantime.

---

## 2. Requirements

### 2.1 Functional Requirements
- FR1: Accept free-text user input describing an incident (chat interface or structured multi-step form).
- FR2: Classify input as `POSH`, `POCSO`, or `OTHER` with a confidence score.
- FR3: If `POCSO` is detected, immediately surface a mandatory-reporting alert in the UI before any drafting occurs, and route the eventual draft to police/SJPU, not an internal committee.
- FR4: Extract structured entities: complainant, respondent/accused, date(s)/time(s) of incident, nature of incident, location, witnesses, evidence description.
- FR5: Retrieve relevant statutory sections and internal SOP excerpts relevant to the classified case type.
- FR6: Generate a formal, chronological, objective complaint draft using extracted facts + retrieved legal context.
- FR7: Let the user view and edit the draft in a rich text editor before export.
- FR8: Export the final draft as PDF and/or DOCX.
- FR9: Never present the AI's output as binding legal advice — every draft must carry a visible disclaimer.
- FR10: Maintain an audit log of case classification and processing steps (not raw narrative text — see §8) for compliance tracking.

### 2.2 Non-Functional Requirements
- NFR1 (Privacy): No raw PII sent to any third-party LLM API without anonymization first (§8.1).
- NFR2 (Data retention): Raw user narrative is processed in memory and not persisted unless the user explicitly opts in and it is encrypted at rest.
- NFR3 (Security): All data in transit over TLS; all data at rest (Postgres) encrypted; secrets managed via environment variables/secret manager, never committed to the repo.
- NFR4 (Accuracy): The system must not fabricate legal citations — every statutory reference in a draft must be traceable to a retrieved chunk (RAG grounding), not model memory.
- NFR5 (Availability): Should degrade gracefully — if the LLM API is down, the app must show an error state, not silently produce a broken draft.
- NFR6 (Accessibility): UI must meet WCAG 2.1 AA at minimum, given trauma-informed design needs (large touch targets, calm color palette, no auto-playing media, clear exit/save-and-leave option).
- NFR7 (Auditability): Every classification decision and mandatory-report trigger must be logged with a timestamp and immutable record.
- NFR8 (Jurisdiction): The system must be configurable per-deployment for jurisdiction-specific authority contact info (India-specific by default, per the source document).

### 2.3 Explicit Non-Goals
- This system does not provide binding legal advice or represent itself as a lawyer.
- This system does not automatically submit complaints to police or IC on the user's behalf — it prepares a draft; a human decides to submit it. (Exception: the mandatory-reporting alert notifies/instructs the user of their legal obligation; it does not auto-file.)

---

## 3. Architecture Overview

```
[React/Next.js Frontend]
        │  HTTPS/JSON
        ▼
[FastAPI Backend] ──► [PII Anonymizer (Presidio)] ──► [LangChain Pipeline]
        │                                                    │
        │                                          ┌─────────┼─────────┐
        │                                          ▼         ▼         ▼
        │                                   [Classifier] [Extractor] [Drafter]
        │                                                              │
        │                                                              ▼
        │                                                     [Vector DB Retrieval
        │                                                      (ChromaDB/FAISS)]
        ▼
[PostgreSQL: users, case metadata, audit logs — NOT raw narratives]
```

---

## 4. Technology Stack (fixed for this build)

- **Frontend:** React.js (or Next.js), TypeScript, a rich text editor (TipTap or Slate), Tailwind CSS.
- **Backend:** Python 3.11+, FastAPI, Uvicorn, Pydantic v2.
- **Orchestration:** LangChain (LCEL chains) — LlamaIndex is an acceptable substitute for the RAG layer only.
- **Relational DB:** PostgreSQL 15+, SQLAlchemy + Alembic for migrations.
- **Vector DB:** ChromaDB (local/self-hosted default). Design the retriever behind an interface so Pinecone/FAISS can be swapped in later.
- **LLM:** Provider-agnostic via LangChain's chat model interface. Default to an API-based model (e.g., GPT-4o or Claude) for prototyping; document how to swap to a self-hosted model (Ollama/vLLM with Llama 3) for deployments requiring full data locality.
- **Embeddings:** `text-embedding-3-small` (OpenAI) or `all-MiniLM-L6-v2` (HuggingFace, local, no external call — preferred default for privacy).
- **PII Anonymization:** Microsoft Presidio (`presidio-analyzer`, `presidio-anonymizer`).
- **Guardrails:** NeMo Guardrails, or a custom rule layer (regex + a "no binding legal advice" system-prompt clause + output post-filter) if NeMo adds too much complexity for v1.
- **Export:** `python-docx` and `weasyprint` or `reportlab` for PDF.
- **Auth:** JWT-based session auth (or NextAuth if using Next.js) — even an MVP handling this data needs login, not anonymous access.
- **Testing:** `pytest` (backend), `vitest`/`jest` + React Testing Library (frontend).

---

## 5. Data Models

### 5.1 Pydantic Schemas (backend/app/schemas.py)

```python
from pydantic import BaseModel, Field
from typing import Literal, Optional
from datetime import date

class ClassificationResult(BaseModel):
    category: Literal["POSH", "POCSO", "OTHER"]
    confidence: float = Field(ge=0, le=1)
    minor_involved: bool
    rationale: str

class ExtractedFacts(BaseModel):
    complainant_name: Optional[str]
    respondent_name: Optional[str]
    incident_dates: list[date] = []
    incident_location: Optional[str]
    nature_of_incident: str
    witnesses: list[str] = []
    evidence_description: list[str] = []

class RetrievedContext(BaseModel):
    source: str          # e.g. "PoSH Act 2013, Section 9"
    text_snippet: str
    relevance_score: float

class ComplaintDraft(BaseModel):
    category: Literal["POSH", "POCSO"]
    addressed_to: str    # "Internal Committee" or "Local Police / SJPU"
    draft_text: str
    disclaimer: str
    citations: list[RetrievedContext]

class AnalyzeComplaintRequest(BaseModel):
    raw_text: str

class AnalyzeComplaintResponse(BaseModel):
    classification: ClassificationResult
    extracted_facts: ExtractedFacts
    draft: ComplaintDraft
    mandatory_report_alert: bool
```

### 5.2 PostgreSQL Tables (conceptual — implement via SQLAlchemy models + Alembic migration)

- `users (id, email_hash, created_at, ...)`
- `cases (id, user_id, category, status, created_at, updated_at)` — **no raw narrative text stored here**
- `audit_log (id, case_id, event_type, event_detail_json, created_at)` — logs classification events, mandatory-report triggers, export events; `event_detail_json` must not contain raw PII
- `encrypted_narratives (id, case_id, ciphertext, created_at)` — **only populated if user explicitly opts in to save**, encrypted with a key not stored in the same DB

---

## 6. Phased Build Plan (hand this section to the coding agent as the execution order)

### Phase 0 — Repo Scaffold
1. Create monorepo structure:
   ```
   /frontend       (React/Next.js app)
   /backend        (FastAPI app)
   /backend/app/chains      (LangChain pipeline code)
   /backend/app/models      (SQLAlchemy models)
   /backend/app/schemas.py  (Pydantic schemas from §5.1)
   /backend/app/rag         (ingestion + retriever code)
   /data/legal_sources       (PoSH Act, POCSO Act, SOP PDFs — gitignored, populated manually per §1)
   /docs
   ```
2. `.gitignore`: `.env`, `/data/legal_sources/*`, `*.pdf`, vector DB persistence dir.
3. Set up `.env.example` listing required environment variables (LLM API key, DB URL, encryption key, JWT secret) — never commit actual secrets.
4. Docker Compose for local dev: `postgres`, `backend`, `frontend`, and a `chroma` service if using ChromaDB in server mode.

### Phase 1 — Prompt Prototyping
Deliverable: `/backend/app/chains/prompts.py` with three versioned prompt templates.

1. **Classifier prompt** — must output structured JSON matching `ClassificationResult`. Use function-calling / tool-use or Pydantic-constrained output (e.g., LangChain's `.with_structured_output()`), not free text parsing.
2. **Extractor prompt** — outputs `ExtractedFacts` JSON, same structured-output approach.
3. **Drafter prompt** — takes `ExtractedFacts` + `RetrievedContext[]`, outputs `ComplaintDraft` JSON. Must instruct the model to:
   - Only cite statutory sections present in the provided context (no fabrication).
   - Use a neutral, chronological, professional tone.
   - Address the draft to "Internal Committee" for POSH or "Local Police / Special Juvenile Police Unit" for POCSO.
   - Always include the fixed disclaimer text (see §9.3) verbatim.
4. Write at least 10 synthetic test cases (mix of PoSH, POCSO, ambiguous/OTHER) in `/backend/tests/fixtures/sample_narratives.py` and validate classifier + extractor outputs against expected values before moving to Phase 2.

### Phase 2 — LangChain Pipeline (no RAG yet, stub the context)
1. Implement `AnonymizerStep` wrapping Presidio: input raw text → output anonymized text + a mapping dict (kept only in-memory/request-scope, never logged).
2. Implement `ClassifierChain`, `ExtractorChain` using the Phase 1 prompts with structured output.
3. Chain them with LCEL: `anonymize | classify | extract`.
4. Add a `RiskGate` step: if `classification.minor_involved is True`, set a flag that the API layer will use to force the mandatory-reporting response path (FR3) — this must happen before the drafting step runs, not after.
5. Unit test the full chain against the Phase 1 fixtures with a mocked LLM to keep tests deterministic and free.

### Phase 3 — RAG Layer
**Blocked until source documents from §1 are in `/data/legal_sources/`.**
1. Ingestion script `/backend/app/rag/ingest.py`:
   - Load PDFs (`pypdf` or `unstructured`).
   - Chunk with a legal-document-aware splitter (e.g., split on numbered sections/clauses, target ~500 tokens/chunk with overlap).
   - Tag each chunk with metadata: `{source_act, section_number, doc_type}`.
   - Embed with the chosen embedding model and upsert into ChromaDB, one collection per source type (`posh_act`, `pocso_act`, `internal_sop`).
2. Implement `RetrieverStep`: given `classification.category`, query only the relevant collection(s), return top-k chunks as `RetrievedContext[]`.
3. Wire retriever into the pipeline before the drafting step: `anonymize | classify | extract | retrieve | draft`.
4. Add a grounding check: reject/flag any drafted citation that doesn't match a section number present in the retrieved context (simple regex cross-check is sufficient for v1).

### Phase 4 — Backend API
1. `POST /analyze-complaint` — implements `AnalyzeComplaintRequest` → `AnalyzeComplaintResponse`, runs the full pipeline, de-anonymizes names back into the final draft text only (using the in-memory mapping from step 2.1), and returns the response. This endpoint must require authentication.
2. `POST /export` — accepts an edited draft + format (`pdf`/`docx`), returns a file/download URL.
3. `POST /cases` (optional persistence) — only writes to `audit_log`/`cases`; writes to `encrypted_narratives` only if `save_requested: true` is explicitly passed.
4. Standard auth endpoints (`/login`, `/logout`, session refresh) — implement before exposing `/analyze-complaint` publicly.
5. Global error handler: LLM/API failures return a clear 5xx with a user-safe message, never a stack trace.
6. Rate limiting on `/analyze-complaint` (e.g., `slowapi`) to control LLM cost and abuse.

### Phase 5 — Frontend
1. Auth screens (login).
2. Main intake screen: calm, uncluttered layout; large text area; visible privacy note near the input ("Your story is processed securely; see our privacy policy").
3. On submit → call `/analyze-complaint`, show a loading state with reassuring, non-alarming copy.
4. **Mandatory reporting modal:** if `mandatory_report_alert` is true, show this before the draft — non-dismissible without acknowledgment, states the legal obligation under POCSO Section 19, and provides the correct police/SJPU contact info (from §1 item 8). This must render even if the rest of the UI has an error.
5. Draft review screen: rich text editor pre-populated with `draft.draft_text`, visible disclaimer (`draft.disclaimer`) pinned above/below the editor, list of citations shown alongside for transparency.
6. Export buttons (PDF/DOCX) calling `/export`.
7. "Delete my data" / "I don't want this saved" control, defaulting to *not saved* (NFR2).

### Phase 6 — Security, Privacy & Guardrails Hardening
1. Confirm Presidio anonymization runs on 100% of text before it leaves the process boundary to any external LLM API call — write an integration test that asserts no configured PII entity types appear in the outbound request payload.
2. Confirm `encrypted_narratives` uses field-level encryption (e.g., `cryptography.fernet` or pgcrypto) with the key sourced from a secrets manager, not the app's own database.
3. Implement the guardrail layer (NeMo Guardrails or custom):
   - Block the model from stating a definitive legal outcome ("you will win your case").
   - Enforce the disclaimer is always present, unmodified, in every generated draft.
   - Enforce POCSO drafts are always addressed to police/SJPU, never IC, regardless of what the drafting model outputs (deterministic override, not just a prompt instruction).
4. Add CSP headers, HTTPS-only cookies, CSRF protection on state-changing endpoints.
5. Dependency/security scan (`pip-audit`, `npm audit`) in CI.
6. Load-test the anonymization + LLM calls for latency; add request timeouts.

### Phase 7 — Testing & QA
1. Unit tests for every chain step (mocked LLM).
2. Integration test for the full `/analyze-complaint` flow against the synthetic fixtures from Phase 1, asserting: correct classification, correct routing (IC vs police), disclaimer present, no un-grounded citations.
3. A dedicated regression suite of POCSO-triggering inputs to confirm the mandatory-report path fires every time (this is the highest-stakes correctness requirement in the system).
4. Accessibility audit (axe-core) on the frontend.
5. Manual legal review of 20+ generated drafts by qualified legal reviewer (§1 item 6) before any real-user pilot.

### Phase 8 — Deployment
1. Containerize backend and frontend; document environment variables required per §0 scaffold.
2. Choose hosting with data residency appropriate to jurisdiction (relevant given DPDP Act, 2023, if deploying in India).
3. Set up CI/CD: run test suite (Phase 7) on every PR; block deploy on test failure.
4. Configure production secrets via a secrets manager (AWS Secrets Manager / GCP Secret Manager / Vault) — never plain env files in production.
5. Set up monitoring/alerting on `/analyze-complaint` error rate and latency, and on audit-log write failures (a silent audit-log failure is itself a compliance risk).

---

## 7. Suggested Repo-Level Task Breakdown for the Coding Agent

Feed phases 0–8 above to the coding agent roughly in order; each phase's steps are individually sized to be reasonable single tasks/PRs. Suggested acceptance criteria per phase:
- Phase 0: `docker-compose up` boots all services with no errors.
- Phase 1: prompt unit tests pass on ≥9/10 synthetic fixtures.
- Phase 2: chain runs end-to-end on mocked LLM with correct risk-gate flagging.
- Phase 3: retriever returns correctly-scoped, correctly-cited chunks for both PoSH and POCSO test queries.
- Phase 4: `/analyze-complaint` returns a schema-valid response for all fixtures; auth required and enforced.
- Phase 5: manual click-through confirms mandatory-reporting modal cannot be bypassed.
- Phase 6: PII integration test passes; guardrail deterministic-override test passes.
- Phase 7: full test suite green; legal review checklist signed off.
- Phase 8: successful staging deploy with monitoring live.

---

## 8. Data Handling Rules Summary (reference for every phase)

1. Raw narrative text is anonymized before any external API call.
2. Raw narrative text is not persisted to the primary database by default.
3. Persistence only occurs on explicit user opt-in, and only in encrypted form.
4. Audit logs record events and metadata, never raw sensitive text.
5. De-anonymization (swapping placeholders back to real names) happens only in-memory, at the final response-assembly step, scoped to a single request.

---

## 9. Legal/Compliance Guardrails Summary (reference for Phase 1 and Phase 6)

1. Every generated draft carries a visible disclaimer, e.g.: *"This document was drafted with AI assistance based on the information you provided. It is not a substitute for professional legal advice. Please review it carefully, and consult a lawyer or your organization's Internal Committee/legal counsel before submission."*
2. POCSO-classified cases always route to police/SJPU addressing, enforced deterministically, not solely via prompt instruction.
3. The system never tells a user whether they will win or lose a case, or gives definitive legal predictions.
4. All statutory citations in a draft must be traceable to retrieved RAG context (§3 of the phased plan, grounding check).
5. This entire system requires sign-off from a qualified legal professional before real users rely on its output — flag this clearly to the coding agent as a human checkpoint, not something it can complete.

---

## 10. Open Questions to Resolve Before Phase 3 (surface these to the user, don't guess)

- Which LLM provider will be used in production — API-based (data leaves premises even if anonymized) or self-hosted (Llama 3 via Ollama/vLLM)? This affects Phase 0 infra and Phase 6 threat model.
- Single-organization deployment (one company's IC/SOP) or multi-tenant (many organizations, each with their own SOP/IC)? This changes the data model in §5.2 significantly (tenant scoping needed).
- Jurisdiction(s) to support at launch — affects §1 item 8 and NFR8.
- Who is the legal reviewer of record for sign-off in §9.5, and what is their review timeline?
