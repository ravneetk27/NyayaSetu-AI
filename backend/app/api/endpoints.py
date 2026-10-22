from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from app.schemas.case import (
    AnalyzeComplaintRequest, 
    AnalyzeComplaintResponse, 
    IngestResponse,
    ComplaintDraft,
    RetrievedContext,
    ExtractedFacts,
    AgentResponsePayload
)
from app.core.anonymizer import Anonymizer
from app.core.llm import OllamaClient, OUT_OF_SCOPE_MESSAGE
from app.core.rag import LegalRAG
from app.core.exporter import export_to_docx
import io
import json

router = APIRouter()
ollama_client = OllamaClient()
rag_engine = LegalRAG()

@router.post("/ingest", response_model=IngestResponse)
def ingest_documents():
    """Scan the data directory and ingest new PDFs/TXTs into the vector DB."""
    try:
        processed_files, total_chunks = rag_engine.ingest_documents()
        return IngestResponse(
            status="success" if total_chunks > 0 else "no_files_found",
            processed_files=processed_files,
            total_chunks=total_chunks
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")

@router.post("/analyze", response_model=AnalyzeComplaintResponse)
def analyze_complaint(request: AnalyzeComplaintRequest):
    """
    Core pipeline:
    1. Extract narrative from raw_text or compile chat messages history.
    2. Anonymize input (PII protection).
    3. Classify (POSH, POCSO, OTHER).
    4. Extract facts.
    5. Retrieve legal guidelines via local vector search.
    6. Draft formal complaint in standard 8-section template format.
    7. De-anonymize draft + facts back to real details for the user.
    """
    raw_text = ""
    is_chat_mode = False
    if request.messages and len(request.messages) > 0:
        is_chat_mode = True
        msg_dicts = [{"role": m.role, "content": m.content} for m in request.messages]
        extracted_facts = ollama_client.extract_facts_from_chat(msg_dicts)
        raw_text = f"{extracted_facts.complainant_name} {extracted_facts.nature_of_incident} {extracted_facts.incident_location}"
    elif request.raw_text and request.raw_text.strip():
        raw_text = request.raw_text.strip()
    
    if not raw_text:
        raise HTTPException(status_code=400, detail="Incident narrative or chat history cannot be empty.")

    # Domain relevance check across full text
    is_relevant = ollama_client.check_domain_relevance(raw_text)

    try:
        # Step 1: Anonymize
        anonymizer = Anonymizer()
        anon_text, pii_map = anonymizer.anonymize(raw_text)

        # Step 2: Classify
        classification = ollama_client.classify_narrative(anon_text)

        if classification.category == "OTHER":
            empty_facts = ExtractedFacts(
                complainant_name="[Not Applicable]",
                complainant_age="[Not Applicable]",
                respondent_name="[Not Applicable]",
                incident_date="[Not Applicable]",
                incident_location="[Not Applicable]",
                nature_of_incident="Out of scope query",
                witnesses=[],
                evidence_description=[]
            )
            draft = ComplaintDraft(
                category="OTHER",
                addressed_to="[Not Applicable]",
                draft_text="Complaint drafting is not applicable for out-of-scope incidents.",
                disclaimer="[Not Applicable]",
                citations=[]
            )
            payload = ollama_client.build_agent_response_payload(
                is_relevant=False,
                action_triggered="GENERATE_DRAFT",
                advice_response=OUT_OF_SCOPE_MESSAGE,
                facts=empty_facts,
                formatted_draft=""
            )
            return AnalyzeComplaintResponse(
                classification=classification,
                extracted_facts=empty_facts,
                draft=draft,
                mandatory_report_alert=False,
                payload=payload
            )

        # Step 3: Extract Facts (if not chat mode)
        if not is_chat_mode:
            extracted_facts = ollama_client.extract_facts(anon_text)

        # Step 4: RAG Retrieval
        search_query = f"{extracted_facts.nature_of_incident} {classification.category.lower()}"
        retrieved_results = rag_engine.search(search_query, top_k=3)
        
        contexts = [
            RetrievedContext(
                source=res["source"],
                text_snippet=res["text_snippet"],
                relevance_score=res["relevance_score"]
            )
            for res in retrieved_results
        ]

        # Step 5: Draft Generation
        draft = ollama_client.generate_draft(
            category=classification.category,
            facts=extracted_facts,
            contexts=contexts
        )

        # Step 6: De-anonymize
        if extracted_facts.complainant_name:
            extracted_facts.complainant_name = anonymizer.deanonymize(extracted_facts.complainant_name, pii_map)
        if extracted_facts.respondent_name:
            extracted_facts.respondent_name = anonymizer.deanonymize(extracted_facts.respondent_name, pii_map)
        if extracted_facts.respondent_designation:
            extracted_facts.respondent_designation = anonymizer.deanonymize(extracted_facts.respondent_designation, pii_map)
        if extracted_facts.incident_location:
            extracted_facts.incident_location = anonymizer.deanonymize(extracted_facts.incident_location, pii_map)
        if extracted_facts.incident_time:
            extracted_facts.incident_time = anonymizer.deanonymize(extracted_facts.incident_time, pii_map)
            
        extracted_facts.witnesses = [anonymizer.deanonymize(w, pii_map) for w in extracted_facts.witnesses]
        extracted_facts.evidence_description = [anonymizer.deanonymize(e, pii_map) for e in extracted_facts.evidence_description]

        draft.draft_text = anonymizer.deanonymize(draft.draft_text, pii_map)

        mandatory_report = (classification.category == "POCSO") or classification.minor_involved

        payload = ollama_client.build_agent_response_payload(
            is_relevant=is_relevant,
            action_triggered="GENERATE_DRAFT",
            advice_response="Formal complaint draft generated successfully under POSH/POCSO guidelines.",
            facts=extracted_facts,
            formatted_draft=draft.draft_text
        )

        return AnalyzeComplaintResponse(
            classification=classification,
            extracted_facts=extracted_facts,
            draft=draft,
            mandatory_report_alert=mandatory_report,
            payload=payload
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Analysis pipeline error: {str(e)}")

@router.post("/export")
def export_complaint(draft: ComplaintDraft):
    """Generate and download a DOCX file of the complaint draft."""
    try:
        file_stream = export_to_docx(
            draft_text=draft.draft_text,
            category=draft.category,
            addressed_to=draft.addressed_to,
            disclaimer=draft.disclaimer,
            facts=draft.facts,
        )
        return StreamingResponse(
            file_stream,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f"attachment; filename=complaint_draft_{draft.category.lower()}.docx"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate export file: {str(e)}")
